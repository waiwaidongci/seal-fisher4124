"""测试夹具：SQLite 内存库 + 假 Redis，无需 MySQL/Redis 服务。"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')
os.environ.setdefault('REDIS_URL', 'redis://localhost:6399/0')
os.environ.setdefault('JWT_SECRET', 'test-secret')

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from src.config import database as db_config
from src.config.database import Base
from src.models import (  # noqa: F401
    user, study, observation, run, review, audit,
    leak_roll, leak_specimen, leak_round, leak_job,
)


class FakeRedis:
    def __init__(self):
        self.lists = {}

    def rpush(self, key, *values):
        self.lists.setdefault(key, []).extend(values)
        return len(self.lists[key])

    def blpop(self, keys, timeout=0):
        for key in keys:
            if self.lists.get(key):
                return key.encode(), str(self.lists[key].pop(0)).encode()
        return None

    def ping(self):
        return True


@pytest.fixture()
def db():
    # StaticPool 让所有会话共享同一条内存连接，请求会话与 worker 式会话可见同一份数据
    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    session = TestingSession()
    # 让被测代码里的 Session() / get_db 拿到同库会话
    db_config.Session = TestingSession
    db_config.engine = engine
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def fake_redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr('src.services.leak_jobs.Redis.from_url', lambda url: fake)
    return fake


class FakeUser:
    def __init__(self, email='analyst@demo.local', role='analyst'):
        self.email = email
        self.role = role


@pytest.fixture()
def writer_user():
    return FakeUser()


@pytest.fixture()
def admin_user():
    return FakeUser('admin@demo.local', 'admin')
