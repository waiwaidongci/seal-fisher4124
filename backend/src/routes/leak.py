from fastapi import APIRouter, Depends
from sqlalchemy import select
from src.config.database import get_db
from src.config.leak_domain import LEAK_DOMAIN
from src.middlewares.auth import current_user, writer
from src.schemas.leak_roll import RollInput
from src.schemas.leak_specimen import SpecimenInput
from src.schemas.leak_round import RoundInput
from src.schemas.leak_assignment import RoundRollsInput
from src.models.audit import Audit
from src.services import leak_rolls, leak_rounds, leak_jobs
from src.utils.serializers import record

router = APIRouter(prefix='/leak')


@router.get('/domain')
def domain(user=Depends(current_user)):
    return LEAK_DOMAIN


@router.get('/overview')
def overview(db=Depends(get_db), user=Depends(current_user)):
    from src.controllers.leak import overview as build_overview
    return build_overview(db)


@router.get('/rolls')
def rolls(db=Depends(get_db), user=Depends(current_user)):
    return leak_rolls.list_rolls(db)


@router.post('/rolls')
def create_roll(data: RollInput, db=Depends(get_db), user=Depends(writer)):
    return leak_rolls.create_roll(db, data, user)


@router.get('/rolls/{roll_id}/specimens')
def specimens(roll_id: int, db=Depends(get_db), user=Depends(current_user)):
    # 卷级列表：若该卷正处于未揭晓轮的盲验组，复判封存
    masked = leak_rounds.roll_pending_blind(db, roll_id)
    return leak_rolls.list_specimens(db, roll_id, masked)


@router.post('/rolls/{roll_id}/specimens')
def add_specimen(roll_id: int, data: SpecimenInput, db=Depends(get_db), user=Depends(writer)):
    return leak_rolls.save_specimen(db, roll_id, data, user)


@router.put('/rolls/{roll_id}/specimens/{specimen_id}')
def edit_specimen(roll_id: int, specimen_id: int, data: SpecimenInput,
                  db=Depends(get_db), user=Depends(writer)):
    return leak_rolls.save_specimen(db, roll_id, data, user, specimen_id)


@router.delete('/rolls/{roll_id}/specimens/{specimen_id}')
def delete_specimen(roll_id: int, specimen_id: int, db=Depends(get_db), user=Depends(writer)):
    return leak_rolls.remove_specimen(db, roll_id, specimen_id, user)


@router.get('/rounds')
def rounds(db=Depends(get_db), user=Depends(current_user)):
    return leak_rounds.list_rounds(db)


@router.post('/rounds')
def create_round(data: RoundInput, db=Depends(get_db), user=Depends(writer)):
    return leak_rounds.create_round(db, data, user)


@router.get('/rounds/{round_id}')
def round_detail(round_id: int, db=Depends(get_db), user=Depends(current_user)):
    return leak_rounds.get_detail(db, round_id)


@router.put('/rounds/{round_id}/rolls')
def assign_rolls(round_id: int, data: RoundRollsInput, db=Depends(get_db), user=Depends(writer)):
    return leak_rounds.update_assignment(db, round_id, data, user)


@router.post('/rounds/{round_id}/calibrate')
def calibrate(round_id: int, db=Depends(get_db), user=Depends(writer)):
    return leak_jobs.enqueue_calibration(db, round_id, user)


@router.post('/rounds/{round_id}/reveal')
def reveal(round_id: int, db=Depends(get_db), user=Depends(writer)):
    return leak_jobs.enqueue_reveal(db, round_id, user)


@router.get('/jobs')
def jobs(db=Depends(get_db), user=Depends(current_user)):
    return leak_jobs.list_jobs(db)


@router.get('/jobs/{job_id}')
def job(job_id: int, db=Depends(get_db), user=Depends(current_user)):
    return leak_jobs.get_job(db, job_id)


@router.get('/audits')
def leak_audits(db=Depends(get_db), user=Depends(current_user)):
    return [record(x) for x in db.scalars(
        select(Audit).where(Audit.action.like('leak.%')).order_by(Audit.id.desc()).limit(100)
    )]
