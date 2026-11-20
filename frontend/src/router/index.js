import * as overview from '../pages/overview.js';
import * as data from '../pages/data.js';
import * as analysis from '../pages/analysis.js';
import * as results from '../pages/results.js';
import * as review from '../pages/review.js';
import * as audit from '../pages/audit.js';
import * as leakRolls from '../pages/leak-rolls.js';
import * as leakRounds from '../pages/leak-rounds.js';
import * as leakRoundDetail from '../pages/leak-round-detail.js';
import * as leakJobs from '../pages/leak-jobs.js';
export const pages = {
  overview, data, analysis, results, review, audit,
  'leak-rolls': leakRolls,
  'leak-rounds': leakRounds,
  'leak-round': leakRoundDetail,
  'leak-jobs': leakJobs,
};
// 需要二级 id 的页面
export const PAGES_WITH_ID = new Set(['results', 'review', 'leak-round']);
