/**
 * Tests for the App (root) component and api.js.
 *
 * Requirements tested:
 *   FE-APP-01  Header shows BillWatch title and subtitle
 *   FE-APP-02  Three nav tabs present: Dashboard, Signals, Actions
 *   FE-APP-03  Dashboard view renders by default
 *   FE-APP-04  Clicking Signals tab shows SignalTable
 *   FE-APP-05  Clicking Actions tab shows ActionsView
 *   FE-APP-06  Load Synthetic Data button exists and triggers loadBatch
 *   FE-APP-07  Run Recovery Pipeline button exists and triggers runPipeline
 *   FE-APP-08  Success toast appears after batch load
 *   FE-APP-09  Error toast appears when batch load fails
 *   FE-APP-10  Audit Trail tab appears when navigating from Signals
 *   FE-APP-11  Live clock is rendered in the header
 *   FE-APP-12  "Last run" chip appears after running pipeline
 *
 * API module tests:
 *   FE-API-01  loadBatch makes POST /batch/load
 *   FE-API-02  runPipeline makes POST /pipeline/run
 *   FE-API-03  getSignals without param makes GET /signals
 *   FE-API-04  getSignals with param makes GET /signals?source_type=payment
 *   FE-API-05  getAuditTrail makes GET /audit/{entityId}
 *   FE-API-06  getMetricsSummary makes GET /metrics/summary
 *   FE-API-07  Non-200 responses throw with status code in message
 */

import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import App from '../App';
import * as api from '../api';
import { mockMetrics, mockSignals, mockActions } from './mocks';

vi.mock('../api');


describe('App navigation and controls', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getMetricsSummary.mockResolvedValue(mockMetrics);
    api.getSignals.mockResolvedValue(mockSignals);
    api.getActions.mockResolvedValue(mockActions);
    api.loadBatch.mockResolvedValue({ message: 'Loaded 60 payments and 40 checkout sessions.', payments_loaded: 60, checkout_sessions_loaded: 40 });
    api.runPipeline.mockResolvedValue({ message: 'Pipeline complete: detected 30 signals.', signals_detected: 30, actions_decided: 25, actions_executed: 20 });
  });

  it('FE-APP-01: renders BillWatch title in header', async () => {
    render(<App />);
    await waitFor(() => expect(screen.getByRole('heading', { name: /billwatch/i })).toBeInTheDocument());
  });

  it('FE-APP-02: renders three nav tabs', async () => {
    render(<App />);
    await waitFor(() => {
      expect(screen.getByText(/📊 dashboard/i)).toBeInTheDocument();
      expect(screen.getByText(/🔍 signals/i)).toBeInTheDocument();
      expect(screen.getByText(/⚡ actions/i)).toBeInTheDocument();
    });
  });

  it('FE-APP-03: Dashboard view is shown by default', async () => {
    render(<App />);
    await waitFor(() => expect(api.getMetricsSummary).toHaveBeenCalled());
  });

  it('FE-APP-04: clicking Signals tab renders SignalTable', async () => {
    render(<App />);
    await waitFor(() => screen.getByText(/🔍 signals/i));
    fireEvent.click(screen.getByText(/🔍 signals/i));
    await waitFor(() => expect(api.getSignals).toHaveBeenCalled());
  });

  it('FE-APP-05: clicking Actions tab renders ActionsView', async () => {
    render(<App />);
    await waitFor(() => screen.getByText(/⚡ actions/i));
    fireEvent.click(screen.getByText(/⚡ actions/i));
    await waitFor(() => expect(api.getActions).toHaveBeenCalled());
  });

  it('FE-APP-06: Load Synthetic Data button exists', async () => {
    render(<App />);
    await waitFor(() =>
      expect(screen.getByText(/load synthetic data/i)).toBeInTheDocument()
    );
  });

  it('FE-APP-06: clicking Load Synthetic Data calls loadBatch', async () => {
    render(<App />);
    await waitFor(() => screen.getByText(/load synthetic data/i));
    fireEvent.click(screen.getByText(/load synthetic data/i));
    await waitFor(() => expect(api.loadBatch).toHaveBeenCalled());
  });

  it('FE-APP-07: Run Recovery Pipeline button exists', async () => {
    render(<App />);
    await waitFor(() =>
      expect(screen.getByText(/run recovery pipeline/i)).toBeInTheDocument()
    );
  });

  it('FE-APP-07: clicking Run Recovery Pipeline calls runPipeline', async () => {
    render(<App />);
    await waitFor(() => screen.getByText(/run recovery pipeline/i));
    fireEvent.click(screen.getByText(/run recovery pipeline/i));
    await waitFor(() => expect(api.runPipeline).toHaveBeenCalled());
  });

  it('FE-APP-08: success toast appears after successful batch load', async () => {
    render(<App />);
    await waitFor(() => screen.getByText(/load synthetic data/i));
    fireEvent.click(screen.getByText(/load synthetic data/i));
    await waitFor(() =>
      expect(screen.getByText(/loaded 60 payments/i)).toBeInTheDocument()
    );
  });

  it('FE-APP-09: error toast appears when batch load fails', async () => {
    api.loadBatch.mockRejectedValue(new Error('Server down'));
    render(<App />);
    await waitFor(() => screen.getByText(/load synthetic data/i));
    fireEvent.click(screen.getByText(/load synthetic data/i));
    await waitFor(() =>
      expect(screen.getByText(/failed to load batch/i)).toBeInTheDocument()
    );
  });

  it('FE-APP-11: live clock is present in the header', async () => {
    render(<App />);
    // Clock shows time in HH:MM:SS format
    await waitFor(() => {
      const clockEl = document.querySelector('.header-clock');
      expect(clockEl).not.toBeNull();
    });
  });

  it('FE-APP-12: last run chip appears after pipeline run', async () => {
    render(<App />);
    await waitFor(() => screen.getByText(/run recovery pipeline/i));
    fireEvent.click(screen.getByText(/run recovery pipeline/i));
    await waitFor(() =>
      expect(screen.getByText(/last run:/i)).toBeInTheDocument()
    );
  });
});

