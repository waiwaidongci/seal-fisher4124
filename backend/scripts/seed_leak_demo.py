"""漏封仪业务演示数据：3 校准卷 + 2 盲验卷，两个研究轮（含一轮共用软分配示例）。

自然键插入、重复不覆盖；固定 numpy 种子 42，保证可复现。
"""
import json
import numpy as np
from sqlalchemy import select, func
from src.config.database import Base, engine, Session
from src.models.user import User
from src.models.leak_roll import MaterialRoll
from src.models.leak_specimen import LeakSpecimen
from src.models.leak_round import CalibrationRound
from src.schemas.leak_roll import RollInput
from src.schemas.leak_specimen import SpecimenInput
from src.schemas.leak_round import RoundInput
from src.services import leak_rolls, leak_rounds
from src.utils.security import hash_password

TRUE_CUTOFF = 3.2
RNG = np.random.default_rng(42)


class _SeedUser:
    email = 'seed@demo.local'
    role = 'admin'


def _specimens(n):
    out = []
    for i in range(n):
        is_leak = RNG.random() < 0.42
        if is_leak:
            reading = float(np.clip(RNG.normal(TRUE_CUTOFF + 0.9, 0.55), 0, None))
        else:
            reading = float(np.clip(RNG.normal(TRUE_CUTOFF - 1.1, 0.5), 0, None))
        out.append(SpecimenInput(
            specimen_key=f'S-{i + 1:03}',
            reading=round(reading, 3),
            rejudgement='leak' if is_leak else 'sealed',
        ))
    return out


def seed_leak():
    Base.metadata.create_all(engine)
    with Session() as db:
        if not db.scalar(select(User).where(User.email == 'admin@demo.local')):
            db.add(User(email='admin@demo.local', role='admin',
                        password_hash=hash_password('Research2026!')))
            db.commit()

        roll_ids = {}
        plan = [
            ('CAL-A', '校准卷 A（薄膜）', 20),
            ('CAL-B', '校准卷 B（覆膜）', 20),
            ('CAL-C', '校准卷 C（复合膜）', 20),
            ('BLIND-X', '盲验卷 X', 15),
            ('BLIND-Y', '盲验卷 Y（共用软分配示例）', 15),
        ]
        for code, material, n in plan:
            existing = db.scalar(select(MaterialRoll).where(MaterialRoll.roll_code == code))
            if existing:
                roll_ids[code] = existing.id
                continue
            roll = leak_rolls.create_roll(
                db, RollInput(roll_code=code, material=material,
                              note='独立合成观测 / 固定种子42 / 真实分界约 3.2'), _SeedUser())
            for spec in _specimens(n):
                leak_rolls.save_specimen(db, roll['id'], spec, _SeedUser())
            roll_ids[code] = roll['id']

        rounds = [
            ('砚田·漏封校准一轮', ['CAL-A', 'CAL-B'], ['BLIND-X']),
            ('砚田·漏封校准二轮（共用 BLIND-Y 规划）', ['CAL-C'], ['BLIND-Y']),
        ]
        for name, cal_codes, blind_codes in rounds:
            if not db.scalar(select(CalibrationRound).where(CalibrationRound.name == name)):
                leak_rounds.create_round(db, RoundInput(
                    name=name,
                    note='整卷软分配；并发揭晓时共用卷只允许一轮生效',
                    calibration_roll_ids=[roll_ids[c] for c in cal_codes],
                    blind_roll_ids=[roll_ids[c] for c in blind_codes],
                ), _SeedUser())
        counts = {
            'leak_rolls': db.scalar(select(func.count()).select_from(MaterialRoll)),
            'leak_specimens': db.scalar(select(func.count()).select_from(LeakSpecimen)),
            'leak_rounds': db.scalar(select(func.count()).select_from(CalibrationRound)),
        }
        print(json.dumps(counts, ensure_ascii=False))
        return counts


if __name__ == '__main__':
    seed_leak()
