.PHONY: test clean check-release build smoke

test:
	PYTHONDONTWRITEBYTECODE=1 python -m pytest -q

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type f \( -name '*.pyc' -o -name '*.tmp' \) -delete

check-release: clean
	@rm -rf runs .pytest_cache
	@python -c 'import pathlib,tomllib; root=pathlib.Path("."); version=tomllib.loads((root/"pyproject.toml").read_text())["project"]["version"]; assert version=="3.3.1"; assert (root/"dream_rsi"/"__init__.py").read_text().strip()=="__version__ = \"3.3.1\""; files=[p for p in root.rglob("*") if p.is_file() and p.suffix in {".py",".toml",".yaml",".yml",".md",".env",".example"}]; assert not any(any(v in p.read_text(encoding="utf-8",errors="ignore") for v in ("1.1.0","2.7.0","3.3.0","0.7.0")) for p in files); assert not (root/"runs").exists(); assert not list(root.rglob("*.pyc")); assert not list(root.rglob("*.tmp")); print("release check: OK",version)'

build: clean
	python -m build

smoke:
	PYTHONDONTWRITEBYTECODE=1 python -m dream_rsi.cli.run_demo
	PYTHONDONTWRITEBYTECODE=1 python -m dream_rsi.cli.autonomous --help >/dev/null
	PYTHONDONTWRITEBYTECODE=1 python -m dream_rsi.cli.research_matrix --help >/dev/null
