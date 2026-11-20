"""漏封仪校准/盲验全流程服务测试（SQLite，任务直接同步执行）。"""
import pytest
from fastapi import HTTPException
from src.models.leak_roll import MaterialRoll
from src.models.leak_round import CalibrationRound
from src.models.leak_job import LeakJob
from src.schemas.leak_roll import RollInput
from src.schemas.leak_specimen import SpecimenInput
from src.schemas.leak_round import RoundInput
from src.schemas.leak_assignment import RoundRollsInput
from src.services import leak_rolls, leak_rounds, leak_jobs, leak_execution


def make_roll(db, code):
    return leak_rolls.create_roll(db, RollInput(roll_code=code, material='薄膜'), _user())


def add_spec(db, roll_id, key, reading, rejudgement=None):
    leak_rolls.save_specimen(
        db, roll_id,
        SpecimenInput(specimen_key=key, reading=reading, rejudgement=rejudgement),
        _user(),
    )


class _user:
    email = 'analyst@demo.local'
    role = 'analyst'


def _calibration_data():
    # 分界 3.0 零误判的校准集
    return [
        ('c1', 1.0, 'sealed'), ('c2', 2.0, 'sealed'),
        ('c3', 3.0, 'leak'), ('c4', 4.0, 'leak'),
    ]


def _blind_data():
    return [
        ('b1', 1.5, 'sealed'),
        ('b2', 3.5, 'sealed'),   # 仪器判漏封、复判合格 -> 1 个误判
        ('b3', 4.5, 'leak'),
    ]


def _setup_round(db, cal_rolls=1, blind_rolls=1):
    cal_ids, blind_ids = [], []
    for i in range(cal_rolls):
        r = make_roll(db, f'CAL-{i}')
        cal_ids.append(r['id'])
        for k, reading, label in _calibration_data():
            add_spec(db, r['id'], f'{k}-{i}', reading + i * 0.1, label)
    for i in range(blind_rolls):
        r = make_roll(db, f'BLIND-{i}')
        blind_ids.append(r['id'])
        for k, reading, label in _blind_data():
            add_spec(db, r['id'], f'{k}-{i}', reading, label)
    rnd = leak_rounds.create_round(
        db,
        RoundInput(name=f'轮-{cal_rolls}-{blind_rolls}', calibration_roll_ids=cal_ids,
                   blind_roll_ids=blind_ids),
        _user(),
    )
    return rnd, cal_ids, blind_ids


def _drain(db, fake_redis):
    # 模拟 worker：把假队列里的任务全部同步执行
    while True:
        item = fake_redis.blpop(['leak-queue'], timeout=0)
        if not item:
            return
        job_id = int(item[1])
        leak_execution.execute(db, job_id)


def test_full_calibration_and_reveal_flow(db, fake_redis):
    rnd, cal_ids, blind_ids = _setup_round(db)
    job = leak_jobs.enqueue_calibration(db, rnd['id'], _user())
    assert job['status'] == 'queued'
    _drain(db, fake_redis)

    refreshed = leak_rounds.get_detail(db, rnd['id'])
    assert refreshed['status'] == 'calibrated'
    assert refreshed['cutoff'] == pytest.approx(3.1) or refreshed['cutoff'] == 3.0
    # 校准不占任何卷
    assert db.get(MaterialRoll, blind_ids[0]).occupied is False

    reveal_job = leak_jobs.enqueue_reveal(db, rnd['id'], _user())
    _drain(db, fake_redis)
    final = leak_rounds.get_detail(db, rnd['id'])
    assert final['status'] == 'revealed'
    assert final['blind_misjudgements'] == 1
    # 整批盲验卷一起硬占用
    for rid in blind_ids:
        roll = db.get(MaterialRoll, rid)
        assert roll.occupied is True and roll.revealed_by == rnd['id']
    # 校准卷不被盲验占用
    assert db.get(MaterialRoll, cal_ids[0]).occupied is False
    # 揭晓后盲验复判可见
    assert final['blind_rolls'][0]['specimens'][0]['rejudgement'] == 'sealed'


def test_blind_rejudgement_masked_before_freeze(db, fake_redis):
    rnd, _, blind_ids = _setup_round(db)
    detail = leak_rounds.get_detail(db, rnd['id'])
    masked = detail['blind_rolls'][0]['specimens']
    assert all('封存' in (s['rejudgement'] or '') for s in masked)
    # 卷级列表同样封存
    rows = leak_rolls.list_specimens(db, blind_ids[0], leak_rounds.roll_pending_blind(db, blind_ids[0]))
    assert all('封存' in (s['rejudgement'] or '') for s in rows)
    # 校准组不封存
    assert detail['calibration_rolls'][0]['specimens'][0]['rejudgement'] == 'sealed'


def test_calibration_failure_does_not_consume_blind_rolls(db, fake_redis):
    # 校准卷试件缺复判 -> 校准失败
    r = make_roll(db, 'CAL-BAD')
    add_spec(db, r['id'], 'x1', 1.0, None)
    blind = make_roll(db, 'BLIND-KEEP')
    add_spec(db, blind['id'], 'b1', 2.0, 'sealed')
    rnd = leak_rounds.create_round(
        db, RoundInput(name='失败轮', calibration_roll_ids=[r['id']], blind_roll_ids=[blind['id']]),
        _user(),
    )
    leak_jobs.enqueue_calibration(db, rnd['id'], _user())
    _drain(db, fake_redis)

    failed = leak_rounds.get_detail(db, rnd['id'])
    assert failed['status'] == 'rejected'
    assert failed['cutoff'] is None and failed['blind_misjudgements'] is None
    assert '复判必须完整' in failed['reject_reason']
    # 校准失败不占盲验卷，卷可另用
    blind_roll = db.get(MaterialRoll, blind['id'])
    assert blind_roll.occupied is False and blind_roll.revealed_by is None

    other = leak_rounds.create_round(
        db, RoundInput(name='另起一轮', calibration_roll_ids=[r['id']], blind_roll_ids=[blind['id']]),
        _user(),
    )
    assert other['blind_roll_ids'] == [blind['id']]


def test_revealed_roll_cannot_be_blind_again(db, fake_redis):
    rnd, cal_ids, blind_ids = _setup_round(db)
    leak_jobs.enqueue_calibration(db, rnd['id'], _user()); _drain(db, fake_redis)
    leak_jobs.enqueue_reveal(db, rnd['id'], _user()); _drain(db, fake_redis)

    fresh_cal = make_roll(db, 'CAL-NEW')
    for k, reading, label in _calibration_data():
        add_spec(db, fresh_cal['id'], k, reading, label)
    with pytest.raises(HTTPException) as exc:
        leak_rounds.create_round(
            db, RoundInput(name='复用揭晓卷', calibration_roll_ids=[fresh_cal['id']],
                           blind_roll_ids=blind_ids),
            _user(),
        )
    assert exc.value.status_code == 422 and '已揭晓' in exc.value.detail


def test_concurrent_reveal_only_one_wins_shared_rolls(db, fake_redis):
    # 两轮软分配共用同一盲验卷
    shared = make_roll(db, 'SHARED')
    for k, reading, label in _blind_data():
        add_spec(db, shared['id'], k, reading, label)
    cal_a = make_roll(db, 'CAL-A')
    for k, reading, label in _calibration_data():
        add_spec(db, cal_a['id'], k, reading, label)
    cal_b = make_roll(db, 'CAL-B')
    for k, reading, label in _calibration_data():
        add_spec(db, cal_b['id'], k, reading + 0.5, label)

    round_a = leak_rounds.create_round(
        db, RoundInput(name='A轮', calibration_roll_ids=[cal_a['id']], blind_roll_ids=[shared['id']]),
        _user())
    round_b = leak_rounds.create_round(
        db, RoundInput(name='B轮', calibration_roll_ids=[cal_b['id']], blind_roll_ids=[shared['id']]),
        _user())
    for rid in (round_a['id'], round_b['id']):
        leak_jobs.enqueue_calibration(db, rid, _user())
    _drain(db, fake_redis)
    job_a = leak_jobs.enqueue_reveal(db, round_a['id'], _user())
    job_b = leak_jobs.enqueue_reveal(db, round_b['id'], _user())

    # 先执行 A：成功占卷
    leak_execution.execute(db, job_a['id'])
    assert db.get(CalibrationRound, round_a['id']).status == 'revealed'
    # 再执行 B：整批失败，一卷未占（A 已占的保持不变）
    result_b = leak_execution.execute(db, job_b['id'])
    assert result_b.status == 'failed' and '已被其他研究轮揭晓占用' in result_b.error
    rb = db.get(CalibrationRound, round_b['id'])
    assert rb.status == 'rejected' and rb.blind_misjudgements is None
    assert db.get(MaterialRoll, shared['id']).revealed_by == round_a['id']

    # 落选轮未用过的卷（这里换一卷新盲验卷）可另用
    new_blind = make_roll(db, 'BLIND-RETRY')
    for k, reading, label in _blind_data():
        add_spec(db, new_blind['id'], k, reading, label)
    leak_rounds.update_assignment(
        db, round_b['id'],
        RoundRollsInput(calibration_roll_ids=[cal_b['id']], blind_roll_ids=[new_blind['id']]),
        _user(),
    )
    retry = leak_jobs.enqueue_reveal(db, round_b['id'], _user())
    leak_execution.execute(db, retry['id'])
    assert db.get(CalibrationRound, round_b['id']).status == 'revealed'
    assert db.get(MaterialRoll, new_blind['id']).occupied is True


def test_retry_completed_job_is_idempotent(db, fake_redis):
    rnd, _, blind_ids = _setup_round(db)
    leak_jobs.enqueue_calibration(db, rnd['id'], _user()); _drain(db, fake_redis)
    job = leak_jobs.enqueue_reveal(db, rnd['id'], _user())
    first = leak_execution.execute(db, job['id'])
    again = leak_execution.execute(db, job['id'])
    assert first.status == again.status == 'completed'
    assert db.get(LeakJob, job['id']).status == 'completed'
    # 没有重复占用/计数
    roll = db.get(MaterialRoll, blind_ids[0])
    assert roll.occupied is True
    assert db.get(CalibrationRound, rnd['id']).blind_misjudgements == 1


def test_duplicate_enqueue_blocked_and_reveal_requires_calibration(db, fake_redis):
    rnd, _, _ = _setup_round(db)
    leak_jobs.enqueue_calibration(db, rnd['id'], _user())
    with pytest.raises(HTTPException) as exc:
        leak_jobs.enqueue_calibration(db, rnd['id'], _user())
    assert exc.value.status_code == 409
    # 未校准不能揭晓
    fresh = leak_rounds.create_round(
        db, RoundInput(name='裸轮',
                       calibration_roll_ids=rnd['calibration_roll_ids'],
                       blind_roll_ids=rnd['blind_roll_ids']),
        _user())
    with pytest.raises(HTTPException) as exc:
        leak_jobs.enqueue_reveal(db, fresh['id'], _user())
    assert exc.value.status_code == 409


def test_assignment_locked_after_freeze_and_specimen_frozen(db, fake_redis):
    rnd, cal_ids, _ = _setup_round(db)
    leak_jobs.enqueue_calibration(db, rnd['id'], _user()); _drain(db, fake_redis)
    with pytest.raises(HTTPException) as exc:
        leak_rounds.update_assignment(
            db, rnd['id'],
            RoundRollsInput(calibration_roll_ids=cal_ids, blind_roll_ids=[]), _user())
    assert exc.value.status_code == 409
    with pytest.raises(HTTPException) as exc:
        add_spec(db, cal_ids[0], 'new', 9.9, 'leak')
    assert exc.value.status_code == 409


def test_roll_cannot_be_both_calibration_and_blind(db):
    r = make_roll(db, 'DUP')
    with pytest.raises(HTTPException) as exc:
        leak_rounds.create_round(
            db, RoundInput(name='重叠轮', calibration_roll_ids=[r['id']], blind_roll_ids=[r['id']]),
            _user())
    assert exc.value.status_code == 422


def test_masked_blind_rejudgement_not_wiped_by_blank_update(db, fake_redis):
    # 盲验封存卷：带 None 复判的更新不得抹掉已录入复判
    blind = make_roll(db, 'BLIND-MASK')
    add_spec(db, blind['id'], 'm1', 2.0, 'leak')
    cal = make_roll(db, 'CAL-FOR-MASK')
    for k, reading, label in _calibration_data():
        add_spec(db, cal['id'], k, reading, label)
    rnd = leak_rounds.create_round(
        db, RoundInput(name='封存保护轮', calibration_roll_ids=[cal['id']],
                       blind_roll_ids=[blind['id']]),
        _user())
    spec_id = leak_rolls.list_specimens(db, blind['id'], True)[0]['id']
    leak_rolls.save_specimen(
        db, blind['id'],
        SpecimenInput(specimen_key='m1', reading=2.5, rejudgement=None),
        _user(), specimen_id=spec_id)
    kept = leak_rolls.list_specimens(db, blind['id'], True)[0]
    assert '封存' in kept['rejudgement']  # 回显仍封存；底层值保留
    # 显式改判仍生效（写入新值）
    leak_rolls.save_specimen(
        db, blind['id'],
        SpecimenInput(specimen_key='m1', reading=2.5, rejudgement='sealed'),
        _user(), specimen_id=spec_id)
    assert leak_rolls.list_specimens(db, blind['id'], False)[0]['rejudgement'] == 'sealed'

    # 非盲验卷：空复判更新正常清空
    free = make_roll(db, 'FREE-ROLL')
    add_spec(db, free['id'], 'f1', 1.0, 'leak')
    fid = leak_rolls.list_specimens(db, free['id'], False)[0]['id']
    leak_rolls.save_specimen(
        db, free['id'], SpecimenInput(specimen_key='f1', reading=1.0, rejudgement=None),
        _user(), specimen_id=fid)
    assert leak_rolls.list_specimens(db, free['id'], False)[0]['rejudgement'] is None
