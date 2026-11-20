from sqlalchemy import Column, Integer, String, Boolean
from src.config.database import Base


class MaterialRoll(Base):
    # 一卷材料：规划期可被多个研究轮软分配；revealed_by 非空表示已被某轮揭晓硬占用，
    # 此后不得再进入任何轮的盲验组。
    __tablename__ = 'leak_rolls'
    id = Column(Integer, primary_key=True)
    roll_code = Column(String(100), unique=True, nullable=False)
    material = Column(String(120), nullable=False, default='')
    note = Column(String(500), nullable=False, default='')
    occupied = Column(Boolean, nullable=False, default=False)
    revealed_by = Column(Integer, nullable=True)
