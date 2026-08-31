import { useState, useEffect } from 'react';
import { getAuditTrail } from '../api';

const stageIcons = {
  detect: '🔍',
  diagnose: '🔬',
  decide: '⚖️',
  execute: '⚡',
};

const stageDescriptions = {
  detect: 'Signal Detection',
  diagnose: 'Root Cause Diagnosis',
  decide: 'Policy Decision',
  execute: 'Action Execution',
};

const formatTimestamp = (ts) => {
  if (!ts) return '';
  const d = new Date(ts);
  return d.toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
};

export default function AuditDrilldown({ entityId, onBack }) {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!entityId) return;
    setLoading(true);
    setError(null);
    getAuditTrail(entityId)
      .then(setEntries)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [entityId]);

  if (loading) {
    return (
      <div className="loading">
        <div className="loading-spinner"></div>
        <span>Loading audit trail...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="audit-drilldown">
        <div className="audit-header">
          <button className="back-btn" onClick={onBack}>← Back to Signals</button>
        </div>
        <div className="empty-state">
          <div className="empty-state-icon">⚠️</div>
          <h3>Audit Trail Not Found</h3>
          <p>No audit entries found for entity <code style={{ fontFamily: 'var(--font-mono)', color: 'var(--green-400)' }}>{entityId}</code>.</p>
        </div>
      </div>
    );
  }

  // Determine outcome from execute stage
  const executeEntry = entries.find(e => e.stage === 'execute');
  const isRecovered = executeEntry?.metadata?.outcome === 'recovered';
  const isFailed = executeEntry?.metadata?.outcome === 'failed';
  const isEscalated = executeEntry?.metadata?.action_type === 'escalate_human';

  return (
    <div className="audit-drilldown">
      <div className="audit-header">
        <button className="back-btn" onClick={onBack}>← Back to Signals</button>
        <div>
          <h2 style={{ fontSize: '1.1rem', fontWeight: 600 }}>Audit Trail</h2>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            {entityId}
          </div>
        </div>
        <div style={{ marginLeft: 'auto' }}>
          {isRecovered && <span className="badge badge-green">✅ Recovered</span>}
          {isFailed && !isEscalated && <span className="badge badge-red">❌ Failed</span>}
          {isEscalated && <span className="badge badge-amber">👤 Escalated</span>}
          {!executeEntry && <span className="badge badge-gray">⏳ Blocked</span>}
        </div>
      </div>

      {/* Amount at stake */}
      {entries[0]?.metadata && (
        <div className="card" style={{ marginBottom: '24px', display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
          {entries[0].metadata.amount && (
            <div>
              <div className="card-title">Amount</div>
              <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                ₹{entries[0].metadata.amount.toLocaleString('en-IN')}
              </div>
            </div>
          )}
          {entries[0].metadata.cart_value && (
            <div>
              <div className="card-title">Cart Value</div>
              <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                ₹{entries[0].metadata.cart_value.toLocaleString('en-IN')}
              </div>
            </div>
          )}
          {entries[0].metadata.risk_score != null && (
            <div>
              <div className="card-title">Risk Score</div>
              <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--amber-400)', fontFamily: 'var(--font-mono)' }}>
                {entries[0].metadata.risk_score.toFixed(4)}
              </div>
            </div>
          )}
          {executeEntry?.metadata?.amount_recovered > 0 && (
            <div>
              <div className="card-title">Recovered</div>
              <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--green-400)', fontFamily: 'var(--font-mono)' }}>
                ₹{executeEntry.metadata.amount_recovered.toLocaleString('en-IN')}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Timeline */}
      <div className="timeline">
        {entries.map((entry, idx) => {
          const isFinalFail = entry.stage === 'execute' && entry.metadata?.outcome === 'failed';

          return (
            <div className="timeline-node" key={entry.id || idx}>
              <div className={`timeline-dot ${entry.stage} ${isFinalFail ? 'failed' : ''}`}></div>
              <div className={`card timeline-card ${entry.stage}`}>
                <div className="timeline-stage">
                  <div className={`timeline-stage-name ${entry.stage}`}>
                    {stageIcons[entry.stage]} {stageDescriptions[entry.stage] || entry.stage}
                  </div>
                  <div className="timeline-timestamp">
                    {formatTimestamp(entry.timestamp)}
                  </div>
                </div>

                <div className="timeline-explanation">
                  {entry.explanation}
                </div>

                {entry.metadata && Object.keys(entry.metadata).length > 0 && (
                  <div className="timeline-metadata">
                    {Object.entries(entry.metadata).map(([key, value]) => {
                      if (key === 'simulated') return null;
                      const displayVal = typeof value === 'boolean' ? (value ? 'yes' : 'no') :
                                        typeof value === 'number' ? (key.includes('rate') || key === 'confidence' ? `${(value * 100).toFixed(0)}%` : value.toLocaleString()) :
                                        String(value);
                      return (
                        <span className="meta-chip" key={key}>
                          <span className="key">{key.replace(/_/g, ' ')}:</span>
                          <span className="value">{displayVal}</span>
                        </span>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
