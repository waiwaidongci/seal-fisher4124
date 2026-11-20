"""HTTP 层测试：鉴权、盲验封存响应、角色限制、旧研究路由不受影响。"""
import pytest
from fastapi.testclient import TestClient
from src.config.database import get_db
from src.main import app
from src.models.user import User
from src.models.study import Study
from src.utils.security import hash_password


@pytest.fixture()
def client(db, monkeypatch):
    # 绕过限流中间件对 Redis 的依赖
    class _StubRedis:
        def incr(self, key):
            return 1

        def expire(self, key, ttl):
            return True

        def ping(self):
            return True

    monkeypatch.setattr('src.middlewares.rate_limit.redis', _StubRedis())
    monkeypatch.setattr('src.services.leak_jobs.Redis.from_url', lambda url: _StubRedis())
    app.dependency_overrides[get_db] = lambda: db
    for role in ('admin', 'analyst', 'viewer'):
        db.add(User(email=f'{role}@demo.local', role=role,
                    password_hash=hash_password('Research2026!')))
    db.commit()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _token(client, role):
    r = client.post('/auth/login', json={'email': f'{role}@demo.local', 'password': 'Research2026!'})
    assert r.status_code == 200
    return r.json()['token']


def _auth(token):
    return {'Authorization': f'Bearer {token}'}


def test_requires_auth(client):
    assert client.get('/leak/rolls').status_code == 401
    assert client.get('/leak/rounds').status_code == 401


def test_viewer_cannot_write(client):
    token = _token(client, 'viewer')
    r = client.post('/leak/rolls', json={'roll_code': 'R1'}, headers=_auth(token))
    assert r.status_code == 403


def test_full_http_flow_with_masking_and_reveal(client):
    # 直接用内存列表接住入队任务，稍后模拟 worker 同步执行
    queued = []
    import src.services.leak_jobs as jobs_mod
    jobs_mod.Redis.from_url = lambda url: type('Q', (), {
        'rpush': lambda self, k, v: queued.append(int(v))
    })()

    token = _token(client, 'analyst')
    h = _auth(token)
    # 卷 + 试件
    cal = client.post('/leak/rolls', json={'roll_code': 'CAL-1', 'material': '薄膜'}, headers=h).json()
    blind = client.post('/leak/rolls', json={'roll_code': 'BLIND-1'}, headers=h).json()
    for key, reading, label in [('c1', 1.0, 'sealed'), ('c2', 2.0, 'sealed'),
                                ('c3', 3.0, 'leak'), ('c4', 4.0, 'leak')]:
        assert client.post(f"/leak/rolls/{cal['id']}/specimens",
                           json={'specimen_key': key, 'reading': reading, 'rejudgement': label},
                           headers=h).status_code == 200
    for key, reading, label in [('b1', 1.5, 'sealed'), ('b2', 3.5, 'sealed'),
                                ('b3', 4.5, 'leak')]:
        client.post(f"/leak/rolls/{blind['id']}/specimens",
                    json={'specimen_key': key, 'reading': reading, 'rejudgement': label}, headers=h)

    rnd = client.post('/leak/rounds', json={
        'name': 'HTTP 全流程轮',
        'calibration_roll_ids': [cal['id']],
        'blind_roll_ids': [blind['id']],
    }, headers=h).json()

    # 揭晓前：盲验复判接口封存，读数仍可见
    detail = client.get(f"/leak/rounds/{rnd['id']}", headers=h).json()
    assert all('封存' in (s['rejudgement'] or '') for s in detail['blind_rolls'][0]['specimens'])
    assert detail['blind_rolls'][0]['specimens'][0]['reading'] == 1.5

    # 同步执行入队任务（模拟 worker）
    from src.services import leak_execution
    from src.config.database import Session
    client.post(f"/leak/rounds/{rnd['id']}/calibrate", headers=h)
    job_id = queued[-1]
    with Session() as work_db:
        leak_execution.execute(work_db, job_id)

    calibrated = client.get(f"/leak/rounds/{rnd['id']}", headers=h).json()
    assert calibrated['status'] == 'calibrated' and calibrated['cutoff'] == 3.0

    client.post(f"/leak/rounds/{rnd['id']}/reveal", headers=h)
    with Session() as work_db:
        leak_execution.execute(work_db, queued[-1])

    final = client.get(f"/leak/rounds/{rnd['id']}", headers=h).json()
    assert final['status'] == 'revealed'
    assert final['blind_misjudgements'] == 1
    # 揭晓后复判完整可见
    assert final['blind_rolls'][0]['specimens'][1]['rejudgement'] == 'sealed'
    # 页面所需字段齐备：选定分界、盲验误判数
    assert {'cutoff', 'blind_misjudgements', 'reject_reason'} <= set(final)


def test_rejected_round_exposes_reason(client):
    token = _token(client, 'analyst')
    h = _auth(token)
    queued = []
    import src.services.leak_jobs as jobs_mod
    jobs_mod.Redis.from_url = lambda url: type('Q', (), {
        'rpush': lambda self, k, v: queued.append(int(v))
    })()
    cal = client.post('/leak/rolls', json={'roll_code': 'CAL-BAD'}, headers=h).json()
    client.post(f"/leak/rolls/{cal['id']}/specimens",
                json={'specimen_key': 'x', 'reading': 1.0}, headers=h)  # 缺复判
    rnd = client.post('/leak/rounds', json={'name': '失败轮HTTP',
                                            'calibration_roll_ids': [cal['id']]}, headers=h).json()
    client.post(f"/leak/rounds/{rnd['id']}/calibrate", headers=h)
    from src.services import leak_execution
    from src.config.database import Session
    with Session() as work_db:
        leak_execution.execute(work_db, queued[-1])
    out = client.get(f"/leak/rounds/{rnd['id']}", headers=h).json()
    assert out['status'] == 'rejected' and '复判必须完整' in out['reject_reason']


def test_legacy_research_routes_still_serve(client):
    # 旧研究照常：域配置与既有路由不受新模块影响
    token = _token(client, 'admin')
    h = _auth(token)
    domain = client.get('/domain', headers=h)
    assert domain.status_code == 200 and domain.json()['slug'] == 'seal-fisher'
    assert client.get('/studies', headers=h).status_code == 200
    assert client.get('/runs', headers=h).status_code == 200
    # 新域独立
    leak_domain = client.get('/leak/domain', headers=h).json()
    assert leak_domain['slug'] == 'leak-threshold'
