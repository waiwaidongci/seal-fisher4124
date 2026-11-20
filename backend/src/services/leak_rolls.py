import math
from fastapi import HTTPException
from sqlalchemy import select, func
from src.models.leak_roll import MaterialRoll
from src.models.leak_specimen import LeakSpecimen
from src.models.leak_round import CalibrationRound
from src.services.audits import log
from src.utils.serializers import record


def _roll_locked(db, roll):
    if roll.occupied:
        return True
    # 分界已冻结（calibrated/revealed）的轮所涉卷，试件输入整体冻结
    for rnd in db.scalars(select(CalibrationRound).where(
            CalibrationRound.status.in_(('calibrated', 'revealed')))):
        if roll.id in (rnd.calibration_roll_ids or []) or roll.id in (rnd.blind_roll_ids or []):
            return True
    return False


def list_rolls(db):
    out = []
    for roll in db.scalars(select(MaterialRoll).order_by(MaterialRoll.id)):
        x = record(roll)
        x['specimen_count'] = db.scalar(
            select(func.count()).select_from(LeakSpecimen).where(LeakSpecimen.roll_id == roll.id)
        )
        out.append(x)
    return out


def require_roll(db, roll_id):
    roll = db.get(MaterialRoll, roll_id)
    if not roll:
        raise HTTPException(404, '卷材卷不存在')
    return roll


def create_roll(db, data, user):
    if db.scalar(select(MaterialRoll).where(MaterialRoll.roll_code == data.roll_code)):
        raise HTTPException(409, '卷材卷编号已存在')
    roll = MaterialRoll(
        roll_code=data.roll_code, material=data.material, note=data.note,
        occupied=False, revealed_by=None,
    )
    db.add(roll)
    log(db, user, 'leak.roll.create', data.roll_code)
    db.commit()
    return record(roll)


def list_specimens(db, roll_id, blind_masked):
    require_roll(db, roll_id)
    rows = [record(x) for x in db.scalars(
        select(LeakSpecimen).where(LeakSpecimen.roll_id == roll_id).order_by(LeakSpecimen.id)
    )]
    if blind_masked:
        # 分界冻结前：盲验复判只可录入，不可查看
        for r in rows:
            r['rejudgement'] = '*** 封存中（揭晓后可见） ***' if r['rejudgement'] is not None else None
    return rows


def save_specimen(db, roll_id, data, user, specimen_id=None):
    roll = require_roll(db, roll_id)
    if _roll_locked(db, roll):
        raise HTTPException(409, '该卷已随分界冻结或揭晓，试件记录不可再改')
    if not math.isfinite(data.reading):
        raise HTTPException(422, '实测读数必须是有限数值')
    other = db.scalar(select(LeakSpecimen).where(
        LeakSpecimen.roll_id == roll_id, LeakSpecimen.specimen_key == data.specimen_key
    ))
    if other and other.id != specimen_id:
        raise HTTPException(409, '卷内试件编号重复')
    if specimen_id:
        obj = db.get(LeakSpecimen, specimen_id)
        if not obj or obj.roll_id != roll_id:
            raise HTTPException(404, '试件不存在')
        obj.specimen_key = data.specimen_key
        obj.reading = float(data.reading)
        # 封存中的盲验复判不可查看：空值更新不得抹掉已录入复判；要改判须显式传新值
        if data.rejudgement is None:
            from src.services import leak_rounds
            if not leak_rounds.roll_pending_blind(db, roll_id):
                obj.rejudgement = None
        else:
            obj.rejudgement = data.rejudgement
    else:
        count = db.scalar(select(func.count()).select_from(LeakSpecimen).where(
            LeakSpecimen.roll_id == roll_id))
        if count >= 10000:
            raise HTTPException(422, '单卷最多登记10000个试件')
        obj = LeakSpecimen(
            roll_id=roll_id, specimen_key=data.specimen_key,
            reading=float(data.reading), rejudgement=data.rejudgement,
        )
        db.add(obj)
    log(db, user, 'leak.specimen.save', f'{roll.roll_code}/{data.specimen_key}')
    db.commit()
    return record(obj)


def remove_specimen(db, roll_id, specimen_id, user):
    roll = require_roll(db, roll_id)
    if _roll_locked(db, roll):
        raise HTTPException(409, '该卷已随分界冻结或揭晓，试件记录冻结')
    obj = db.get(LeakSpecimen, specimen_id)
    if not obj or obj.roll_id != roll_id:
        raise HTTPException(404, '试件不存在')
    db.delete(obj)
    log(db, user, 'leak.specimen.delete', f'{roll.roll_code}/{specimen_id}')
    db.commit()
    return {'deleted': True}
