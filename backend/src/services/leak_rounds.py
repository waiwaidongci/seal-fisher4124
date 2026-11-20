from fastapi import HTTPException
from sqlalchemy import select
from src.models.leak_roll import MaterialRoll
from src.models.leak_round import CalibrationRound
from src.models.leak_job import LeakJob
from src.models.leak_specimen import LeakSpecimen
from src.services.audits import log
from src.services import leak_rolls
from src.utils.serializers import record, now

EDITABLE_STATES = ('draft', 'rejected')
OPEN_JOB_STATES = ('queued', 'running')


def _validate_assignment(db, calibration_ids, blind_ids):
    if len(set(calibration_ids)) != len(calibration_ids):
        raise HTTPException(422, '校准组内卷号重复')
    if len(set(blind_ids)) != len(blind_ids):
        raise HTTPException(422, '盲验组内卷号重复')
    overlap = set(calibration_ids) & set(blind_ids)
    if overlap:
        raise HTTPException(422, '同一卷不能同时划入校准组与盲验组')
    for rid in calibration_ids + blind_ids:
        if not db.get(MaterialRoll, rid):
            raise HTTPException(422, f'卷材卷 {rid} 不存在')
    for rid in blind_ids:
        roll = db.get(MaterialRoll, rid)
        # 已揭晓卷不得再盲验（硬占用只在揭晓成功时产生）
        if roll.occupied or roll.revealed_by is not None:
            raise HTTPException(422, f'卷 {roll.roll_code} 已揭晓，不得再用于盲验')


def _open_job(db, round_id):
    return db.scalar(select(LeakJob).where(
        LeakJob.round_id == round_id, LeakJob.status.in_(OPEN_JOB_STATES)
    ))


def list_rounds(db):
    return [record(x) for x in db.scalars(select(CalibrationRound).order_by(CalibrationRound.id.desc()))]


def require_round(db, round_id):
    rnd = db.get(CalibrationRound, round_id)
    if not rnd:
        raise HTTPException(404, '研究轮不存在')
    return rnd


def create_round(db, data, user):
    if db.scalar(select(CalibrationRound).where(CalibrationRound.name == data.name)):
        raise HTTPException(409, '研究轮名称已存在')
    _validate_assignment(db, data.calibration_roll_ids, data.blind_roll_ids)
    if not data.calibration_roll_ids:
        raise HTTPException(422, '至少划入一卷校准卷')
    ts = now()
    rnd = CalibrationRound(
        name=data.name, note=data.note, status='draft',
        calibration_roll_ids=list(data.calibration_roll_ids),
        blind_roll_ids=list(data.blind_roll_ids),
        created_at=ts, updated_at=ts,
    )
    db.add(rnd)
    log(db, user, 'leak.round.create', data.name)
    db.commit()
    return record(rnd)


def update_assignment(db, round_id, data, user):
    rnd = require_round(db, round_id)
    if rnd.status not in EDITABLE_STATES:
        raise HTTPException(409, '分界已冻结或已揭晓，整卷分配不可修改')
    if _open_job(db, round_id):
        raise HTTPException(409, '该轮尚有未完成任务，请等任务结束后再调整')
    _validate_assignment(db, data.calibration_roll_ids, data.blind_roll_ids)
    if not data.calibration_roll_ids:
        raise HTTPException(422, '至少保留一卷校准卷')
    rnd.calibration_roll_ids = list(data.calibration_roll_ids)
    rnd.blind_roll_ids = list(data.blind_roll_ids)
    rnd.updated_at = now()
    log(db, user, 'leak.round.assign', f'{round_id}: 校准{len(rnd.calibration_roll_ids)}卷/盲验{len(rnd.blind_roll_ids)}卷')
    db.commit()
    return record(rnd)


def get_detail(db, round_id):
    rnd = require_round(db, round_id)
    out = record(rnd)
    # 揭晓前盲验组复判封存；校准组始终可见
    blind_masked = rnd.status != 'revealed'

    def roll_bundle(roll_id, masked):
        roll = leak_rolls.require_roll(db, roll_id)
        bundle = record(roll)
        bundle['specimens'] = leak_rolls.list_specimens(db, roll_id, masked)
        return bundle

    out['calibration_rolls'] = [roll_bundle(rid, False) for rid in rnd.calibration_roll_ids]
    out['blind_rolls'] = [roll_bundle(rid, blind_masked) for rid in rnd.blind_roll_ids]
    out['jobs'] = [record(x) for x in db.scalars(
        select(LeakJob).where(LeakJob.round_id == round_id).order_by(LeakJob.id.desc())
    )]
    return out


def roll_pending_blind(db, roll_id):
    """该卷是否处于任何未揭晓轮的盲验组（用于卷页试件回显封存）。"""
    for rnd in db.scalars(select(CalibrationRound).where(CalibrationRound.status != 'revealed')):
        if roll_id in (rnd.blind_roll_ids or []):
            return True
    return False
