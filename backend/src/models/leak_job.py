from sqlalchemy import Column, Integer, String, JSON, Text, ForeignKey
from src.config.database import Base


class LeakJob(Base):
    # 异步任务（calibration 校准 / reveal 揭晓）。揭晓把“整批用卷 + 盲验误判数”在一个
    # 数据库事务里一起生效；worker 恢复只重排队 queued/running，已完成任务幂等跳过。
    __tablename__ = 'leak_jobs'
    id = Column(Integer, primary_key=True)
    round_id = Column(Integer, ForeignKey('leak_rounds.id'), nullable=False)
    kind = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default='queued')
    # 入队时冻结的软分配快照，执行时以该快照占卷，中断恢复得到同一结果
    snapshot = Column(JSON, nullable=False)
    result = Column(JSON, nullable=True)
    error = Column(Text, nullable=False, default='')
    created_at = Column(String(40), nullable=False)
    updated_at = Column(String(40), nullable=False)
