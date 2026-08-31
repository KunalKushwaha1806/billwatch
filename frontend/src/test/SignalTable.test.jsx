/**
 * Tests for the SignalTable component.
 *
 * Requirements tested:
 *   FE-SIG-01  Shows loading state while fetching
 *   FE-SIG-02  Shows empty state when no signals
 *   FE-SIG-03  Renders a row for each signal returned by the API
 *   FE-SIG-04  Source type badge renders 'Payment' or 'Checkout' correctly
 *   FE-SIG-05  Risk score is rendered as a number (0.00–1.00)
 *   FE-SIG-06  Root cause badge renders cause text with underscores replaced by spaces
 *   FE-SIG-07  Amount column shows INR-formatted value
 *   FE-SIG-08  Clicking a row calls onSelectSignal with the correct source_id
 *   FE-SIG-09  Filter tabs (All / Payments / Checkouts) call getSignals with correct param
 *   FE-SIG-10  Search input filters rows by source_id
 *   FE-SIG-11  Search input filters rows by root_cause
 *   FE-SIG-12  Search clear button resets the filter
 *   FE-SIG-13  Signal count displays "N signals flagged"
 *   FE-SIG-14  Clicking a column header sorts ascending/descending
 */

import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import SignalTable from '../components/SignalTable';
import * as api from '../api';
import { mockSignals } from './mocks';

vi.mock('../api');


describe('SignalTable', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getSignals.mockResolvedValue(mockSignals);
  });

  it('FE-SIG-01: shows loading state initially', () => {
    api.getSignals.mockImplementation(() => new Promise(() => {}));
    render(<SignalTable onSelectSignal={() => {}} />);
    expect(screen.getByText(/loading signals/i)).toBeInTheDocument();
  });

  it('FE-SIG-02: shows empty state when API returns no signals', async () => {
    api.getSignals.mockResolvedValue([]);
    render(<SignalTable onSelectSignal={() => {}} />);
    await waitFor(() => expect(screen.getByText(/no signals detected/i)).toBeInTheDocument());
  });

  it('FE-SIG-03: renders a row per signal', async () => {
    render(<SignalTable onSelectSignal={() => {}} />);
    await waitFor(() => {
      // 3 signals → 3 rows (+ header)
      const rows = screen.getAllByRole('row');
      expect(rows.length).toBe(mockSignals.length + 1); // +1 for thead
    });
  });

  it('FE-SIG-04: renders Payment badge for payment type', async () => {
    render(<SignalTable onSelectSignal={() => {}} />);
    await waitFor(() => {
      const paymentBadges = screen.getAllByText(/💳 Payment/);
      expect(paymentBadges.length).toBeGreaterThan(0);
    });
  });

  it('FE-SIG-04: renders Checkout badge for checkout type', async () => {
    render(<SignalTable onSelectSignal={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText('🛒 Checkout')).toBeInTheDocument();
    });
  });

  it('FE-SIG-05: renders risk scores', async () => {
    render(<SignalTable onSelectSignal={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText('0.92')).toBeInTheDocument();
      expect(screen.getByText('0.65')).toBeInTheDocument();
      expect(screen.getByText('0.35')).toBeInTheDocument();
    });
  });

  it('FE-SIG-06: root cause underscores replaced by spaces', async () => {
    render(<SignalTable onSelectSignal={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText(/bank timeout/i)).toBeInTheDocument();
      expect(screen.getByText(/price hesitation/i)).toBeInTheDocument();
      expect(screen.getByText(/card expired/i)).toBeInTheDocument();
    });
  });

  it('FE-SIG-07: shows formatted INR amount for payment signals', async () => {
    render(<SignalTable onSelectSignal={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText(/₹12,000/)).toBeInTheDocument();
    });
  });

  it('FE-SIG-08: clicking a row calls onSelectSignal with correct source_id', async () => {
    const onSelect = vi.fn();
    render(<SignalTable onSelectSignal={onSelect} />);
    await waitFor(() => screen.getByText('pay_abc123'));

    fireEvent.click(screen.getByText('pay_abc123').closest('tr'));
    expect(onSelect).toHaveBeenCalledWith('pay_abc123');
  });

  it('FE-SIG-09: All Signals filter calls getSignals with no param', async () => {
    render(<SignalTable onSelectSignal={() => {}} />);
    await waitFor(() => screen.getByText(/all signals/i));
    fireEvent.click(screen.getByText(/all signals/i));
    expect(api.getSignals).toHaveBeenCalledWith(undefined);
  });

  it('FE-SIG-09: Payments filter calls getSignals with "payment"', async () => {
    render(<SignalTable onSelectSignal={() => {}} />);
    await waitFor(() => screen.getByText(/💳 payments/i));
    fireEvent.click(screen.getByText(/💳 payments/i));
    expect(api.getSignals).toHaveBeenCalledWith('payment');
  });

  it('FE-SIG-10: search by source_id filters visible rows', async () => {
    const user = userEvent.setup();
    render(<SignalTable onSelectSignal={() => {}} />);
    await waitFor(() => screen.getByText('pay_abc123'));

    const searchInput = screen.getByPlaceholderText(/search by source id/i);
    await user.type(searchInput, 'pay_abc123');

    // Only the row matching 'pay_abc123' should remain
    await waitFor(() => {
      expect(screen.getByText('pay_abc123')).toBeInTheDocument();
      expect(screen.queryByText('sess_xyz456')).not.toBeInTheDocument();
    });
  });

  it('FE-SIG-11: search by root_cause filters rows', async () => {
    const user = userEvent.setup();
    render(<SignalTable onSelectSignal={() => {}} />);
    await waitFor(() => screen.getByText('pay_abc123'));

    const searchInput = screen.getByPlaceholderText(/search by source id/i);
    await user.type(searchInput, 'bank_timeout');

    await waitFor(() => {
      expect(screen.getByText('pay_abc123')).toBeInTheDocument();
      expect(screen.queryByText('sess_xyz456')).not.toBeInTheDocument();
    });
  });

  it('FE-SIG-12: search clear button resets filter', async () => {
    const user = userEvent.setup();
    render(<SignalTable onSelectSignal={() => {}} />);
    await waitFor(() => screen.getByText('pay_abc123'));

    const searchInput = screen.getByPlaceholderText(/search by source id/i);
    await user.type(searchInput, 'pay_abc123');
    await waitFor(() => expect(screen.queryByText('sess_xyz456')).not.toBeInTheDocument());

    const clearBtn = screen.getByText('✕');
    await user.click(clearBtn);

    await waitFor(() => {
      expect(screen.getByText('sess_xyz456')).toBeInTheDocument();
    });
  });

  it('FE-SIG-13: shows signal count', async () => {
    render(<SignalTable onSelectSignal={() => {}} />);
    await waitFor(() => expect(screen.getByText(/3 signals flagged/)).toBeInTheDocument());
  });

  it('FE-SIG-14: clicking Risk Score header toggles sort direction', async () => {
    render(<SignalTable onSelectSignal={() => {}} />);
    await waitFor(() => screen.getByText(/3 signals flagged/));
    const header = screen.getByText(/Risk Score/i);
    expect(header).toHaveTextContent('↓');
    fireEvent.click(header);
    expect(header).toHaveTextContent('↑');
  });
});

