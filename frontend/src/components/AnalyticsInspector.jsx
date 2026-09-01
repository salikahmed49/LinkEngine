import React, { useEffect, useState, useRef } from 'react';
import {
  Activity,
  Search,
  RefreshCw,
  Globe,
  Monitor,
  Clock,
  AlertCircle,
  ExternalLink,
  Radio,
} from 'lucide-react';
import { getLinkAnalytics } from '../services/api';

function extractSlug(input) {
  if (!input) return '';
  let str = input.trim();
  // Remove protocol and domain if full URL was pasted
  if (str.includes('/')) {
    const parts = str.split('/').filter(Boolean);
    return parts[parts.length - 1] || '';
  }
  return str.replace(/^\/+/, '');
}

export default function AnalyticsInspector({ initialCode = '', onCodeChange }) {
  const [queryCode, setQueryCode] = useState(initialCode || 'torvalds');
  const [analytics, setAnalytics] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const activeSlugRef = useRef(queryCode);
  activeSlugRef.current = queryCode;

  const fetchAnalytics = async (codeToFetch, silent = false) => {
    const slug = extractSlug(codeToFetch || queryCode);
    if (!slug) return;

    if (!silent) setIsLoading(true);
    setError(null);

    try {
      const data = await getLinkAnalytics(slug);
      setAnalytics(data);
    } catch (err) {
      if (!silent) {
        setAnalytics(null);
        setError(err.message || 'Failed to fetch telemetry');
      }
    } finally {
      if (!silent) setIsLoading(false);
    }
  };

  // Sync with initialCode from parent (e.g. when user clicks "Inspect Stream" on a created link)
  useEffect(() => {
    if (initialCode) {
      const slug = extractSlug(initialCode);
      setQueryCode(slug);
      fetchAnalytics(slug);
    } else {
      fetchAnalytics('torvalds');
    }
  }, [initialCode]);

  // Live Auto-Refresh polling every 3 seconds
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      if (activeSlugRef.current) {
        fetchAnalytics(activeSlugRef.current, true);
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [autoRefresh]);

  const handleSearch = (e) => {
    e.preventDefault();
    const slug = extractSlug(queryCode);
    if (!slug) return;
    setQueryCode(slug);
    fetchAnalytics(slug);
    if (onCodeChange) onCodeChange(slug);
  };

  const handleQuickLookup = (code) => {
    const slug = extractSlug(code);
    setQueryCode(slug);
    fetchAnalytics(slug);
    if (onCodeChange) onCodeChange(slug);
  };

  // Helper to compute percentage for distribution bars
  const totalReferrerClicks =
    analytics?.top_referrers?.reduce((sum, item) => sum + item.count, 0) || 1;
  const totalPlatformClicks =
    analytics?.top_user_agents?.reduce((sum, item) => sum + item.count, 0) || 1;

  return (
    <div className="surface-panel workbench-panel">
      {/* Workbench Header */}
      <div className="workbench-top">
        <div className="workbench-title-group">
          <Activity size={16} strokeWidth={2} className="text-cyan" />
          <h2 className="panel-heading">Stream Telemetry Workbench</h2>
        </div>

        <div className="workbench-controls">
          <button
            type="button"
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`btn-auto-refresh ${autoRefresh ? 'active' : ''}`}
            title="Toggle real-time stream ingestion polling"
          >
            <Radio size={12} strokeWidth={2.5} className={autoRefresh ? 'text-emerald' : ''} />
            <span>{autoRefresh ? 'Live Stream On' : 'Live Paused'}</span>
          </button>

          <button
            type="button"
            onClick={() => fetchAnalytics(queryCode)}
            className="btn-icon-refresh"
            disabled={isLoading}
            title="Refresh immediately"
          >
            <RefreshCw size={13} strokeWidth={2} className={isLoading ? 'spin' : ''} />
          </button>
        </div>
      </div>

      {/* Search Bar */}
      <div className="search-toolbar">
        <form onSubmit={handleSearch} className="search-bar">
          <span className="search-prefix">/</span>
          <input
            type="text"
            className="search-input mono"
            placeholder="enter slug or paste URL to inspect"
            value={queryCode}
            onChange={(e) => setQueryCode(e.target.value)}
            spellCheck="false"
            required
          />
          <button type="submit" className="btn-search" disabled={isLoading || !queryCode.trim()}>
            <Search size={13} strokeWidth={2} />
            <span>Inspect</span>
          </button>
        </form>

        <div className="quick-chip-row">
          <span className="quick-label">Sample slugs:</span>
          {['torvalds', 'fastapi', 'streams'].map((slug) => (
            <button
              key={slug}
              type="button"
              onClick={() => handleQuickLookup(slug)}
              className={`quick-chip mono ${extractSlug(queryCode) === slug ? 'active' : ''}`}
            >
              /{slug}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="error-callout">
          <AlertCircle size={15} strokeWidth={2} className="shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Analytics Content */}
      {analytics && (
        <div className="workbench-content">
          {/* Key Metrics Strip */}
          <div className="telemetry-strip">
            <div className="stat-card">
              <span className="stat-label">Total Clicks</span>
              <div className="stat-number-row">
                <span className="stat-hero mono">{analytics.total_clicks}</span>
                <span className="stat-subtag">Events</span>
              </div>
            </div>

            <div className="stat-card">
              <span className="stat-label">Resolution Path</span>
              <div className="stat-number-row">
                <span className="stat-badge mono text-cyan">Redis Cache-Aside</span>
              </div>
            </div>

            <div className="stat-card">
              <span className="stat-label">Stream Pipeline</span>
              <div className="stat-number-row">
                <span className="stat-badge mono text-emerald">XADD · Consumer</span>
              </div>
            </div>
          </div>

          {/* Destination URL */}
          <div className="target-banner">
            <span className="target-tag">Destination:</span>
            <a
              href={analytics.original_url}
              target="_blank"
              rel="noopener noreferrer"
              className="target-link mono"
            >
              <span>{analytics.original_url}</span>
              <ExternalLink size={12} strokeWidth={2} className="shrink-0" />
            </a>
          </div>

          {/* Distribution Proportional Bars */}
          <div className="distribution-grid">
            {/* Top Referrers */}
            <div className="distribution-box">
              <div className="distribution-header">
                <div className="flex-align">
                  <Globe size={13} strokeWidth={2} className="text-secondary" />
                  <span className="dist-title">Top Traffic Referrers</span>
                </div>
                <span className="dist-meta mono">{analytics.top_referrers.length} sources</span>
              </div>

              {analytics.top_referrers.length === 0 ? (
                <div className="dist-empty">No click events recorded yet for this link.</div>
              ) : (
                <div className="progress-bars-stack">
                  {analytics.top_referrers.map((item, idx) => {
                    const pct = Math.round((item.count / totalReferrerClicks) * 100);
                    return (
                      <div key={idx} className="progress-row">
                        <div className="progress-labels">
                          <span className="progress-name" title={item.name}>
                            {item.name}
                          </span>
                          <span className="progress-val mono">
                            {item.count} <span className="text-dim">({pct}%)</span>
                          </span>
                        </div>
                        <div className="progress-track">
                          <div
                            className="progress-fill fill-cyan"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Client Platforms */}
            <div className="distribution-box">
              <div className="distribution-header">
                <div className="flex-align">
                  <Monitor size={13} strokeWidth={2} className="text-secondary" />
                  <span className="dist-title">Client Platforms / Browsers</span>
                </div>
                <span className="dist-meta mono">{analytics.top_user_agents.length} clients</span>
              </div>

              {analytics.top_user_agents.length === 0 ? (
                <div className="dist-empty">No user-agent telemetry yet.</div>
              ) : (
                <div className="progress-bars-stack">
                  {analytics.top_user_agents.map((item, idx) => {
                    const pct = Math.round((item.count / totalPlatformClicks) * 100);
                    return (
                      <div key={idx} className="progress-row">
                        <div className="progress-labels">
                          <span className="progress-name" title={item.name}>
                            {item.name}
                          </span>
                          <span className="progress-val mono">
                            {item.count} <span className="text-dim">({pct}%)</span>
                          </span>
                        </div>
                        <div className="progress-track">
                          <div
                            className="progress-fill fill-indigo"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {/* Real-Time Stream Event Log Table */}
          <div className="event-log-box">
            <div className="event-log-header">
              <div className="flex-align">
                <Clock size={13} strokeWidth={2} className="text-secondary" />
                <span className="dist-title">Real-Time Redis Stream Feed</span>
              </div>
              <span className="event-badge mono">
                {analytics.recent_events.length} Recent Ingestions
              </span>
            </div>

            {analytics.recent_events.length === 0 ? (
              <div className="dist-empty">
                No stream events recorded yet. Click the short link to publish real-time events.
              </div>
            ) : (
              <div className="table-viewport">
                <table className="flat-table">
                  <thead>
                    <tr>
                      <th>Time (UTC)</th>
                      <th>Client IP</th>
                      <th>Referrer</th>
                      <th>Event ID</th>
                    </tr>
                  </thead>
                  <tbody>
                    {analytics.recent_events.map((ev) => (
                      <tr key={ev.event_id}>
                        <td className="mono text-nowrap">
                          {new Date(ev.clicked_at).toLocaleTimeString()}
                        </td>
                        <td className="mono">{ev.ip_address || '—'}</td>
                        <td className="cell-truncate text-secondary">
                          {ev.referrer || 'Direct / None'}
                        </td>
                        <td className="mono text-dim cell-truncate" title={ev.event_id}>
                          {ev.event_id.slice(0, 8)}...
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
