import { useState, useEffect, useCallback } from 'react';
import { getActions } from '../api';

const formatCurrency = (val) => {
  if (!val) return '—';
  return '₹' + Number(val).toLocaleString('en-IN', { maximumFractionDigits: 0 });
};

const formatTime = (ts) => {
  if (!ts) return '—';
  const d = new Date(ts);
  return d.toLocaleString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
};

const ACTION_TYPE_META = {
  retry_payment:           { label: 'Retry Payment',    icon: '🔄', color: 'blue' },
  send_nudge:              { label: 'Send Nudge',        icon: '💬', color: 'purple' },
  escalate_human:          { label: 'Escalate to Human',icon: '👤', color: 'amber' },
  no_action_policy_block:  { label: 'Policy Block',      icon: '🚫', color: 'red' },
};

const OUTCOME_META = {
  recovered:     { label: 'Recovered',     color: 'green', icon: '✅' },
  failed:        { label: 'Failed',        color: 'red',   icon: '❌' },
  still_pending: { label: 'Pending',       color: 'amber', icon: '⏳' },
};

const STOPPED_REASON_LABELS = {
  max_attempts_reached:  'Max Attempts',
  cooldown_active:       'Cooldown Active',
  low_confidence_diagnosis: 'Low Confidence',
  fraud_policy_block:    'Fraud Block',
};

export default function ActionsView({ onSelectEntity }) {
  const [actions, setActions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [outcomeFilter, setOutcomeFilter] = useState('');
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState('scheduled_at');
  const [sortDir, setSortDir] = useState('desc');

  const fetchActions = useCallback(() => {
    setLoading(true);
    getActions(outcomeFilter || undefined)
      .then(setActions)
      .catch(() => setActions([]))
      .finally(() => setLoading(false));
  }, [outcomeFilter]);

  useEffect(() => { fetchActions(); }, [fetchActions]);

  const handleSort = (key) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('desc'); }
  };

  const filtered = actions.filter(a => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      (a.source_id || '').toLowerCase().includes(q) ||
      (a.id || '').toLowerCase().includes(q) ||
      (a.root_cause || '').toLowerCase().includes(q) ||
      (a.action_type || '').toLowerCase().includes(q)
    );
  });

  const sorted = [...filtered].sort((a, b) => {
    let aVal = a[sortKey];
    let bVal = b[sortKey];
    if (typeof aVal === 'string') aVal = aVal.toLowerCase();
    if (typeof bVal === 'string') bVal = bVal.toLowerCase();
    if (aVal == null) return 1;
    if (bVal == null) return -1;
    if (aVal < bVal) return sortDir === 'asc' ? -1 : 1;
    if (aVal > bVal) return sortDir === 'asc' ? 1 : -1;
    return 0;
  });

  // Summary stats
  const totalRecovered = actions
    .filter(a => a.outcome === 'recovered')
    .reduce((sum, a) => sum + (a.amount_recovered || 0), 0);
  const recoveredCount = actions.filter(a => a.outcome === 'recovered').length;
  const failedCount = actions.filter(a => a.outcome === 'failed' && a.action_type !== 'no_action_policy_block').length;
  const blockedCount = actions.filter(a => a.action_type === 'no_action_policy_block').length;

  const handleExportCSV = () => {
    const headers = ['ID', 'Source ID', 'Action Type', 'Root Cause', 'Outcome', 'Amount Recovered', 'Stopped Reason', 'Scheduled At', 'Executed At'];
    const rows = sorted.map(a => [
      a.id, a.source_id, a.action_type, a.root_cause || '',
      a.outcome || '', a.amount_recovered || 0,
      a.stopped_reason || '', a.scheduled_at || '', a.executed_at || '',
    ]);
    const csv = [headers, ...rows].map(r => r.map(v => `"${v}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url; link.download = 'billwatch_actions.csv';
    link.click(); URL.revokeObjectURL(url);
  };

  const thClass = (key) => sortKey === key ? 'sorted' : '';
  const sortArrow = (key) => sortKey === key ? (sortDir === 'asc' ? ' ↑' : ' ↓') : '';

  if (loading) {
    return (
      <div className="loading">
        <div className="loading-spinner"></div>
        <span>Loading recovery actions...</span>
      </div>
    );
  }

  if (actions.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">⚡</div>
        <h3>No Recovery Actions Yet</h3>
        <p>Load a batch and run the pipeline to generate recovery actions.</p>
      </div>
    );
  }

  return (
    <div>
      {/* Mini Summary Row */}
      <div className="actions-summary-row">
        <div className="actions-summary-chip green">
          <span className="actions-summary-icon">✅</span>
          <div>
            <div className="actions-summary-val">{formatCurrency(totalRecovered)}</div>
            <div className="actions-summary-label">{recoveredCount} Recovered</div>
          </div>
        </div>
        <div className="actions-summary-chip red">
          <span className="actions-summary-icon">❌</span>
          <div>
            <div className="actions-summary-val">{failedCount}</div>
            <div className="actions-summary-label">Failed</div>
          </div>
        </div>
        <div className="actions-summary-chip amber">
          <span className="actions-summary-icon">🚫</span>
          <div>
            <div className="actions-summary-val">{blockedCount}</div>
            <div className="actions-summary-label">Policy Blocked</div>
          </div>
        </div>
        <div className="actions-summary-chip blue">
          <span className="actions-summary-icon">📋</span>
          <div>
            <div className="actions-summary-val">{actions.length}</div>
            <div className="actions-summary-label">Total Actions</div>
          </div>
        </div>
      </div>

      {/* Toolbar */}
      <div className="actions-toolbar">
        <div className="search-wrapper">
          <span className="search-icon">🔍</span>
          <input
            className="search-input"
            type="text"
            placeholder="Search by ID, source, cause..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          {search && (
            <button className="search-clear" onClick={() => setSearch('')}>✕</button>
          )}
        </div>

        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {['', 'recovered', 'failed', 'still_pending'].map(outcome => (
            <button
              key={outcome}
              className={`btn ${outcomeFilter === outcome ? 'btn-primary' : 'btn-secondary'}`}
              style={{ padding: '6px 14px', fontSize: '0.78rem' }}
              onClick={() => setOutcomeFilter(outcome)}
            >
              {outcome === '' ? 'All' :
               outcome === 'recovered' ? '✅ Recovered' :
               outcome === 'failed' ? '❌ Failed' : '⏳ Pending'}
            </button>
          ))}
        </div>

        <button className="btn btn-secondary" onClick={handleExportCSV} style={{ marginLeft: 'auto', padding: '6px 14px', fontSize: '0.78rem' }}>
          📥 Export CSV
        </button>
      </div>

      <div style={{ color: 'var(--text-muted)', fontSize: '0.78rem', marginBottom: '12px' }}>
        Showing {sorted.length} of {actions.length} actions
      </div>

      <div className="table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th className={thClass('action_type')} onClick={() => handleSort('action_type')}>
                Action{sortArrow('action_type')}
              </th>
              <th className={thClass('source_id')} onClick={() => handleSort('source_id')}>
                Source ID{sortArrow('source_id')}
              </th>
              <th className={thClass('root_cause')} onClick={() => handleSort('root_cause')}>
                Root Cause{sortArrow('root_cause')}
              </th>
              <th className={thClass('attempt_number')} onClick={() => handleSort('attempt_number')}>
                Attempt{sortArrow('attempt_number')}
              </th>
              <th className={thClass('outcome')} onClick={() => handleSort('outcome')}>
                Outcome{sortArrow('outcome')}
              </th>
              <th className={thClass('amount_recovered')} onClick={() => handleSort('amount_recovered')}>
                Recovered{sortArrow('amount_recovered')}
              </th>
              <th className={thClass('stopped_reason')} onClick={() => handleSort('stopped_reason')}>
                Stop Reason{sortArrow('stopped_reason')}
              </th>
              <th className={thClass('scheduled_at')} onClick={() => handleSort('scheduled_at')}>
                Scheduled{sortArrow('scheduled_at')}
              </th>
            </tr>
          </thead>
          <tbody>
            {sorted.map(action => {
              const actionMeta = ACTION_TYPE_META[action.action_type] || { label: action.action_type, icon: '⚙️', color: 'gray' };
              const outcomeMeta = action.outcome ? OUTCOME_META[action.outcome] : null;
              const stoppedLabel = action.stopped_reason ? STOPPED_REASON_LABELS[action.stopped_reason] || action.stopped_reason.replace(/_/g, ' ') : null;

              return (
                <tr
                  key={action.id}
                  onClick={() => onSelectEntity && onSelectEntity(action.source_id)}
                  title="Click to view audit trail"
                >
                  <td>
                    <span className={`badge badge-${actionMeta.color}`}>
                      {actionMeta.icon} {actionMeta.label}
                    </span>
                  </td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.78rem' }}>
                    {action.source_id}
                  </td>
                  <td>
                    <span className="badge badge-gray" style={{ fontSize: '0.72rem' }}>
                      {(action.root_cause || 'unknown').replace(/_/g, ' ')}
                    </span>
                  </td>
                  <td style={{ textAlign: 'center' }}>
                    <span className="attempt-badge">#{action.attempt_number}</span>
                  </td>
                  <td>
                    {outcomeMeta ? (
                      <span className={`badge badge-${outcomeMeta.color}`}>
                        {outcomeMeta.icon} {outcomeMeta.label}
                      </span>
                    ) : (
                      <span style={{ color: 'var(--text-muted)' }}>—</span>
                    )}
                  </td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: action.amount_recovered > 0 ? 'var(--green-400)' : 'var(--text-muted)' }}>
                    {formatCurrency(action.amount_recovered)}
                  </td>
                  <td>
                    {stoppedLabel ? (
                      <span className="badge badge-amber" style={{ fontSize: '0.7rem' }}>
                        {stoppedLabel}
                      </span>
                    ) : (
                      <span style={{ color: 'var(--text-muted)' }}>—</span>
                    )}
                  </td>
                  <td style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', whiteSpace: 'nowrap' }}>
                    {formatTime(action.scheduled_at)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
