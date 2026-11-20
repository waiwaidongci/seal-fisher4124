// 前端渲染冒烟测试：stub fetch / localStorage / document，验证四个漏封仪页面可渲染、封存与状态文案正确。
import test from 'node:test';
import assert from 'node:assert/strict';

const roundDetail = {
  id: 1, name: '一轮', note: '说明', status: 'draft',
  calibration_roll_ids: [1], blind_roll_ids: [2],
  cutoff: null, blind_misjudgements: null, reject_reason: '',
  calibration_rolls: [{id: 1, roll_code: 'CAL-1', material: '薄膜', occupied: false,
    specimens: [{specimen_key: 'C1', reading: 1.1, rejudgement: 'sealed'}]}],
  blind_rolls: [{id: 2, roll_code: 'BLIND-1', material: '薄膜', occupied: false,
    specimens: [{specimen_key: 'B1', reading: 4.2, rejudgement: '*** 封存中（揭晓后可见） ***'}]}],
  jobs: [],
};

const routes = {
  '/leak/overview': {
    rolls: [
      {id: 1, roll_code: 'CAL-1', material: '薄膜', occupied: false, specimen_count: 1},
      {id: 2, roll_code: 'BLIND-1', material: '薄膜', occupied: false, specimen_count: 1},
    ],
    rounds: [{id: 1, name: '一轮', status: 'draft', calibration_roll_ids: [1],
      blind_roll_ids: [2], cutoff: null, blind_misjudgements: null, reject_reason: ''}],
    jobs: [],
  },
  '/leak/rolls/1/specimens': [{id: 10, specimen_key: 'C1', reading: 1.1, rejudgement: 'sealed'}],
  '/leak/rounds/1': roundDetail,
  '/leak/audits': [],
};

globalThis.localStorage = {
  store: {'research-role': 'analyst'},
  getItem(k) { return this.store[k] ?? null; },
  setItem(k, v) { this.store[k] = v; },
  clear() { this.store = {}; },
};
globalThis.location = {hash: '#leak-rounds'};
globalThis.document = {
  getElementById: () => null,
  querySelectorAll: () => [],
};
globalThis.fetch = async (path) => {
  const key = path.replace('/api', '').split('?')[0];
  const body = routes[key];
  if (body === undefined) throw new Error('unmocked route ' + key);
  return {
    ok: true, status: 200,
    headers: {get: () => 'application/json'},
    json: async () => body,
    blob: async () => ({}),
  };
};

const {render: renderRolls} = await import('../src/pages/leak-rolls.js');
const {render: renderRounds} = await import('../src/pages/leak-rounds.js');
const {render: renderDetail} = await import('../src/pages/leak-round-detail.js');
const {render: renderJobs} = await import('../src/pages/leak-jobs.js');

test('卷材页渲染选中卷的试件读数', async () => {
  const html = await renderRolls();
  assert.match(html, /卷材卷与试件读数/);
  assert.match(html, /CAL-1/);
  assert.match(html, /1\.1/); // 选中 CAL-1 时展示其试件读数
});

test('研究轮列表显示状态与空分界占位', async () => {
  const html = await renderRounds();
  assert.match(html, /校准\/盲验研究轮/);
  assert.match(html, /草稿（未校准）/);
  assert.match(html, /软分配/);
});

test('研究轮详情：冻结前盲验复判封存、动作按钮就位', async () => {
  const html = await renderDetail('1');
  assert.match(html, /未冻结/);
  assert.match(html, /封存中/);
  assert.match(html, /校准并冻结分界/);
  assert.match(html, /揭晓盲验/);
});

test('研究轮详情：揭晓后显示选定分界、误判数与逐件结果', async () => {
  routes['/leak/rounds/1'] = {
    ...roundDetail, status: 'revealed', cutoff: 3.3, blind_misjudgements: 1,
    blind_rolls: [{id: 2, roll_code: 'BLIND-1', material: '薄膜', occupied: true,
      specimens: [{specimen_key: 'B1', reading: 4.2, rejudgement: 'sealed'}]}],
    jobs: [
      {id: 8, round_id: 1, kind: 'reveal', status: 'completed', error: '', updated_at: 't2',
        result: {cutoff: 3.3, blind_misjudgements: 1, roll_ids: [2], specimen_count: 1,
          details: [{specimen_key: 'B1', reading: 4.2, rejudgement: 'sealed', instrument: 'leak', misjudged: true}]}},
      {id: 7, round_id: 1, kind: 'calibration', status: 'completed', error: '', updated_at: 't1',
        result: {cutoff: 3.3, calibration_misjudgements: 0, specimen_count: 4,
          candidate_table: [{cutoff: 1.1, misjudgements: 2}, {cutoff: 3.3, misjudgements: 0}]}},
    ],
  };
  const html = await renderDetail('1');
  assert.match(html, /3\.3/);
  assert.match(html, /盲验已揭晓/);
  assert.match(html, /盲验逐件结果/);
  assert.match(html, /误判/);
  assert.match(html, /校准候选分界/); // 揭晓后校准候选表仍可见
  assert.match(html, /选定/);
});

test('拒绝原因在详情页可见', async () => {
  routes['/leak/rounds/1'] = {
    ...roundDetail, status: 'rejected',
    reject_reason: '盲验卷已被其他研究轮揭晓占用：BLIND-1；本轮未占用任何卷',
    jobs: [],
  };
  const html = await renderDetail('1');
  assert.match(html, /拒绝原因/);
  assert.match(html, /未占用任何卷/);
});

test('任务页渲染', async () => {
  const html = await renderJobs();
  assert.match(html, /任务队列与操作留痕/);
});
