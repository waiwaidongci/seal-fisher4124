import os
from fastapi import HTTPException
from redis import Redis
from sqlalchemy import select
from src.config.leak_domain import LEAK_DOMAIN
from src.models.leak_job import LeakJob
from src.services import leak_rounds
from src.services.audits import log
from src.utils.serializers import record, now


def _snapshot(rnd):
    return {
        'calibration_roll_ids': list(rnd.calibration_roll_ids or []),
        'blind_roll_ids': list(rnd.blind_roll_ids or []),
    }


def _enqueue(db, rnd, kind, user):
    if leak_rounds._open_job(db, rnd.id):
        raise HTTPException(409, '该轮已有进行中的任务，请勿重复提交')
    job = LeakJob(
        round_id=rnd.id, kind=kind, status='queued',
        snapshot=_snapshot(rnd), result=None, error='',
        created_at=now(), updated_at=now(),
    )
    db.add(job)
    rnd.updated_at = now()
    db.flush()
    log(db, user, f'leak.job.{kind}.queue', f'round={rnd.id} job={job.id}')
    db.commit()
    Redis.from_url(os.environ['REDIS_URL']).rpush(LEAK_DOMAIN['queue'], job.id)
    return record(job)


def enqueue_calibration(db, round_id, user):
    rnd = leak_rounds.require_round(db, round_id)
    if rnd.status not in ('draft', 'rejected'):
        raise HTTPException(409, '该轮分界已冻结，无需再次校准')
    if not rnd.calibration_roll_ids:
        raise HTTPException(422, '校准组为空，无法校准')
    return _enqueue(db, rnd, 'calibration', user)


def enqueue_reveal(db, round_id, user):
    rnd = leak_rounds.require_round(db, round_id)
    if rnd.status == 'revealed':
        raise HTTPException(409, '该轮已揭晓，揭晓仅生效一次')
    if rnd.cutoff is None or rnd.status not in ('calibrated', 'rejected'):
        raise HTTPException(409, '分界尚未冻结，请先完成校准')
    if not rnd.blind_roll_ids:
        raise HTTPException(422, '盲验组为空，无法揭晓')
    return _enqueue(db, rnd, 'reveal', user)


def list_jobs(db):
    return [record(x) for x in db.scalars(select(LeakJob).order_by(LeakJob.id.desc()))]


def get_job(db, job_id):
    job = db.get(LeakJob, job_id)
    if not job:
        raise HTTPException(404, '任务不存在')
    return record(job)
