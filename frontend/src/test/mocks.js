/**
 * Shared mock factories and helpers for frontend tests.
 */

import { vi } from 'vitest';

// ── Mock the entire api.js module ───────────────────────────────────
vi.mock('../api');

export const mockMetrics = {
  total_at_risk: 150000,
  total_recovered: 87500,
  recovery_rate: 0.5833,
  actions_taken: 42,
  actions_blocked_by_policy: 8,
  escalated_to_human: 3,
  by_root_cause: {
    bank_timeout: { attempted: 12, recovered: 8 },
    otp_failed:   { attempted: 7,  recovered: 4 },
    card_expired: { attempted: 3,  recovered: 0 },
  },
  stopped_reasons: {
    max_attempts_reached: 4,
    cooldown_active: 3,
    fraud_policy_block: 1,
  },
};

export const mockSignals = [
  {
    id: 'sig_001',
    source_type: 'payment',
    source_id: 'pay_abc123',
    risk_score: 0.92,
    root_cause: 'bank_timeout',
    diagnosis_confidence: 1.0,
    diagnosed_at: '2026-08-20T10:00:00',
    source_details: { amount: 12000, currency: 'INR', failure_code: 'bank_timeout', payment_method: 'card', customer_id: 'cust_001' },
  },
  {
    id: 'sig_002',
    source_type: 'checkout',
    source_id: 'sess_xyz456',
    risk_score: 0.65,
    root_cause: 'price_hesitation',
    diagnosis_confidence: 0.70,
    diagnosed_at: '2026-08-20T11:00:00',
    source_details: { cart_value: 5000, stage_reached: 'payment_selection', customer_id: 'cust_002' },
  },
  {
    id: 'sig_003',
    source_type: 'payment',
    source_id: 'pay_def789',
    risk_score: 0.35,
    root_cause: 'card_expired',
    diagnosis_confidence: 1.0,
    diagnosed_at: '2026-08-20T12:00:00',
    source_details: { amount: 3000, currency: 'INR', failure_code: 'card_expired', payment_method: 'card', customer_id: 'cust_003' },
  },
];

export const mockActions = [
  {
    id: 'act_001',
    signal_id: 'sig_001',
    action_type: 'retry_payment',
    attempt_number: 1,
    scheduled_at: '2026-08-20T10:05:00',
    executed_at: '2026-08-20T10:05:01',
    outcome: 'recovered',
    amount_recovered: 12000,
    stopped_reason: null,
    source_id: 'pay_abc123',
    root_cause: 'bank_timeout',
    source_type: 'payment',
  },
  {
    id: 'act_002',
    signal_id: 'sig_002',
    action_type: 'send_nudge',
    attempt_number: 1,
    scheduled_at: '2026-08-20T11:05:00',
    executed_at: '2026-08-20T11:05:01',
    outcome: 'failed',
    amount_recovered: 0,
    stopped_reason: null,
    source_id: 'sess_xyz456',
    root_cause: 'price_hesitation',
    source_type: 'checkout',
  },
  {
    id: 'act_003',
    signal_id: 'sig_003',
    action_type: 'no_action_policy_block',
    attempt_number: 1,
    scheduled_at: '2026-08-20T12:05:00',
    executed_at: '2026-08-20T12:05:00',
    outcome: 'failed',
    amount_recovered: 0,
    stopped_reason: 'fraud_policy_block',
    source_id: 'pay_def789',
    root_cause: 'card_expired',
    source_type: 'payment',
  },
];

export const mockAuditTrail = [
  {
    id: 'audit_001',
    entity_id: 'pay_abc123',
    stage: 'detect',
    explanation: 'Flagged failed payment: amount=₹12000.00, failure_code=bank_timeout, attempt #1, risk_score=0.85',
    timestamp: '2026-08-20T10:00:00',
    metadata: { amount: 12000, failure_code: 'bank_timeout', risk_score: 0.85 },
  },
  {
    id: 'audit_002',
    entity_id: 'pay_abc123',
    stage: 'diagnose',
    explanation: 'Diagnosed payment failure: code=bank_timeout, root_cause=bank_timeout, strategy=retry_soon. Confidence: 1.0',
    timestamp: '2026-08-20T10:01:00',
    metadata: { root_cause: 'bank_timeout', confidence: 1.0 },
  },
  {
    id: 'audit_003',
    entity_id: 'pay_abc123',
    stage: 'decide',
    explanation: 'ACTION APPROVED: retry_payment for root_cause=bank_timeout, risk_score=0.85.',
    timestamp: '2026-08-20T10:02:00',
    metadata: { action_type: 'retry_payment', root_cause: 'bank_timeout' },
  },
  {
    id: 'audit_004',
    entity_id: 'pay_abc123',
    stage: 'execute',
    explanation: '[SIMULATED] ✅ retry_payment: outcome=RECOVERED, amount=₹12000.00',
    timestamp: '2026-08-20T10:03:00',
    metadata: { outcome: 'recovered', amount_recovered: 12000, simulated: true },
  },
];
