from sqlalchemy import Column, Integer, String, Float, ForeignKey, UniqueConstraint
from src.config.database import Base


class LeakSpecimen(Base):
    # 卷内试件：reading 为漏封仪实测读数；rejudgement 为人工复判（leak 漏封 / sealed 合格）。
    # 盲验卷在分界冻结前复判只可录入，接口层对回显做封存。
    __tablename__ = 'leak_specimens'
    __table_args__ = (UniqueConstraint('roll_id', 'specimen_key'),)
    id = Column(Integer, primary_key=True)
    roll_id = Column(Integer, ForeignKey('leak_rolls.id'), nullable=False)
    specimen_key = Column(String(100), nullable=False)
    reading = Column(Float, nullable=False)
    rejudgement = Column(String(20), nullable=True)
