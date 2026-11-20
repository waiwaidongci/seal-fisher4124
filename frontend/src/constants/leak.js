export const LEAK_DOMAIN = {"id": "gb-0038", "slug": "leak-threshold", "title": "漏封仪分界校准与盲验席", "direction": "分界值校准 / 盲样验证", "algorithm": "校准组实测读数候选分界；读数达到分界即判漏封；误判最少且同分取小值", "note": "分界值换一卷可能就不准。读数达到分界算漏封；从校准组实测读数中选误判最少的分界，同分取小值。分界冻结前盲验复判只可录入、不可查看；校准失败不占盲验卷；已揭晓卷不得再盲验。", "judgement": {"leak": "漏封", "sealed": "合格"}, "round_states": ["draft", "calibrated", "revealed", "rejected"], "job_states": ["queued", "running", "completed", "failed"]};
export const ROUND_STATE_LABELS = {
  draft: '草稿（未校准）',
  calibrated: '分界已冻结',
  revealed: '盲验已揭晓',
  rejected: '已拒绝（见原因）',
};
export const JOB_STATE_LABELS = {
  queued: '排队中',
  running: '执行中',
  completed: '已完成',
  failed: '失败',
};
