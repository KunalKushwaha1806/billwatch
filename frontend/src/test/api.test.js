/**
 * Unit tests for api.js HTTP wrapper functions.
 *
 * Requirements tested:
 *   FE-API-01  loadBatch makes POST /batch/load
 *   FE-API-02  runPipeline makes POST /pipeline/run
 *   FE-API-03  getSignals without param makes GET /signals
 *   FE-API-04  getSignals with param makes GET /signals?source_type=payment
 *   FE-API-05  getAuditTrail makes GET /audit/{entityId}
 *   FE-API-06  getMetricsSummary makes GET /metrics/summary
 *   FE-API-07  Non-200 responses throw with status in error message
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  loadBatch,
  runPipeline,
  getSignals,
  getActions,
  getAuditTrail,
  getMetricsSummary,
} from '../api';

describe('api.js HTTP Client', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    global.fetch = vi.fn();
  });

  const makeResponse = (body, status = 200) => ({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
  });

  it('FE-API-01: loadBatch posts to /batch/load', async () => {
    global.fetch.mockResolvedValue(makeResponse({ message: 'ok' }));
    await loadBatch();
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/batch/load'),
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('FE-API-02: runPipeline posts to /pipeline/run', async () => {
    global.fetch.mockResolvedValue(makeResponse({ message: 'ok' }));
    await runPipeline();
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/pipeline/run'),
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('FE-API-03: getSignals without param calls /signals', async () => {
    global.fetch.mockResolvedValue(makeResponse([]));
    await getSignals();
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringMatching(/\/signals$/),
      expect.any(Object),
    );
  });

  it('FE-API-04: getSignals with param adds query string', async () => {
    global.fetch.mockResolvedValue(makeResponse([]));
    await getSignals('payment');
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('source_type=payment'),
      expect.any(Object),
    );
  });

  it('FE-API-05: getAuditTrail calls /audit/{entityId}', async () => {
    global.fetch.mockResolvedValue(makeResponse([]));
    await getAuditTrail('pay_test_123');
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/audit/pay_test_123'),
      expect.any(Object),
    );
  });

  it('FE-API-06: getMetricsSummary calls /metrics/summary', async () => {
    global.fetch.mockResolvedValue(makeResponse({}));
    await getMetricsSummary();
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/metrics/summary'),
      expect.any(Object),
    );
  });

  it('FE-API-07: getActions with param adds query string', async () => {
    global.fetch.mockResolvedValue(makeResponse([]));
    await getActions('recovered');
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('outcome=recovered'),
      expect.any(Object),
    );
  });

  it('FE-API-08: non-200 response throws with status code in message', async () => {
    global.fetch.mockResolvedValue(makeResponse({ detail: 'Not found' }, 404));
    await expect(getAuditTrail('bad_id')).rejects.toThrow('404');
  });
});
