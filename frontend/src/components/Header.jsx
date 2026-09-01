import React, { useEffect, useState } from 'react';
import { getHealth } from '../services/api';

export default function Header() {
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
        <div className="brand-logo">
          <span className="brand-dot" />
          <span className="brand-name">LinkEngine</span>
        </div>
        <span className="brand-divider">/</span>
        <span className="brand-tagline">Real-Time Stream Telemetry & URL Router</span>
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
