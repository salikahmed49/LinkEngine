import React, { useEffect, useState } from 'react';
import { Activity, Link2, BarChart3 } from 'lucide-react';
import { getHealth } from '../services/api';

export default function Header({ activeTab, onTabChange }) {
  const [latency, setLatency] = useState(null);
  const [isOnline, setIsOnline] = useState(true);

  useEffect(() => {
    let isMounted = true;
    async function measureLatency() {
      const start = performance.now();
      try {
        await getHealth();
        const duration = Math.round(performance.now() - start);
        if (isMounted) {
          setLatency(duration);
          setIsOnline(true);
        }
      } catch {
        if (isMounted) {
          setIsOnline(false);
        }
      }
    }

    measureLatency();
    const interval = setInterval(measureLatency, 5000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <header className="navbar">
      <div className="navbar-left">
        <div className="brand-logo" onClick={() => onTabChange('router')} style={{ cursor: 'pointer' }}>
          <span className="brand-dot" />
          <span className="brand-name">LinkEngine</span>
        </div>
        <span className="brand-divider">/</span>
        
        {/* Navigation Tabs */}
        <nav className="header-nav-tabs">
          <button
            type="button"
            onClick={() => onTabChange('router')}
            className={`tab-btn ${activeTab === 'router' ? 'active' : ''}`}
          >
            <Link2 size={13} />
            <span>Link Router & Stream</span>
          </button>

          <button
            type="button"
            onClick={() => onTabChange('grafana')}
            className={`tab-btn ${activeTab === 'grafana' ? 'active' : ''}`}
          >
            <BarChart3 size={13} className="text-amber" />
            <span>Grafana Telemetry</span>
            <span className="live-pill">Live</span>
          </button>
        </nav>
      </div>

      <div className="navbar-right">
        <div className={`telemetry-badge ${isOnline ? 'online' : 'offline'}`}>
          <span className="pulse-dot" />
          {isOnline ? (
            <span>
              Engine <strong>{latency}ms</strong> · Operational
            </span>
          ) : (
            <span>Offline</span>
          )}
        </div>
      </div>
    </header>
  );
}
