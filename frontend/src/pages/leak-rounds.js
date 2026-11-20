import {LEAK_DOMAIN, ROUND_STATE_LABELS} from '../constants/leak.js';
import {leakStore, loadLeak} from '../stores/leak.js';
import {leakApi} from '../api/leak.js';
import {table} from '../components/common/table.js';
import {bindForm} from '../hooks/forms.js';
import {esc, fmt} from '../utils/format.js';

export async function render() {
  await loadLeak();
  const writable = localStorage.getItem('research-role') !== 'viewer';
  const rollOptions = group => leakStore.rolls
    .filter(r => group === 'blind' ? !r.occupied : true)
    .map(r => `<label class="check"><input type="checkbox" name="${group}" value="${r.id}"> ${esc(r.roll_code)}${r.occupied ? '（已揭晓）' : ''}</label>`)
    .join('');
  return `<div class="eyebrow">L02 / CALIBRATION ROUNDS</div>
<h1>校准/盲验研究轮</h1>
<p class="lead">规划期一卷可软分到多个轮；揭晓时整批用卷与盲验误判数一起生效，共用卷只允许一轮占用。</p>
${writable ? `<details><summary>新增研究轮</summary>
<form id="round-form" class="worksheet">
  <label>研究轮名称<input name="name" required minlength="2"></label>
  <label>说明<input name="note"></label>
  <h3>校准组（整卷划入，至少一卷）</h3>
  <div class="check-grid">${rollOptions('calibration')}</div>
  <h3>盲验组（已揭晓卷不可选）</h3>
  <div class="check-grid">${rollOptions('blind')}</div>
  <button type="submit">保存研究轮（软分配）</button>
</form></details>` : ''}
<h2>研究轮列表 <small>点击名称查看详情、发起校准与揭晓</small></h2>
${table(['研究轮', '状态', '校准卷数', '盲验卷数', '选定分界', '盲验误判数', '拒绝原因'],
  leakStore.rounds.map(r => [
    {html: `<a href="#leak-round/${r.id}">${esc(r.name)}</a>`},
    {html: `<span class="status ${r.status === 'revealed' ? 'completed' : r.status === 'rejected' ? 'failed' : ''}">${esc(ROUND_STATE_LABELS[r.status] || r.status)}</span>`},
    (r.calibration_roll_ids || []).length,
    (r.blind_roll_ids || []).length,
    r.cutoff === null || r.cutoff === undefined ? '—' : fmt(r.cutoff),
    r.blind_misjudgements === null || r.blind_misjudgements === undefined ? '—' : fmt(r.blind_misjudgements),
    r.reject_reason ? esc(r.reject_reason) : '—',
  ]))}`;
}

export function bind(refresh) {
  bindForm('round-form', async (data, form) => {
    // 同名复选框必须用 getAll，Object.fromEntries 会把重复键压缩成最后一个值
    const fd = new FormData(form);
    const pick = name => fd.getAll(name).map(Number);
    await leakApi.createRound({
      name: data.name,
      note: data.note || '',
      calibration_roll_ids: pick('calibration'),
      blind_roll_ids: pick('blind'),
    });
    await loadLeak();
    refresh();
  });
}
