import { useState, useEffect } from 'react';
import { getSignals } from '../api';

const outcomeColor = (cause) => {
  const colors = {
    bank_timeout: 'blue',
    otp_failed: 'amber',
    network_error: 'blue',
    insufficient_funds: 'red',
    card_expired: 'red',
    payment_friction: 'amber',
    price_hesitation: 'amber',
    shipping_cost_surprise: 'amber',
    distraction_timeout: 'gray',
    unknown: 'gray',
  };
  return colors[cause] || 'gray';
};

const riskLevel = (score) => {
  if (score >= 0.7) return 'high';
  if (score >= 0.4) return 'medium';
  return 'low';
};

export default function SignalTable({ onSelectSignal }) {
  const [signals, setSignals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sortKey, setSortKey] = useState('risk_score');
  const [sortDir, setSortDir] = useState('desc');
  const [filterType, setFilterType] = useState('');
  const [search, setSearch] = useState('');

  useEffect(() => {
    setLoading(true);
    getSignals(filterType || undefined)
      .then(setSignals)
      .catch(() => setSignals([]))
      .finally(() => setLoading(false));
  }, [filterType]);

  const handleSort = (key) => {
    if (sortKey === key) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  const filtered = signals.filter(s => {
    if (!search) return true;
    const q = search.toLowerCase();
    const details = s.source_details || {};
    return (
      (s.source_id || '').toLowerCase().includes(q) ||
      (s.root_cause || '').toLowerCase().includes(q) ||
      (details.payment_method || '').toLowerCase().includes(q) ||
      (details.failure_code || '').toLowerCase().includes(q) ||
      (details.stage_reached || '').toLowerCase().includes(q) ||
      (details.customer_id || '').toLowerCase().includes(q)
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

  if (loading) {
    return (
      <div className="loading">
        <div className="loading-spinner"></div>
        <span>Loading signals...</span>
      </div>
    );
  }

  if (signals.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">🔍</div>
        <h3>No Signals Detected</h3>
        <p>Run the pipeline to detect at-risk payments and checkouts.</p>
      </div>
    );
  }

  const thClass = (key) => `${sortKey === key ? 'sorted' : ''}`;
  const sortArrow = (key) => sortKey === key ? (sortDir === 'asc' ? ' ↑' : ' ↓') : '';

  return (
    <div>
      {/* Search bar */}
      <div className="search-wrapper" style={{ marginBottom: '16px' }}>
        <span className="search-icon">🔍</span>
        <input
          className="search-input"
          type="text"
          placeholder="Search by source ID, root cause, method..."
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        {search && (
          <button className="search-clear" onClick={() => setSearch('')}>✕</button>
        )}
      </div>

      {/* Filter tabs */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '20px', flexWrap: 'wrap', alignItems: 'center' }}>
        {['', 'payment', 'checkout'].map((type) => (
          <button
            key={type}
            className={`btn ${filterType === type ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setFilterType(type)}
            style={{ padding: '6px 16px', fontSize: '0.8rem' }}
          >
            {type === '' ? 'All Signals' : type === 'payment' ? '💳 Payments' : '🛒 Checkouts'}
          </button>
        ))}
        <div style={{ marginLeft: 'auto', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
          {filtered.length !== signals.length
            ? `${filtered.length} of ${signals.length} signal${signals.length !== 1 ? 's' : ''}`
            : `${signals.length} signal${signals.length !== 1 ? 's' : ''} flagged`
          }
        </div>
      </div>

      <div className="table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th className={thClass('source_type')} onClick={() => handleSort('source_type')}>
                Type{sortArrow('source_type')}
              </th>
              <th className={thClass('source_id')} onClick={() => handleSort('source_id')}>
                Source ID{sortArrow('source_id')}
              </th>
              <th className={thClass('risk_score')} onClick={() => handleSort('risk_score')}>
                Risk Score{sortArrow('risk_score')}
              </th>
              <th className={thClass('root_cause')} onClick={() => handleSort('root_cause')}>
                Root Cause{sortArrow('root_cause')}
              </th>
              <th className={thClass('diagnosis_confidence')} onClick={() => handleSort('diagnosis_confidence')}>
                Confidence{sortArrow('diagnosis_confidence')}
              </th>
              <th>Amount</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((signal) => {
              const details = signal.source_details || {};
              const amount = details.amount || details.cart_value;
              const level = riskLevel(signal.risk_score);

              return (
                <tr
                  key={signal.id}
                  onClick={() => onSelectSignal(signal.source_id)}
                  title="Click to view audit trail"
                >
                  <td>
                    <span className={`badge ${signal.source_type === 'payment' ? 'badge-blue' : 'badge-amber'}`}>
                      {signal.source_type === 'payment' ? '💳 Payment' : '🛒 Checkout'}
                    </span>
                  </td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>
                    {signal.source_id}
                  </td>
                  <td>
                    <div className="risk-bar-container">
                      <div className="risk-bar">
                        <div
                          className={`risk-bar-fill ${level}`}
                          style={{ width: `${signal.risk_score * 100}%` }}
                        ></div>
                      </div>
                      <span className={`risk-score-value`} style={{
                        color: level === 'high' ? 'var(--red-400)' : level === 'medium' ? 'var(--amber-400)' : 'var(--green-400)'
                      }}>
                        {signal.risk_score.toFixed(2)}
                      </span>
                    </div>
                  </td>
                  <td>
                    <span className={`badge badge-${outcomeColor(signal.root_cause)}`}>
                      {(signal.root_cause || 'unknown').replace(/_/g, ' ')}
                    </span>
                  </td>
                  <td>
                    {signal.diagnosis_confidence != null ? (
                      <span style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '0.8rem',
                        color: signal.diagnosis_confidence >= 0.7 ? 'var(--green-400)' :
                               signal.diagnosis_confidence >= 0.5 ? 'var(--amber-400)' : 'var(--red-400)'
                      }}>
                        {(signal.diagnosis_confidence * 100).toFixed(0)}%
                      </span>
                    ) : (
                      <span style={{ color: 'var(--text-muted)' }}>—</span>
                    )}
                  </td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                    {amount ? `₹${amount.toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : '—'}
                  </td>
                  <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                    {signal.source_type === 'payment'
                      ? `${details.payment_method || ''} · ${details.failure_code || ''}`
                      : `stage: ${details.stage_reached || ''}`
                    }
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
