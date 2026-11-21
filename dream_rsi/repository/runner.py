from __future__ import annotations
import os
import hashlib, shutil, subprocess, tempfile, time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Sequence
from dream_rsi.repository.patching import PatchSet, apply_patchset
from dream_rsi.execution.docker_sandbox import DockerSandbox

@dataclass(frozen=True)
class RepositoryRunResult:
    success: bool
    returncode: int
    stdout: str
    stderr: str
    duration_s: float
    timed_out: bool
    mode: str
    changed_files: tuple[str,...]
    fingerprint: str
    command: tuple[str,...]
    def manifest(self): return asdict(self)

class RepositoryRunner:
    """Runs repository tests in an ephemeral workspace. Docker is preferred; local execution is explicit fallback."""
    def __init__(self, timeout_s=60.0, prefer_docker=True, allow_local_fallback=None, image='python:3.12-alpine'):
        self.timeout_s=timeout_s; self.prefer_docker=prefer_docker
        if allow_local_fallback is None:
            self.allow_local_fallback = os.getenv("DREAM_RSI_ENV", "development").lower() != "production"
        else:
            self.allow_local_fallback = allow_local_fallback
        self.docker=DockerSandbox(timeout_s=timeout_s, image=image)
    @staticmethod
    def fingerprint(root):
        root=Path(root); h=hashlib.sha256()
        for p in sorted(x for x in root.rglob('*') if x.is_file() and '.git' not in x.parts and '__pycache__' not in x.parts):
            h.update(str(p.relative_to(root)).encode()); h.update(p.read_bytes())
        return h.hexdigest()
    def _local(self, root, command):
        start=time.perf_counter()
        try:
            p=subprocess.run(command,cwd=root,capture_output=True,text=True,timeout=self.timeout_s)
            return p.returncode,p.stdout[-10000:],p.stderr[-10000:],False,time.perf_counter()-start
        except subprocess.TimeoutExpired as e:
            return -1,(e.stdout or '')[-10000:],(e.stderr or '')[-10000:],True,time.perf_counter()-start
    def run(self, repository, command: Sequence[str], patchset: PatchSet|None=None):
        src=Path(repository).resolve()
        if not src.exists(): raise FileNotFoundError(src)
        with tempfile.TemporaryDirectory(prefix='dream-rsi-repo-') as td:
            td_path = Path(td)
            td_path.chmod(0o755)
            root = td_path / 'repo'
            shutil.copytree(src, root, ignore=shutil.ignore_patterns('.git', '__pycache__'))
            changed = tuple(apply_patchset(root, patchset)) if patchset else ()
            mode = 'local-fallback'; start = time.perf_counter()
            executed_docker = False
            if self.prefer_docker and self.docker.available:
                # Ensure unprivileged (--cap-drop ALL) container users can traverse, read, and write in /workspace.
                root.chmod(0o777)
                for item in root.rglob('*'):
                    try:
                        if item.is_dir():
                            item.chmod(0o777)
                        elif os.access(item, os.X_OK):
                            item.chmod(0o775)
                        else:
                            item.chmod(0o666)
                    except OSError:
                        pass
                # Mount repo read-write only inside the ephemeral container. Command is explicit and task-controlled.
                cmd=['docker','run','--rm','--network','none','--cap-drop','ALL','--security-opt','no-new-privileges',
                     '--pids-limit','128','--memory','512m','--cpus','1.0','--tmpfs','/tmp:rw,noexec,nosuid,size=64m',
                     '--mount',f'type=bind,src={root},dst=/workspace,rw','-w','/workspace',self.docker.image,*command]
                try:
                    p=subprocess.run(cmd,capture_output=True,text=True,timeout=self.timeout_s)
                    rc,out,err,timed=p.returncode,p.stdout[-10000:],p.stderr[-10000:],False
                    from dream_rsi.execution.docker_sandbox import DAEMON_ERROR_PATTERNS
                    is_daemon_error = rc != 0 and any(pat in err.lower() for pat in DAEMON_ERROR_PATTERNS)
                    if not (is_daemon_error and self.allow_local_fallback):
                        mode='docker'
                        executed_docker = True
                except subprocess.TimeoutExpired as e:
                    rc,out,err,timed=-1,(e.stdout or '')[-10000:],(e.stderr or '')[-10000:],True
                    mode='docker'
                    executed_docker = True
            if not executed_docker:
                if not self.allow_local_fallback: raise RuntimeError('Docker unavailable and local fallback disabled')
                rc,out,err,timed,dur=self._local(root,command)
                mode='local-fallback'
            return RepositoryRunResult(rc==0,rc,out,err,time.perf_counter()-start,timed,mode,changed,self.fingerprint(root),tuple(command))
