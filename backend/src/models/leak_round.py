from sqlalchemy import Column, Integer, String, Float, JSON, Text
from src.config.database import Base


class CalibrationRound(Base):
    # 一轮校准/盲验研究。整卷划入：calibration_roll_ids 与 blind_roll_ids 是规划期软分配，
    # 可与其他轮重叠；揭晓成功后状态转 revealed，所占用的盲验卷在 leak_rolls 上硬标记。
    __tablename__ = 'leak_rounds'
    id = Column(Integer, primary_key=True)
    name = Column(String(120), unique=True, nullable=False)
    note = Column(Text, nullable=False, default='')
    # draft 草稿 / calibrated 分界已冻结 / revealed 盲验已揭晓 / rejected 最近一次任务被拒
    status = Column(String(20), nullable=False, default='draft')
    calibration_roll_ids = Column(JSON, nullable=False, default=list)
    blind_roll_ids = Column(JSON, nullable=False, default=list)
    cutoff = Column(Float, nullable=True)
    blind_misjudgements = Column(Integer, nullable=True)
    reject_reason = Column(Text, nullable=False, default='')
    created_at = Column(String(40), nullable=False)
    updated_at = Column(String(40), nullable=False)
