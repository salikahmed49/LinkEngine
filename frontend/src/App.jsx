import React, { useState } from 'react';
import Header from './components/Header';
import CreateLinkForm from './components/CreateLinkForm';
import LinkResult from './components/LinkResult';
import AnalyticsInspector from './components/AnalyticsInspector';
import GrafanaDashboard from './components/GrafanaDashboard';

export default function App() {
  const [activeTab, setActiveTab] = useState('router');
  const [createdLink, setCreatedLink] = useState(null);
  const [selectedCodeForAnalytics, setSelectedCodeForAnalytics] = useState('torvalds');

  const handleLinkCreated = (linkData) => {
    setCreatedLink(linkData);
    setSelectedCodeForAnalytics(linkData.short_code);
  };

  const handleInspectStats = (code) => {
    setSelectedCodeForAnalytics(code);
    setActiveTab('router');
  };

  return (
    <div className="app-wrapper">
      <Header activeTab={activeTab} onTabChange={setActiveTab} />

      {activeTab === 'router' ? (
        <main className="layout-grid">
          <aside className="left-stack">
            <CreateLinkForm onLinkCreated={handleLinkCreated} />
            {createdLink && (
              <LinkResult
                linkData={createdLink}
                onInspectStats={handleInspectStats}
              />
            )}
          </aside>

          <section className="right-stack">
            <AnalyticsInspector
              key={selectedCodeForAnalytics}
              initialCode={selectedCodeForAnalytics}
              onCodeChange={setSelectedCodeForAnalytics}
            />
          </section>
        </main>
      ) : (
        <main>
          <GrafanaDashboard />
        </main>
      )}
    </div>
  );
}
