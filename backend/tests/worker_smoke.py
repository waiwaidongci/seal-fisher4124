"""worker 双队列冒烟：伪 Redis 投递漏封任务与旧研究任务各一条，驱动真实 worker 循环验证分发。"""
import os
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['DATABASE_URL'] = 'sqlite:////tmp/worker-smoke.db'
os.environ['REDIS_URL'] = 'redis://stub:6379/0'
os.environ['JWT_SECRET'] = 'x'
os.environ['ARTIFACTS_DIR'] = '/tmp/artifacts-smoke'

Path('/tmp/worker-smoke.db').unlink(missing_ok=True)
Path('/tmp/artifacts-smoke').mkdir(exist_ok=True)


class FakeRedisClient:
    def __init__(self):
        self.q = {}
        self.pops = 0

    def rpush(self, key, *vals):
        self.q.setdefault(key, []).extend(vals)

    def lrange(self, key, start, end):
        return list(self.q.get(key, []))

    def _tick(self):
        self.pops += 1
        if self.pops > 2:
            raise SystemExit('stop after two jobs')

    def lpop(self, key):
        vals = self.q.get(key)
        if not vals:
            return None
        self._tick()
        return str(vals.pop(0)).encode()

    def blpop(self, keys, timeout=2):
        for k in keys:
            if self.q.get(k):
                self._tick()
                return k.encode(), str(self.q[k].pop(0)).encode()
        raise SystemExit('stop: queues drained')

    def ping(self):
        return True


client = FakeRedisClient()
fake_module = types.ModuleType('redis')
fake_module.Redis = types.SimpleNamespace(from_url=lambda url: client)
sys.modules['redis'] = fake_module

from src.config.database import Base, Session  # noqa: E402
from src.models import (  # noqa: E402
    user, study, observation, run, review, audit,
    leak_roll, leak_specimen, leak_round, leak_job,
)
from src.models.leak_roll import MaterialRoll  # noqa: E402
from src.models.leak_specimen import LeakSpecimen  # noqa: E402
from src.models.leak_round import CalibrationRound  # noqa: E402
from src.models.leak_job import LeakJob  # noqa: E402
from src.models.run import Run  # noqa: E402
from src.utils.serializers import now  # noqa: E402

Base.metadata.create_all(bind=__import__('src.config.database', fromlist=['engine']).engine)

with Session() as db:
    roll = MaterialRoll(roll_code='W1', material='m', occupied=False)
    db.add(roll); db.flush()
    for i, (reading, label) in enumerate([(1.0, 'sealed'), (2.0, 'sealed'),
                                          (3.0, 'leak'), (4.0, 'leak')]):
        db.add(LeakSpecimen(roll_id=roll.id, specimen_key=f'S{i}', reading=reading, rejudgement=label))
    rnd = CalibrationRound(name='worker轮', status='draft',
                           calibration_roll_ids=[roll.id], blind_roll_ids=[],
                           created_at=now(), updated_at=now())
    db.add(rnd); db.flush()
    lj = LeakJob(round_id=rnd.id, kind='calibration', status='queued',
                 snapshot={'calibration_roll_ids': [roll.id], 'blind_roll_ids': []},
                 created_at=now(), updated_at=now())
    db.add(lj)
    # 旧研究任务：空快照必然 failed，仅验证 worker 仍能分发到旧分支而不崩溃
    old = Run(study_id=1, name='old', status='queued', parameters={}, snapshot=[],
              checksum='x', created_at=now())
    db.add(old); db.flush()
    leak_job_id, old_run_id = lj.id, old.id
    db.commit()

client.rpush('leak-queue', leak_job_id)
client.rpush('analysis-queue', old_run_id)

try:
    import src.worker  # noqa: F401  导入即运行真实 while 循环
except SystemExit:
    pass

with Session() as db:
    job = db.get(LeakJob, leak_job_id)
    rnd = db.get(CalibrationRound, job.round_id)
    old = db.get(Run, old_run_id)
    assert job.status == 'completed', job.status
    assert rnd.status == 'calibrated' and rnd.cutoff == 3.0, (rnd.status, rnd.cutoff)
    assert old.status == 'failed' and old.error, old.status
    print('worker dual-queue OK: leak cutoff =', rnd.cutoff, '| legacy run ->', old.status)

Path('/tmp/worker-smoke.db').unlink(missing_ok=True)
