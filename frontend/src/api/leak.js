import {request, post} from './client.js';
export const leakApi = {
  domain: () => request('/leak/domain'),
  overview: () => request('/leak/overview'),
  rolls: () => request('/leak/rolls'),
  createRoll: x => post('/leak/rolls', x),
  specimens: rollId => request(`/leak/rolls/${rollId}/specimens`),
  saveSpecimen: (rollId, x, specimenId) => specimenId
    ? request(`/leak/rolls/${rollId}/specimens/${specimenId}`, {method: 'PUT', body: JSON.stringify(x)})
    : post(`/leak/rolls/${rollId}/specimens`, x),
  removeSpecimen: (rollId, specimenId) =>
    request(`/leak/rolls/${rollId}/specimens/${specimenId}`, {method: 'DELETE'}),
  rounds: () => request('/leak/rounds'),
  createRound: x => post('/leak/rounds', x),
  round: id => request(`/leak/rounds/${id}`),
  assignRolls: (id, x) => request(`/leak/rounds/${id}/rolls`, {method: 'PUT', body: JSON.stringify(x)}),
  calibrate: id => post(`/leak/rounds/${id}/calibrate`, {}),
  reveal: id => post(`/leak/rounds/${id}/reveal`, {}),
  jobs: () => request('/leak/jobs'),
  audits: () => request('/leak/audits'),
};
