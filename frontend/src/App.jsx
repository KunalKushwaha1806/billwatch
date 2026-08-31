import { useState, useCallback, useEffect } from 'react';
import Dashboard from './components/Dashboard';
import SignalTable from './components/SignalTable';
import AuditDrilldown from './components/AuditDrilldown';
import ActionsView from './components/ActionsView';
import { loadBatch, runPipeline } from './api';

const VIEWS = {
  DASHBOARD: 'dashboard',
  SIGNALS:   'signals',
  ACTIONS:   'actions',
  AUDIT:     'audit',
};

export default function App() {
  const [view, setView] = useState(VIEWS.DASHBOARD);
  const [auditEntityId, setAuditEntityId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState(null);
  const [toastType, setToastType] = useState('info'); // 'info' | 'error' | 'success'
  const [refreshKey, setRefreshKey] = useState(0);
  const [lastRunAt, setLastRunAt] = useState(null);
  const [clock, setClock] = useState(new Date());

  // Live clock tick
  useEffect(() => {
    const id = setInterval(() => setClock(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const showToast = (message, type = 'info', duration = 4500) => {
    setToast(message);
    setToastType(type);
    setTimeout(() => setToast(null), duration);
  };

  const handleLoadBatch = useCallback(async () => {
    setLoading(true);
    try {
      const res = await loadBatch();
      showToast(`✅ ${res.message}`, 'success');
      setRefreshKey((k) => k + 1);
    } catch (err) {
      showToast(`❌ Failed to load batch: ${err.message}`, 'error');
    } finally {
      setLoading(false);
    }
  }, []);

  const handleRunPipeline = useCallback(async () => {
    setLoading(true);
    try {
      const res = await runPipeline();
      showToast(`⚡ ${res.message}`, 'success');
      setRefreshKey((k) => k + 1);
      setLastRunAt(new Date());
    } catch (err) {
      showToast(`❌ Pipeline failed: ${err.message}`, 'error');
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSelectSignal = (entityId) => {
    setAuditEntityId(entityId);
    setView(VIEWS.AUDIT);
  };

  const handleBackFromAudit = () => {
    // Return to wherever the user navigated from
    setView(prevAuditOrigin || VIEWS.SIGNALS);
    setAuditEntityId(null);
  };

  const [prevAuditOrigin, setPrevAuditOrigin] = useState(VIEWS.SIGNALS);

  const navigateToAudit = (entityId, origin = VIEWS.SIGNALS) => {
    setPrevAuditOrigin(origin);
    setAuditEntityId(entityId);
    setView(VIEWS.AUDIT);
  };

  const formatClockDiff = (date) => {
    if (!date) return null;
    const secs = Math.floor((clock - date) / 1000);
    if (secs < 60) return `${secs}s ago`;
    const mins = Math.floor(secs / 60);
    if (mins < 60) return `${mins}m ago`;
    return `${Math.floor(mins / 60)}h ago`;
  };

  return (
    <div className="app">
      {/* Header */}
      <header className="app-header">
        <div className="app-logo">
          <div className="app-logo-icon">₹</div>
          <div>
            <h1>BillWatch</h1>
            <div className="subtitle">AI Revenue Recovery Agent</div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="nav-tabs">
          <button
            className={`nav-tab ${view === VIEWS.DASHBOARD ? 'active' : ''}`}
            onClick={() => setView(VIEWS.DASHBOARD)}
          >
            📊 Dashboard
          </button>
          <button
            className={`nav-tab ${view === VIEWS.SIGNALS ? 'active' : ''}`}
            onClick={() => setView(VIEWS.SIGNALS)}
          >
            🔍 Signals
          </button>
          <button
            className={`nav-tab ${view === VIEWS.ACTIONS ? 'active' : ''}`}
            onClick={() => setView(VIEWS.ACTIONS)}
          >
            ⚡ Actions
          </button>
          {view === VIEWS.AUDIT && (
            <button className="nav-tab active">
              📋 Audit Trail
            </button>
          )}
        </nav>

        {/* Live clock */}
        <div className="header-clock">
          <span className="live-dot" />
          {clock.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
        </div>
      </header>

      {/* Control Bar */}
      <div className="control-bar">
        <button
          className="btn btn-secondary"
          onClick={handleLoadBatch}
          disabled={loading}
        >
          {loading ? <span className="spinner"></span> : '📦'}
          Load Synthetic Data
        </button>
        <button
          className="btn btn-primary"
          onClick={handleRunPipeline}
          disabled={loading}
        >
          {loading ? <span className="spinner"></span> : '⚡'}
          Run Recovery Pipeline
        </button>
        {lastRunAt && (
          <div className="last-run-chip">
            <span className="status-dot recovered" style={{ marginRight: 6 }} />
            Last run: {formatClockDiff(lastRunAt)}
          </div>
        )}
      </div>

      {/* View Content */}
      {view === VIEWS.DASHBOARD && <Dashboard key={`dash-${refreshKey}`} />}
      {view === VIEWS.SIGNALS && (
        <SignalTable
          key={`sig-${refreshKey}`}
          onSelectSignal={(id) => navigateToAudit(id, VIEWS.SIGNALS)}
        />
      )}
      {view === VIEWS.ACTIONS && (
        <ActionsView
          key={`act-${refreshKey}`}
          onSelectEntity={(id) => navigateToAudit(id, VIEWS.ACTIONS)}
        />
      )}
      {view === VIEWS.AUDIT && (
        <AuditDrilldown entityId={auditEntityId} onBack={handleBackFromAudit} />
      )}

      {/* Toast */}
      {toast && <div className={`toast toast-${toastType}`}>{toast}</div>}
    </div>
  );
}
