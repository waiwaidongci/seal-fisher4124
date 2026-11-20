import {leakApi} from '../api/leak.js';
export const leakStore = {
  rolls: [],
  rounds: [],
  jobs: [],
  rollId: 0,
  roundId: 0,
};
export async function loadLeak() {
  const data = await leakApi.overview();
  leakStore.rolls = data.rolls;
  leakStore.rounds = data.rounds;
  leakStore.jobs = data.jobs;
  if (!leakStore.rollId) leakStore.rollId = leakStore.rolls[0]?.id || 0;
  if (!leakStore.roundId) leakStore.roundId = leakStore.rounds[0]?.id || 0;
}
