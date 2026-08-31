/**
 * Tests for the Dashboard component.
 *
 * Requirements tested:
 *   FE-DASH-01  Shows loading state while fetching
 *   FE-DASH-02  Shows empty state when no data (total_at_risk === 0)
 *   FE-DASH-03  Shows error/empty state on API failure
 *   FE-DASH-04  Renders hero stat with recovered amount formatted in INR
 *   FE-DASH-05  Renders all 5 stat cards (at-risk, recovered, actions, blocked, escalated)
 *   FE-DASH-06  Shows simulation banner
 *   FE-DASH-07  Recovery rate displays correctly as a percentage
 *   FE-DASH-08  Root cause breakdown is rendered with correct labels
 *   FE-DASH-09  Stopped reasons breakdown is rendered
 *   FE-DASH-10  "No actions blocked" message appears when stopped_reasons is empty
 */

import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import Dashboard from '../components/Dashboard';
import * as api from '../api';
import { mockMetrics } from './mocks';

vi.mock('../api');


describe('Dashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('FE-DASH-01: shows loading state initially', async () => {
    api.getMetricsSummary.mockImplementation(() => new Promise(() => {})); // never resolves
    render(<Dashboard />);
    expect(screen.getByText(/loading metrics/i)).toBeInTheDocument();
  });

  it('FE-DASH-02: shows empty state when total_at_risk is 0', async () => {
    api.getMetricsSummary.mockResolvedValue({ ...mockMetrics, total_at_risk: 0 });
    render(<Dashboard />);
    await waitFor(() => expect(screen.getByText(/no signals detected/i)).toBeInTheDocument());
  });

  it('FE-DASH-03: shows no-data state on API error', async () => {
    api.getMetricsSummary.mockRejectedValue(new Error('Network error'));
    render(<Dashboard />);
    await waitFor(() => expect(screen.getByText(/no data available/i)).toBeInTheDocument());
  });

  it('FE-DASH-04: renders total recovered amount in INR format', async () => {
    api.getMetricsSummary.mockResolvedValue(mockMetrics);
    render(<Dashboard />);
    // 87500 formatted → ₹87,500 (Indian locale)
    await waitFor(() => expect(screen.getAllByText(/₹87,500/).length).toBeGreaterThan(0));
  });

  it('FE-DASH-05: renders all 5 stat card titles', async () => {
    api.getMetricsSummary.mockResolvedValue(mockMetrics);
    render(<Dashboard />);
    await waitFor(() => {
      expect(screen.getByText('At Risk')).toBeInTheDocument();
      expect(screen.getByText('Recovered')).toBeInTheDocument();
      expect(screen.getByText('Actions Taken')).toBeInTheDocument();
      expect(screen.getByText('Blocked by Policy')).toBeInTheDocument();
      expect(screen.getByText('Escalated to Human')).toBeInTheDocument();
    });
  });

  it('FE-DASH-06: displays simulation banner', async () => {
    api.getMetricsSummary.mockResolvedValue(mockMetrics);
    render(<Dashboard />);
    await waitFor(() =>
      expect(screen.getByText(/all recovery actions are simulated/i)).toBeInTheDocument()
    );
  });

  it('FE-DASH-07: shows recovery rate as percentage', async () => {
    api.getMetricsSummary.mockResolvedValue(mockMetrics);
    render(<Dashboard />);
    // 0.5833 * 100 = 58.3%
    await waitFor(() => expect(screen.getByText(/58\.3%/)).toBeInTheDocument());
  });

  it('FE-DASH-08: renders root cause labels from by_root_cause', async () => {
    api.getMetricsSummary.mockResolvedValue(mockMetrics);
    render(<Dashboard />);
    await waitFor(() => {
      expect(screen.getByText(/bank timeout/i)).toBeInTheDocument();
      expect(screen.getByText(/otp failed/i)).toBeInTheDocument();
      expect(screen.getByText(/card expired/i)).toBeInTheDocument();
    });
  });

  it('FE-DASH-09: renders stopped reason labels', async () => {
    api.getMetricsSummary.mockResolvedValue(mockMetrics);
    render(<Dashboard />);
    await waitFor(() => {
      expect(screen.getByText(/max attempts reached/i)).toBeInTheDocument();
      expect(screen.getByText(/cooldown active/i)).toBeInTheDocument();
    });
  });

  it('FE-DASH-10: shows "no actions blocked" when stopped_reasons is empty', async () => {
    api.getMetricsSummary.mockResolvedValue({ ...mockMetrics, stopped_reasons: {} });
    render(<Dashboard />);
    await waitFor(() =>
      expect(screen.getByText(/no actions were blocked/i)).toBeInTheDocument()
    );
  });

  it('renders stat card values correctly', async () => {
    api.getMetricsSummary.mockResolvedValue(mockMetrics);
    render(<Dashboard />);
    await waitFor(() => {
      expect(screen.getByText('42')).toBeInTheDocument(); // actions_taken
      expect(screen.getAllByText('8').length).toBeGreaterThan(0);  // actions_blocked
      expect(screen.getAllByText('3').length).toBeGreaterThan(0);  // escalated
    });
  });
});

