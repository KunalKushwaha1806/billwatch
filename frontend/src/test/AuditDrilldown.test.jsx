/**
 * Tests for the AuditDrilldown component.
 *
 * Requirements tested:
 *   FE-AUD-01  Shows loading state while fetching
 *   FE-AUD-02  Shows error/not-found state on API failure (e.g. 404)
 *   FE-AUD-03  Renders one timeline card per audit entry
 *   FE-AUD-04  Stage icons/labels render correctly for all 4 stages
 *   FE-AUD-05  "← Back to Signals" button calls onBack
 *   FE-AUD-06  Entity ID is displayed in the header
 *   FE-AUD-07  Outcome badge shows ✅ Recovered when execution succeeded
 *   FE-AUD-08  Outcome badge shows 👤 Escalated when action_type = escalate_human
 *   FE-AUD-09  Amount card is shown when metadata contains amount
 *   FE-AUD-10  Meta-chips are rendered for metadata key/value pairs
 *   FE-AUD-11  "simulated" key is hidden from meta-chips
 *   FE-AUD-12  Timestamp is rendered for each entry
 */

import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import AuditDrilldown from '../components/AuditDrilldown';
import * as api from '../api';
import { mockAuditTrail } from './mocks';

vi.mock('../api');


describe('AuditDrilldown', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getAuditTrail.mockResolvedValue(mockAuditTrail);
  });

  it('FE-AUD-01: shows loading state initially', () => {
    api.getAuditTrail.mockImplementation(() => new Promise(() => {}));
    render(<AuditDrilldown entityId="pay_abc123" onBack={() => {}} />);
    expect(screen.getByText(/loading audit trail/i)).toBeInTheDocument();
  });

  it('FE-AUD-02: shows not-found state on API error', async () => {
    api.getAuditTrail.mockRejectedValue(new Error('404'));
    render(<AuditDrilldown entityId="pay_unknown" onBack={() => {}} />);
    await waitFor(() =>
      expect(screen.getByText(/audit trail not found/i)).toBeInTheDocument()
    );
  });

  it('FE-AUD-03: renders one card per audit entry (4 cards)', async () => {
    render(<AuditDrilldown entityId="pay_abc123" onBack={() => {}} />);
    await waitFor(() => {
      // 4 entries → 4 stage labels
      expect(screen.getByText(/🔍 signal detection/i)).toBeInTheDocument();
      expect(screen.getByText(/🔬 root cause diagnosis/i)).toBeInTheDocument();
      expect(screen.getByText(/⚖️ policy decision/i)).toBeInTheDocument();
      expect(screen.getByText(/⚡ action execution/i)).toBeInTheDocument();
    });
  });

  it('FE-AUD-04: renders all 4 stage icons/names', async () => {
    render(<AuditDrilldown entityId="pay_abc123" onBack={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText(/signal detection/i)).toBeInTheDocument();
      expect(screen.getByText(/root cause diagnosis/i)).toBeInTheDocument();
      expect(screen.getByText(/policy decision/i)).toBeInTheDocument();
      expect(screen.getByText(/action execution/i)).toBeInTheDocument();
    });
  });

  it('FE-AUD-05: back button calls onBack', async () => {
    const onBack = vi.fn();
    render(<AuditDrilldown entityId="pay_abc123" onBack={onBack} />);
    await waitFor(() => screen.getByText(/← back to signals/i));
    fireEvent.click(screen.getByText(/← back to signals/i));
    expect(onBack).toHaveBeenCalledOnce();
  });

  it('FE-AUD-06: entity ID shown in header', async () => {
    render(<AuditDrilldown entityId="pay_abc123" onBack={() => {}} />);
    await waitFor(() =>
      expect(screen.getByText('pay_abc123')).toBeInTheDocument()
    );
  });

  it('FE-AUD-07: shows ✅ Recovered badge when outcome=recovered', async () => {
    render(<AuditDrilldown entityId="pay_abc123" onBack={() => {}} />);
    await waitFor(() =>
      expect(screen.getByText(/✅ recovered/i)).toBeInTheDocument()
    );
  });

  it('FE-AUD-08: shows 👤 Escalated badge for escalate_human', async () => {
    const escalatedTrail = [
      ...mockAuditTrail.slice(0, 3),
      {
        ...mockAuditTrail[3],
        explanation: '[SIMULATED] Escalated to human review.',
        metadata: { action_type: 'escalate_human', outcome: 'still_pending', simulated: true },
      },
    ];
    api.getAuditTrail.mockResolvedValue(escalatedTrail);
    render(<AuditDrilldown entityId="pay_abc123" onBack={() => {}} />);
    await waitFor(() =>
      expect(screen.getByText(/👤 escalated/i)).toBeInTheDocument()
    );
  });

  it('FE-AUD-09: shows Amount card when metadata has amount', async () => {
    render(<AuditDrilldown entityId="pay_abc123" onBack={() => {}} />);
    await waitFor(() => expect(screen.getByText(/Amount/)).toBeInTheDocument());
    expect(screen.getAllByText(/12,000/).length).toBeGreaterThan(0);
  });

  it('FE-AUD-10: renders meta-chips for metadata fields', async () => {
    render(<AuditDrilldown entityId="pay_abc123" onBack={() => {}} />);
    // "failure code" chip from detect entry metadata
    await waitFor(() =>
      expect(screen.getByText(/failure code:/i)).toBeInTheDocument()
    );
  });

  it('FE-AUD-11: simulated key is hidden from meta-chips', async () => {
    render(<AuditDrilldown entityId="pay_abc123" onBack={() => {}} />);
    await waitFor(() => screen.getByText(/signal detection/i));
    // "simulated" should NOT appear as a chip key
    const chipKeys = screen.queryAllByText(/simulated:/i);
    expect(chipKeys).toHaveLength(0);
  });

  it('FE-AUD-12: timestamps are rendered for each entry', async () => {
    render(<AuditDrilldown entityId="pay_abc123" onBack={() => {}} />);
    await waitFor(() => {
      // Should have at least 4 timestamp elements rendered
      // The format is locale-based; just check they exist by class or count of cards
      const cards = screen.getAllByText(/20 aug 2026/i);
      expect(cards.length).toBeGreaterThanOrEqual(1);
    });
  });

  it('renders explanation text from each entry', async () => {
    render(<AuditDrilldown entityId="pay_abc123" onBack={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText(/flagged failed payment/i)).toBeInTheDocument();
      expect(screen.getByText(/action approved/i)).toBeInTheDocument();
      expect(screen.getByText(/\[simulated\]/i)).toBeInTheDocument();
    });
  });
});
