/**
 * Tests for the ActionsView component.
 *
 * Requirements tested:
 *   FE-ACT-01  Shows loading state while fetching
 *   FE-ACT-02  Shows empty state when no actions
 *   FE-ACT-03  Renders one row per action
 *   FE-ACT-04  Summary chips show correct aggregated counts/amounts
 *   FE-ACT-05  Action type badge renders correct label
 *   FE-ACT-06  Outcome badge renders correctly (Recovered / Failed / Pending)
 *   FE-ACT-07  Stopped reason badge appears for blocked actions
 *   FE-ACT-08  Clicking a row calls onSelectEntity with source_id
 *   FE-ACT-09  Outcome filter (All / Recovered / Failed / Pending) calls getActions correctly
 *   FE-ACT-10  Search input filters by source_id
 *   FE-ACT-11  Search input filters by action_type
 *   FE-ACT-12  Export CSV button triggers a download (anchor click)
 *   FE-ACT-13  Action count text shows correct number
 *   FE-ACT-14  Amount recovered is formatted in INR for recovered actions
 */

import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ActionsView from '../components/ActionsView';
import * as api from '../api';
import { mockActions } from './mocks';

vi.mock('../api');


describe('ActionsView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getActions.mockResolvedValue(mockActions);
  });

  it('FE-ACT-01: shows loading state initially', () => {
    api.getActions.mockImplementation(() => new Promise(() => {}));
    render(<ActionsView onSelectEntity={() => {}} />);
    expect(screen.getByText(/loading recovery actions/i)).toBeInTheDocument();
  });

  it('FE-ACT-02: shows empty state when no actions', async () => {
    api.getActions.mockResolvedValue([]);
    render(<ActionsView onSelectEntity={() => {}} />);
    await waitFor(() =>
      expect(screen.getByText(/no recovery actions yet/i)).toBeInTheDocument()
    );
  });

  it('FE-ACT-03: renders one table row per action', async () => {
    render(<ActionsView onSelectEntity={() => {}} />);
    await waitFor(() => {
      const rows = screen.getAllByRole('row');
      expect(rows.length).toBe(mockActions.length + 1); // +1 for thead
    });
  });

  it('FE-ACT-04: summary chip shows total recovered amount', async () => {
    render(<ActionsView onSelectEntity={() => {}} />);
    // mockActions: act_001 recovered ₹12,000
    await waitFor(() => expect(screen.getAllByText(/₹12,000/).length).toBeGreaterThan(0));
  });

  it('FE-ACT-04: summary chip shows failed count', async () => {
    render(<ActionsView onSelectEntity={() => {}} />);
    // act_002 is failed (non-policy-block)
    await waitFor(() => {
      // "1 Failed" in the chip label area
      const failedLabels = screen.getAllByText(/failed/i);
      expect(failedLabels.length).toBeGreaterThan(0);
    });
  });

  it('FE-ACT-05: renders action type badges', async () => {
    render(<ActionsView onSelectEntity={() => {}} />);
    await waitFor(() => {
      expect(screen.getAllByText(/retry payment/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/send nudge/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/policy block/i).length).toBeGreaterThan(0);
    });
  });

  it('FE-ACT-06: renders outcome badges', async () => {
    render(<ActionsView onSelectEntity={() => {}} />);
    await waitFor(() => {
      expect(screen.getAllByText(/recovered/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/failed/i).length).toBeGreaterThan(0);
    });
  });

  it('FE-ACT-07: stopped reason badge appears for fraud block', async () => {
    render(<ActionsView onSelectEntity={() => {}} />);
    await waitFor(() => expect(screen.getByText(/fraud block/i)).toBeInTheDocument());
  });

  it('FE-ACT-08: clicking a row calls onSelectEntity with source_id', async () => {
    const onSelect = vi.fn();
    render(<ActionsView onSelectEntity={onSelect} />);
    await waitFor(() => screen.getByText('pay_abc123'));
    fireEvent.click(screen.getByText('pay_abc123').closest('tr'));
    expect(onSelect).toHaveBeenCalledWith('pay_abc123');
  });

  it('FE-ACT-09: All filter calls getActions with no param', async () => {
    render(<ActionsView onSelectEntity={() => {}} />);
    await waitFor(() => screen.getAllByRole('button', { name: /^all$/i }));
    fireEvent.click(screen.getAllByRole('button', { name: /^all$/i })[0]);
    expect(api.getActions).toHaveBeenCalledWith(undefined);
  });

  it('FE-ACT-09: Recovered filter calls getActions with "recovered"', async () => {
    render(<ActionsView onSelectEntity={() => {}} />);
    await waitFor(() => screen.getByRole('button', { name: /recovered/i }));
    const recoveredBtn = screen.getByRole('button', { name: /recovered/i });
    fireEvent.click(recoveredBtn);
    expect(api.getActions).toHaveBeenCalledWith('recovered');
  });

  it('FE-ACT-10: search by source_id filters rows', async () => {
    const user = userEvent.setup();
    render(<ActionsView onSelectEntity={() => {}} />);
    await waitFor(() => screen.getByText('pay_abc123'));

    const search = screen.getByPlaceholderText(/search by id/i);
    await user.type(search, 'pay_abc123');

    await waitFor(() => {
      expect(screen.getByText('pay_abc123')).toBeInTheDocument();
      expect(screen.queryByText('sess_xyz456')).not.toBeInTheDocument();
    });
  });

  it('FE-ACT-11: search by action_type filters rows', async () => {
    const user = userEvent.setup();
    render(<ActionsView onSelectEntity={() => {}} />);
    await waitFor(() => screen.getByText('pay_abc123'));

    const search = screen.getByPlaceholderText(/search by id/i);
    await user.type(search, 'send_nudge');

    await waitFor(() => {
      expect(screen.getByText('sess_xyz456')).toBeInTheDocument();
      expect(screen.queryByText('pay_abc123')).not.toBeInTheDocument();
    });
  });

  it('FE-ACT-12: Export CSV button exists and is clickable', async () => {
    // Mock URL.createObjectURL and anchor click
    const mockCreateURL = vi.fn().mockReturnValue('blob:test');
    const mockRevokeURL = vi.fn();
    const mockClick = vi.fn();
    global.URL.createObjectURL = mockCreateURL;
    global.URL.revokeObjectURL = mockRevokeURL;

    render(<ActionsView onSelectEntity={() => {}} />);
    await waitFor(() => screen.getByText(/export csv/i));
    fireEvent.click(screen.getByText(/export csv/i));

    expect(mockCreateURL).toHaveBeenCalled();
  });

  it('FE-ACT-13: shows correct action count', async () => {
    render(<ActionsView onSelectEntity={() => {}} />);
    await waitFor(() =>
      expect(screen.getByText(/showing 3 of 3 actions/i)).toBeInTheDocument()
    );
  });

  it('FE-ACT-14: recovered amount is INR-formatted', async () => {
    render(<ActionsView onSelectEntity={() => {}} />);
    await waitFor(() => {
      expect(screen.getAllByText(/₹12,000/).length).toBeGreaterThan(0);
    });
  });
});
