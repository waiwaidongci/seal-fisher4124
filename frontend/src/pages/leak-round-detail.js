import {LEAK_DOMAIN, ROUND_STATE_LABELS, JOB_STATE_LABELS} from '../constants/leak.js';
import {loadLeak} from '../stores/leak.js';
import {leakApi} from '../api/leak.js';
import {table} from '../components/common/table.js';
import {esc, fmt} from '../utils/format.js';

function rollBlock(title, rolls, masked) {
  return `<h3>${esc(title)} <small>${rolls.length} 卷</small></h3>` + rolls.map(roll =>
    `<details><summary>${esc(roll.roll_code)} · ${esc(roll.material || '')} · ${roll.specimens.length} 个试件${roll.occupied ? ' · 已占用' : ''}</summary>
${table(['试件编号', '实测读数', '人工复判'], roll.specimens.map(s => [
  s.specimen_key, s.reading,
  s.rejudgement === null || s.rejudgement === undefined ? '—' : esc(s.rejudgement),
]))}</details>`).join('');
}

export async function render(id) {
  if (!id) return '<h1>研究轮详情</h1><p class="method-note">请从研究轮列表选择一轮。</p>';
  await loadLeak();
  const r = await leakApi.round(id);
  const writable = localStorage.getItem('research-role') !== 'viewer';
  const latestJob = r.jobs[0];
  const busy = latestJob && ['queued', 'running'].includes(latestJob.status);
  const lastCalibration = r.jobs.find(j => j.kind === 'calibration' && j.status === 'completed');
  const lastReveal = r.jobs.find(j => j.kind === 'reveal' && j.status === 'completed');
  const candidateTable = lastCalibration?.result?.candidate_table || null;
  const revealDetail = lastReveal?.result?.details || null;
  return `<div class="eyebrow">L03 / ROUND DETAIL · #${r.id}</div>
<h1>${esc(r.name)} <span class="status ${r.status === 'revealed' ? 'completed' : r.status === 'rejected' ? 'failed' : ''}">${esc(ROUND_STATE_LABELS[r.status] || r.status)}</span></h1>
<p>${esc(r.note || '')}</p>
<div class="strip">
  <div>选定分界<br><strong style="font-size:26px">${r.cutoff === null || r.cutoff === undefined ? '未冻结' : fmt(r.cutoff)}</strong></div>
  <div>盲验误判数<br><strong style="font-size:26px">${r.blind_misjudgements === null || r.blind_misjudgements === undefined ? '—' : fmt(r.blind_misjudgements)}</strong></div>
  <div>规则<br><small>${esc(LEAK_DOMAIN.algorithm)}</small></div>
</div>
${r.reject_reason ? `<div class="error">拒绝原因：${esc(r.reject_reason)}</div>` : ''}
${writable ? `<div class="toolbar">
  <button id="btn-calibrate" ${busy || r.status === 'calibrated' || r.status === 'revealed' ? 'disabled' : ''}>① 校准并冻结分界</button>
  <button id="btn-reveal" class="secondary" ${busy || r.cutoff === null || r.cutoff === undefined || r.status === 'revealed' ? 'disabled' : ''}>② 揭晓盲验（原子占卷）</button>
  ${busy ? '<small class="checksum">任务进行中，页面每2秒刷新…</small>' : ''}
</div>` : ''}
<h2>任务记录</h2>
${table(['#', '类型', '状态', '错误/拒绝原因', '时间'], r.jobs.map(j => [
  j.id,
  j.kind === 'calibration' ? '校准' : '揭晓',
  {html: `<span class="status ${j.status === 'completed' ? 'completed' : j.status === 'failed' ? 'failed' : ''}">${esc(JOB_STATE_LABELS[j.status] || j.status)}</span>`},
  j.error ? esc(j.error) : '—',
  j.updated_at,
]))}
${candidateTable ? `<h2>校准候选分界 <small>读数达到分界即判漏封；误判最少、同分取小值</small></h2>
${table(['候选分界（取校准组实测读数）', '误判数'], candidateTable.map(c => [
  {html: c.cutoff === r.cutoff ? `<strong>${fmt(c.cutoff)} ✓ 选定</strong>` : fmt(c.cutoff)},
  c.misjudgements,
]))}` : ''}
${revealDetail ? `<h2>盲验逐件结果 <small>揭晓后可见复判</small></h2>
${table(['试件编号', '实测读数', '复判真值', '仪器判定', '是否误判'], revealDetail.map(d => [
  d.specimen_key, d.reading,
  d.rejudgement === 'leak' ? '漏封' : '合格',
  d.instrument === 'leak' ? '漏封' : '合格',
  d.misjudged ? {html: '<span class="error">误判</span>'} : '一致',
]))}` : ''}
<h2>整卷分配</h2>
${rollBlock('校准组卷（复判可见）', r.calibration_rolls, false)}
${rollBlock(r.status === 'revealed' ? '盲验组卷（已揭晓，复判可见）' : '盲验组卷（冻结前复判封存）', r.blind_rolls, true)}`;
}

export function bind(refresh, id) {
  const cal = document.getElementById('btn-calibrate');
  const rev = document.getElementById('btn-reveal');
  if (cal) cal.onclick = async () => {
    try { await leakApi.calibrate(id); await refresh(); }
    catch (e) { document.getElementById('notice').textContent = e.message; }
  };
  if (rev) rev.onclick = async () => {
    if (!confirm('揭晓将原子占用整批盲验卷并写入盲验误判数，且不可撤销。确认？')) return;
    try { await leakApi.reveal(id); await refresh(); }
    catch (e) { document.getElementById('notice').textContent = e.message; }
  };
}
