"""漏封仪任务执行器：被 worker 调用，也可在测试中直接调用。

揭晓的“整批用卷 + 盲验误判数”在单个数据库事务内一起生效；
中断后重跑同一任务得到同一结果，重试不会重复占卷。
"""
import logging
from sqlalchemy import select
from src.models.leak_roll import MaterialRoll
from src.models.leak_specimen import LeakSpecimen
from src.models.leak_round import CalibrationRound
from src.models.leak_job import LeakJob
from src.services import leak_algorithm
from src.utils.serializers import now


def _specimens(db, roll_ids):
    rows = []
    for rid in roll_ids:
        for s in db.scalars(select(LeakSpecimen).where(LeakSpecimen.roll_id == rid).order_by(LeakSpecimen.id)):
            rows.append({
                'specimen_key': s.specimen_key,
                'reading': s.reading,
                'rejudgement': s.rejudgement,
                'roll_id': rid,
            })
    return rows


def _run_calibration(db, job):
    rnd = db.get(CalibrationRound, job.round_id)
    roll_ids = job.snapshot['calibration_roll_ids']
    missing = [rid for rid in roll_ids if not db.get(MaterialRoll, rid)]
    if missing:
        raise ValueError(f'校准卷已不存在：{missing}')
    specimens = _specimens(db, roll_ids)
    # 校准失败不触碰任何盲验卷；仅记录拒绝原因
    cutoff, misjudgements, table = leak_algorithm.choose_cutoff(specimens)
    rnd.cutoff = cutoff
    rnd.status = 'calibrated'
    rnd.reject_reason = ''
    rnd.updated_at = now()
    job.result = {
        'cutoff': cutoff,
        'calibration_misjudgements': misjudgements,
        'candidate_table': table,
        'roll_ids': roll_ids,
        'specimen_count': len(specimens),
    }


def _run_reveal(db, job):
    rnd = db.get(CalibrationRound, job.round_id)
    blind_ids = job.snapshot['blind_roll_ids']
    # 行锁串行化并发揭晓：共用卷只允许一轮在本事务内占用
    locked = list(db.scalars(
        select(MaterialRoll).where(MaterialRoll.id.in_(blind_ids)).order_by(MaterialRoll.id).with_for_update()
    ))
    if len(locked) != len(set(blind_ids)):
        raise ValueError('部分盲验卷已不存在，揭晓中止，未占用任何卷')
    conflicts = [r.roll_code for r in locked if r.occupied or r.revealed_by is not None]
    if conflicts:
        raise ValueError(
            '盲验卷已被其他研究轮揭晓占用：' + '、'.join(conflicts) + '；本轮未占用任何卷，落选轮未用过的卷可另用'
        )
    specimens = _specimens(db, blind_ids)
    total, details = leak_algorithm.blind_review(specimens, rnd.cutoff)
    # 整批用卷与盲验误判数在同一事务内一起生效
    for roll in locked:
        roll.occupied = True
        roll.revealed_by = rnd.id
    rnd.status = 'revealed'
    rnd.blind_misjudgements = total
    rnd.reject_reason = ''
    rnd.updated_at = now()
    job.result = {
        'cutoff': rnd.cutoff,
        'blind_misjudgements': total,
        'roll_ids': blind_ids,
        'specimen_count': len(specimens),
        'details': details,
    }


_HANDLERS = {'calibration': _run_calibration, 'reveal': _run_reveal}


def execute(db, job_id):
    """执行单个任务。返回更新后的任务记录；终态任务幂等跳过。"""
    job = db.get(LeakJob, job_id)
    if not job:
        logging.warning('leak job %s missing', job_id)
        return None
    if job.status in ('completed', 'failed'):
        return job
    job.status = 'running'
    job.updated_at = now()
    db.commit()
    try:
        _HANDLERS[job.kind](db, job)
        job.status = 'completed'
        job.error = ''
        job.updated_at = now()
        db.commit()
    except Exception as exc:
        logging.exception('leak job %s failed', job_id)
        db.rollback()
        job = db.get(LeakJob, job_id)
        rnd = db.get(CalibrationRound, job.round_id)
        job.status = 'failed'
        job.error = str(exc)
        job.updated_at = now()
        # 校准失败不占盲验卷；揭晓失败说明一卷未占，轮回到 rejected 并保留原因
        if rnd.status != 'revealed':
            rnd.status = 'rejected'
            rnd.reject_reason = str(exc)
            rnd.updated_at = now()
        db.commit()
    return db.get(LeakJob, job_id)
