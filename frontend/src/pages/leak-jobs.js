import {JOB_STATE_LABELS} from '../constants/leak.js';
import {leakStore, loadLeak} from '../stores/leak.js';
import {leakApi} from '../api/leak.js';
import {table} from '../components/common/table.js';
import {esc} from '../utils/format.js';

function summary(job) {
  const r = job.result || {};
  if (job.kind === 'calibration') {
    return `分界=${r.cutoff}，校准误判=${r.calibration_misjudgements}，试件=${r.specimen_count}`;
  }
  return `分界=${r.cutoff}，盲验误判=${r.blind_misjudgements}，占卷=${(r.roll_ids || []).length}，试件=${r.specimen_count}`;
}

export async function render() {
  await loadLeak();
  const audits = await leakApi.audits();
  return `<div class="eyebrow">L04 / JOBS & AUDIT</div>
<h1>任务队列与操作留痕</h1>
<p class="lead">worker 重启会把 queued/running 任务重新排队；已完成任务重试幂等跳过，揭晓不重复占卷。</p>
<h2>漏封仪任务</h2>
${table(['任务#', '研究轮', '类型', '状态', '结果摘要', '错误', '更新时间'], leakStore.jobs.map(j => [
  j.id, j.round_id,
  j.kind === 'calibration' ? '校准' : '揭晓',
  {html: `<span class="status ${j.status === 'completed' ? 'completed' : j.status === 'failed' ? 'failed' : ''}">${esc(JOB_STATE_LABELS[j.status] || j.status)}</span>`},
  j.result ? esc(summary(j)) : '—',
  j.error ? esc(j.error) : '—',
  j.updated_at,
]))}
<h2>操作留痕（漏封仪）</h2>
${table(['时间', '操作者', '动作', '明细'], audits.map(a => [a.created_at, a.actor, a.action, a.detail]))}`;
}

export function bind() {}
