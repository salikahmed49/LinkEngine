import React, { useState } from 'react';
import Header from './components/Header';
import CreateLinkForm from './components/CreateLinkForm';
import LinkResult from './components/LinkResult';
import AnalyticsInspector from './components/AnalyticsInspector';

export default function App() {
  const [createdLink, setCreatedLink] = useState(null);
  const [selectedCodeForAnalytics, setSelectedCodeForAnalytics] = useState('torvalds');

  const handleLinkCreated = (linkData) => {
    setCreatedLink(linkData);
    setSelectedCodeForAnalytics(linkData.short_code);
  };

  const handleInspectStats = (code) => {
    setSelectedCodeForAnalytics(code);
  };

  return (
    <div className="app-wrapper">
      <Header />

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
    </div>
  );
}
