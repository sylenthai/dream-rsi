import os

def test_queue_and_worker_lifecycle(tmp_path):
    from dream_rsi.storage import RunStore
    from dream_rsi.service.queue import InMemoryJobQueue
    from dream_rsi.service.worker import ExperimentWorker
    from dream_rsi.service.experiments import ExperimentService
    store=RunStore(str(tmp_path/'runs.sqlite'))
    q=InMemoryJobQueue(); svc=ExperimentService(store, q)
    r=svc.submit('smoke', {'x':1}, 'abc')
    assert r.status == 'queued'
    worker=ExperimentWorker(store,q,{'smoke':lambda task,cfg:{'ok':True}})
    assert worker.process_once()
    out=svc.get(r.id)
    assert out.status == 'succeeded' and out.result == {'ok':True}
    assert svc.submit('smoke', {'x':2}, 'abc').id == r.id
    store.close()

def test_worker_retry_and_failure(tmp_path):
    from dream_rsi.storage import RunStore
    from dream_rsi.service.queue import InMemoryJobQueue
    from dream_rsi.service.worker import ExperimentWorker
    from dream_rsi.service.experiments import ExperimentService
    store=RunStore(str(tmp_path/'runs.sqlite')); q=InMemoryJobQueue(); svc=ExperimentService(store,q)
    r=svc.submit('boom', {})
    worker=ExperimentWorker(store,q,{'boom':lambda *_: (_ for _ in ()).throw(RuntimeError('x'))},max_attempts=2)
    worker.process_once(); assert svc.get(r.id).status == 'retrying'
    worker.process_once(); assert svc.get(r.id).status == 'failed'
    store.close()
