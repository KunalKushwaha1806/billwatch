/**
 * BillWatch API client — thin fetch wrappers for all backend endpoints.
 */

const API_BASE = 'http://localhost:8000';

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`API ${res.status}: ${err}`);
  }
  return res.json();
}

/** POST /batch/load — load synthetic dataset */
export const loadBatch = () => request('/batch/load', { method: 'POST' });

/** POST /pipeline/run — run the 4-stage recovery pipeline */
export const runPipeline = () => request('/pipeline/run', { method: 'POST' });

/** GET /signals — list all flagged risk signals */
export const getSignals = (sourceType) => {
  const params = sourceType ? `?source_type=${sourceType}` : '';
  return request(`/signals${params}`);
};

/** GET /actions — list all recovery actions */
export const getActions = (outcome) => {
  const params = outcome ? `?outcome=${outcome}` : '';
  return request(`/actions${params}`);
};

/** GET /audit/{entityId} — full audit trail for an entity */
export const getAuditTrail = (entityId) => request(`/audit/${entityId}`);

/** GET /metrics/summary — aggregate recovery metrics */
export const getMetricsSummary = () => request('/metrics/summary');
