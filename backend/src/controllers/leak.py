"""漏封仪业务控制器：保持端点契约与持久化/计算逻辑分离。"""
from src.services import leak_rolls, leak_rounds, leak_jobs


def overview(db):
    return {
        'rolls': leak_rolls.list_rolls(db),
        'rounds': leak_rounds.list_rounds(db),
        'jobs': leak_jobs.list_jobs(db),
    }
