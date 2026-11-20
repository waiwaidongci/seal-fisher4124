import {LEAK_DOMAIN} from '../constants/leak.js';
import {leakStore, loadLeak} from '../stores/leak.js';
import {leakApi} from '../api/leak.js';
import {table} from '../components/common/table.js';
import {bindForm} from '../hooks/forms.js';
import {esc} from '../utils/format.js';

export async function render() {
  await loadLeak();
  const writable = localStorage.getItem('research-role') !== 'viewer';
  const roll = leakStore.rolls.find(r => r.id === leakStore.rollId) || leakStore.rolls[0];
  leakStore.rollId = roll?.id || 0;
  let specimens = [];
  if (roll) specimens = await leakApi.specimens(roll.id);
  const occupied = roll?.occupied;
  const maskedRow = s => typeof s.rejudgement === 'string' && s.rejudgement.includes('封存');
  return `<div class="eyebrow">L01 / ROLL REGISTER</div>
<h1>卷材卷与试件读数</h1>
<p class="lead">整卷划入校准或盲验。分界冻结前，盲验卷复判只可录入、不可查看；已揭晓卷试件冻结。</p>
<div class="method-note">${esc(LEAK_DOMAIN.note)}</div>
<div class="toolbar">
  <label style="min-width:320px">选择卷材卷
    <select id="roll-select">${leakStore.rolls.map(r =>
      `<option value="${r.id}" ${r.id === leakStore.rollId ? 'selected' : ''}>${esc(r.roll_code)} · ${esc(r.material || '未注明材料')}${r.occupied ? ' · 已揭晓占用' : ''}</option>`).join('')}
    </select>
  </label>
</div>
${writable ? `<details><summary>新增卷材卷</summary>
<form id="roll-form" class="inline-form">
  <label>卷材卷编号<input name="roll_code" placeholder="如 ROLL-202611-01" required></label>
  <label>材料/批次<input name="material" placeholder="如 薄膜 A 批"></label>
  <label>备注<input name="note"></label>
  <button type="submit">保存卷材卷</button>
</form></details>` : ''}
${roll ? `<h2>${esc(roll.roll_code)} <small>${esc(roll.material || '')} · ${specimens.length} 个试件${occupied ? ' · 已揭晓占用（只读）' : ''}</small></h2>
${writable && !occupied ? `<form id="specimen-form" class="inline-form">
  <label>试件编号<input name="specimen_key" placeholder="如 S-001" required></label>
  <label>漏封仪实测读数<input name="reading" type="number" step="any" required></label>
  <label>人工复判<select name="rejudgement"><option value="">暂不复判</option><option value="leak">漏封</option><option value="sealed">合格</option></select></label>
  <button type="submit">登记试件</button>
  <button type="button" id="cancel-edit" hidden>取消编辑</button>
</form><p class="method-note">若该卷在未揭晓轮的盲验组中，复判保存后列表只显示“封存中”，揭晓后才可见。</p>` : ''}
${table(['试件编号', '实测读数', '人工复判', ...(writable && !occupied ? ['操作'] : [])],
  specimens.map(s => [
    s.specimen_key, s.reading,
    s.rejudgement === null || s.rejudgement === undefined ? '—' : esc(s.rejudgement),
    ...(writable && !occupied ? [maskedRow(s)
      ? '封存中（揭晓前不可改）'
      : {html: `<button class="text" data-edit='${esc(JSON.stringify(s))}'>编辑</button> <button class="text" data-delete="${s.id}">移除</button>`}] : []),
  ]))}` : '<p class="method-note">尚无卷材卷。先新增一卷并登记试件。</p>'}`;
}

export function bind(refresh) {
  const sel = document.getElementById('roll-select');
  if (sel) sel.onchange = () => { leakStore.rollId = +sel.value; refresh(); };
  bindForm('roll-form', async data => {
    await leakApi.createRoll(data);
    await loadLeak();
    leakStore.rollId = leakStore.rolls[leakStore.rolls.length - 1].id;
    refresh();
  });
  let editing = null;
  bindForm('specimen-form', async data => {
    const payload = {
      specimen_key: data.specimen_key,
      reading: +data.reading,
      rejudgement: data.rejudgement || null,
    };
    await leakApi.saveSpecimen(leakStore.rollId, payload, editing);
    editing = null;
    refresh();
  });
  document.querySelectorAll('[data-edit]').forEach(el => el.onclick = () => {
    const s = JSON.parse(el.dataset.edit);
    editing = s.id;
    const form = document.getElementById('specimen-form');
    form.elements.specimen_key.value = s.specimen_key;
    form.elements.reading.value = s.reading;
    form.elements.rejudgement.value = (s.rejudgement || '').includes('封存') ? '' : (s.rejudgement || '');
    document.getElementById('cancel-edit').hidden = false;
    form.scrollIntoView({behavior: 'smooth', block: 'center'});
  });
  const cancel = document.getElementById('cancel-edit');
  if (cancel) cancel.onclick = () => refresh();
  document.querySelectorAll('[data-delete]').forEach(el => el.onclick = async () => {
    try { await leakApi.removeSpecimen(leakStore.rollId, +el.dataset.delete); refresh(); }
    catch (e) { document.getElementById('notice').textContent = e.message; }
  });
}
