import { useState, useEffect, useRef } from 'react';
import { getMetricsSummary } from '../api';

const formatCurrency = (val) => {
  if (val == null) return '₹0';
  return '₹' + val.toLocaleString('en-IN', { maximumFractionDigits: 0 });
};

const formatPercent = (val) => {
  if (val == null) return '0%';
  return (val * 100).toFixed(1) + '%';
};

/** Animated count-up hook */
function useCountUp(target, duration = 1200) {
  const [val, setVal] = useState(0);
  const startRef = useRef(null);
  useEffect(() => {
    if (target == null || target === 0) { setVal(0); return; }
    let raf;
    const animate = (ts) => {
      if (!startRef.current) startRef.current = ts;
      const elapsed = ts - startRef.current;
      const progress = Math.min(elapsed / duration, 1);
      // Ease out cubic
      const ease = 1 - Math.pow(1 - progress, 3);
      setVal(target * ease);
      if (progress < 1) raf = requestAnimationFrame(animate);
    };
    raf = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);
  return val;
}

/** Horizontal stacked bar showing recovered vs failed vs pending */
function RecoveryBar({ recovered, total }) {
  const pct = total > 0 ? (recovered / total) * 100 : 0;
  return (
    <div className="recovery-bar-track">
      <div
        className="recovery-bar-fill"
        style={{ width: `${pct}%` }}
        title={`${pct.toFixed(1)}% recovered`}
      />
    </div>
  );
}

/** Small sparkline-style bar chart for root cause breakdown */
function RootCauseChart({ data }) {
  const entries = Object.entries(data);
  if (entries.length === 0) return null;
  const maxAttempted = Math.max(...entries.map(([, d]) => d.attempted), 1);

  return (
    <div className="root-cause-chart">
      {entries.map(([cause, d]) => {
        const widthPct = (d.attempted / maxAttempted) * 100;
        const recPct = d.attempted > 0 ? (d.recovered / d.attempted) * 100 : 0;
        return (
          <div className="rcc-row" key={cause}>
            <div className="rcc-label">{cause.replace(/_/g, ' ')}</div>
            <div className="rcc-bar-wrap">
              <div className="rcc-bar-bg" style={{ width: `${widthPct}%` }}>
                <div className="rcc-bar-rec" style={{ width: `${recPct}%` }} />
              </div>
            </div>
            <div className="rcc-stats">
              <span className="rcc-rec">{d.recovered}</span>
              <span className="rcc-sep">/</span>
              <span className="rcc-att">{d.attempted}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

/** Donut/ring chart for blocking reasons */
function BlockingPie({ data }) {
  const entries = Object.entries(data);
  if (entries.length === 0) return null;

  const total = entries.reduce((s, [, v]) => s + v, 0);
  const COLORS = ['var(--amber-400)', 'var(--red-400)', 'var(--blue-400)', 'var(--purple-400)', 'var(--text-muted)'];

  let cumulative = 0;
  const segments = entries.map(([label, count], i) => {
    const pct = (count / total) * 100;
    const seg = { label: label.replace(/_/g, ' '), count, pct, color: COLORS[i % COLORS.length], offset: cumulative };
    cumulative += pct;
    return seg;
  });

  // SVG circle: r=40, circumference ≈ 251.3
  const R = 40;
  const C = 2 * Math.PI * R;

  return (
    <div className="blocking-pie-wrap">
      <svg width="100" height="100" viewBox="0 0 100 100" className="blocking-pie-svg">
        <circle cx="50" cy="50" r={R} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="14" />
        {segments.map((seg, i) => (
          <circle
            key={i}
            cx="50" cy="50" r={R}
            fill="none"
            stroke={seg.color}
            strokeWidth="14"
            strokeDasharray={`${(seg.pct / 100) * C} ${C}`}
            strokeDashoffset={-((seg.offset / 100) * C)}
            style={{ transition: 'stroke-dasharray 0.6s ease', transformOrigin: 'center', transform: 'rotate(-90deg)' }}
          />
        ))}
      </svg>
      <div className="blocking-pie-legend">
        {segments.map((seg, i) => (
          <div className="pie-legend-item" key={i}>
            <span className="pie-legend-dot" style={{ background: seg.color }} />
            <span className="pie-legend-label">{seg.label}</span>
            <span className="pie-legend-val" style={{ color: seg.color }}>{seg.count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchMetrics = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getMetricsSummary();
      setMetrics(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchMetrics(); }, []);

  const animatedRecovered = useCountUp(metrics?.total_recovered || 0);
  const animatedAtRisk = useCountUp(metrics?.total_at_risk || 0);

  if (loading) {
    return (
      <div className="loading">
        <div className="loading-spinner"></div>
        <span>Loading metrics...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">⚠️</div>
        <h3>No Data Available</h3>
        <p>Load a batch and run the pipeline to see recovery metrics. Use the buttons above to get started.</p>
      </div>
    );
  }

  if (!metrics || metrics.total_at_risk === 0) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">📊</div>
        <h3>No Signals Detected</h3>
        <p>Load a batch and run the pipeline to see recovery metrics.</p>
      </div>
    );
  }

  const rootCauses = metrics.by_root_cause || {};
  const stoppedReasons = metrics.stopped_reasons || {};

  return (
    <div>
      {/* Simulation Banner */}
      <div className="sim-banner">
        ⚡ All recovery actions are simulated — no real payments or messages are processed
      </div>

      {/* Hero: Total Recovered */}
      <div className="card hero-stat">
        <div className="stat-value">
          {formatCurrency(animatedRecovered)}
        </div>
        <div className="stat-label">Total Revenue Recovered (Simulated)</div>
        <div className="recovery-rate">
          {formatPercent(metrics.recovery_rate)} recovery rate from {formatCurrency(animatedAtRisk)} at risk
        </div>
        <RecoveryBar recovered={metrics.total_recovered} total={metrics.total_at_risk} />
      </div>

      {/* Stats Grid */}
      <div className="stats-grid">
        <div className="card stat-card red">
          <div className="card-title">At Risk</div>
          <div className="stat-value red">{formatCurrency(metrics.total_at_risk)}</div>
          <div className="stat-label">Total flagged amount</div>
        </div>

        <div className="card stat-card green">
          <div className="card-title">Recovered</div>
          <div className="stat-value green">{formatCurrency(metrics.total_recovered)}</div>
          <div className="stat-label">Successfully recovered</div>
        </div>

        <div className="card stat-card blue">
          <div className="card-title">Actions Taken</div>
          <div className="stat-value blue">{metrics.actions_taken}</div>
          <div className="stat-label">Recovery actions executed</div>
        </div>

        <div className="card stat-card amber">
          <div className="card-title">Blocked by Policy</div>
          <div className="stat-value amber">{metrics.actions_blocked_by_policy}</div>
          <div className="stat-label">Stopped by stopping rules</div>
        </div>

        <div className="card stat-card purple">
          <div className="card-title">Escalated to Human</div>
          <div className="stat-value purple">{metrics.escalated_to_human}</div>
          <div className="stat-label">Low-confidence cases</div>
        </div>
      </div>

      {/* Charts Grid */}
      <div className="breakdown-grid">
        {/* Root Cause Chart */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">Recovery by Root Cause</div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
              <span style={{ color: 'var(--green-400)' }}>■</span> recovered &nbsp;
              <span style={{ color: 'rgba(255,255,255,0.08)' }}>■</span> attempted
            </div>
          </div>
          <RootCauseChart data={rootCauses} />
        </div>

        {/* Blocking Pie */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">Stopping Rule Breakdown</div>
          </div>
          {Object.entries(stoppedReasons).length > 0 ? (
            <BlockingPie data={stoppedReasons} />
          ) : (
            <div style={{ color: 'var(--text-muted)', fontSize: '0.875rem', padding: '8px 0' }}>
              No actions were blocked
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
