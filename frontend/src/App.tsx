import React, { useState, useEffect } from 'react';
import { Header } from './components/layout/Header';
import type { NavTab } from './components/layout/Header';
import { SettingsModal } from './components/layout/SettingsModal';
import { OverviewPage } from './pages/OverviewPage';
import { checkHealth } from './services/api';
import type { HealthResponse } from './types/api';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<NavTab>('overview');
  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthPing, setHealthPing] = useState<number | null>(null);
  const [healthLoading, setHealthLoading] = useState<boolean>(true);

  // State is set only in the promise callbacks, after the request settles.
  const loadHealth = () =>
    checkHealth()
      .then(({ data, pingMs }) => {
        setHealth(data);
        setHealthPing(pingMs);
      })
      .catch(() => {
        setHealth(null);
        setHealthPing(null);
      })
      .finally(() => setHealthLoading(false));

  const refreshHealth = () => {
    setHealthLoading(true);
    return loadHealth();
  };

  useEffect(() => {
    const interval = setInterval(loadHealth, 45000);
    const first = setTimeout(loadHealth, 0);
    return () => {
      clearTimeout(first);
      clearInterval(interval);
    };
  }, []);

  const goTo = (tab: NavTab) => {
    setActiveTab(tab);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div className="min-h-screen bg-bg text-ink flex flex-col">
      <Header
        activeTab={activeTab}
        onTabChange={goTo}
        health={health}
        healthPing={healthPing}
        healthLoading={healthLoading}
        onOpenSettings={() => setIsSettingsOpen(true)}
        onRefreshHealth={refreshHealth}
      />

      <main className="flex-1 w-full max-w-[1680px] mx-auto px-6 sm:px-10 lg:px-16 pt-14 pb-24">
        {activeTab === 'overview' && <OverviewPage />}
      </main>

      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        onConfigChanged={refreshHealth}
      />

      <footer className="border-t border-rule">
        <div className="max-w-[1680px] mx-auto px-6 sm:px-10 lg:px-16 py-6 flex flex-col sm:flex-row gap-2 sm:items-center justify-between text-xs text-muted">
          <span>
            <span className="font-medium text-ink-2">LawBuddy</span> — legal help for everyday problems in India
          </span>
          <span>Legal information, not legal advice. For free legal aid, contact your DLSA.</span>
        </div>
      </footer>
    </div>
  );
};

export default App;
