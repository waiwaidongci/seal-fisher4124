import os,time,json,logging
from pathlib import Path
from redis import Redis
from sqlalchemy import select
from src.config.database import Session
from src.config.leak_domain import LEAK_DOMAIN
from src.models.run import Run
from src.models.leak_job import LeakJob
from src.models import user,study,observation,review,audit
from src.models import leak_roll,leak_specimen,leak_round,leak_job
from src.services.algorithm import calculate
from src.services import leak_execution
from src.utils.serializers import checksum
redis=Redis.from_url(os.environ['REDIS_URL'])
LEAK_QUEUE=LEAK_DOMAIN['queue']
Path(os.environ.get('ARTIFACTS_DIR','/app/artifacts')).mkdir(exist_ok=True)
# Recover jobs interrupted after dequeue. A project runs exactly one worker.
# 持久队列里可能残留同一任务 ID，恢复时去重后再补投，避免重复处理。
def _recover(queue_name, ids):
    existing = {int(x) for x in redis.lrange(queue_name, 0, -1)}
    for ident in ids:
        if ident not in existing:
            redis.rpush(queue_name, ident)

with Session() as db:
    pending=list(db.scalars(select(Run).where(Run.status.in_(['queued','running']))))
    _recover('analysis-queue', [r.id for r in pending])
    pending_leak=list(db.scalars(select(LeakJob).where(LeakJob.status.in_(['queued','running']))))
    _recover(LEAK_QUEUE, [j.id for j in pending_leak])
# 两条队列公平轮流取活：每轮先试非阻塞 LPOP，再阻塞等待，避免 BLPOP 多键时一条队列饥饿
while True:
    Path('/tmp/worker-heartbeat').touch()
    item=None
    for qname in (LEAK_QUEUE,'analysis-queue'):
        raw=redis.lpop(qname)
        if raw is not None:
            item=(qname,raw);break
    if item is None:
        waited=redis.blpop([LEAK_QUEUE,'analysis-queue'],timeout=2)
        if waited: item=(waited[0].decode() if isinstance(waited[0],bytes) else waited[0],waited[1])
    if not item: continue
    queue_name,raw=item
    ident=int(raw)
    if queue_name==LEAK_QUEUE:
        with Session() as db:
            leak_execution.execute(db,ident)
        continue
    id=ident
    with Session() as db:
        run=db.get(Run,id)
        if not run or run.status in ('completed','failed'): continue
        run.status='running';db.commit()
        try:
            if checksum(run.snapshot)!=run.checksum: raise ValueError('输入快照校验失败')
            result=calculate(run.snapshot,run.parameters)
            result['input_sha256']=run.checksum
            run.result=result;run.status='completed'
            Path(f"{os.environ.get('ARTIFACTS_DIR','/app/artifacts')}/run-{id}.json").write_text(json.dumps(result,ensure_ascii=False,allow_nan=False))
        except Exception as e:
            logging.exception('analysis failed');run.status='failed';run.error=str(e)
        db.commit()
