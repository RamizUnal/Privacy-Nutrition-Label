import React, { useState, useCallback } from 'react';
import { analyzeWebsite, getRecentDomains } from './api';
import type { AnalysisResult } from './types';
import SearchBar from './components/SearchBar';
import PrivacyLabel from './components/PrivacyLabel';
import LoadingScreen from './components/LoadingScreen';
import RecentDomains from './components/RecentDomains';

export default function App() {
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentUrl, setCurrentUrl] = useState('');

  const handleAnalyze = useCallback(async (url: string, forceRefresh = false) => {
    setLoading(true);
    setError(null);
    setCurrentUrl(url);
    try {
      const data = await analyzeWebsite(url, forceRefresh);
      setResult(data);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Analysis failed. Please try again.');
    } finally {
      setLoading(false);
    }
  }, []);

  const handleReset = () => {
    setResult(null);
    setError(null);
    setCurrentUrl('');
  };

  return (
    <div className="min-h-screen bg-bg grid-bg">
      <div className="app-page">
        {/* Top strip */}
        <header className="flex items-center justify-between px-3 pb-4 pt-1 font-mono text-[11px] font-medium uppercase tracking-[0.14em] text-white/80">
          <button onClick={handleReset} className="flex items-center gap-2 transition-opacity hover:opacity-70">
            <svg className="h-4 w-4" viewBox="0 0 16 16" fill="currentColor">
              <path d="M3 2h10v13l-5-3-5 3V2z" />
            </svg>
            <span>Case — Privacy Engineering</span>
          </button>

          <div className="hidden items-center gap-2 sm:flex">
            <span>v1.2 · 2026</span>
            <svg className="h-4 w-4" viewBox="0 0 16 16" fill="currentColor">
              <path d="M8 14s-6-3.7-6-8a3.5 3.5 0 0 1 6-2.5A3.5 3.5 0 0 1 14 6c0 4.3-6 8-6 8z" />
            </svg>
          </div>
        </header>

        {/* Main content */}
        <main>
        {loading ? (
          <section className="app-card hero-sky min-h-[760px] px-5 py-5 sm:px-7">
            <AppNav onReset={handleReset} />
            <LoadingScreen url={currentUrl} />
          </section>
        ) : result ? (
          <div className="animate-fade-in">
            <section className="app-card hero-sky mb-4 min-h-[360px] px-5 py-5 sm:px-7">
              <AppNav onReset={handleReset} />
              <div className="mx-auto flex max-w-5xl flex-col items-center px-2 py-12 text-center">
                <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-2xl bg-white/80 shadow-sm">
                  <img
                    src={`https://www.google.com/s2/favicons?domain=${result.domain}&sz=64`}
                    alt=""
                    className="h-6 w-6"
                    onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }}
                  />
                </div>
                <h1 className="font-display text-[clamp(44px,7vw,92px)] font-light leading-[0.98] tracking-[-0.012em] text-white">
                  {result.domain}
                </h1>
                <p className="mt-4 max-w-xl text-sm leading-6 text-white/60">
                  A privacy report scored across policy promises, consent behaviour,
                  trackers, cookies, retention, rights, and technical hygiene.
                </p>
                <div className="mt-8 w-full max-w-3xl">
                  <SearchBar
                    onAnalyze={handleAnalyze}
                    compact
                    initialUrl={currentUrl}
                    onRefresh={() => handleAnalyze(currentUrl, true)}
                  />
                </div>
              </div>
            </section>
            <div className="rounded-[28px] bg-white/70 p-3 shadow-[var(--shadow-md)] backdrop-blur-xl">
              <PrivacyLabel result={result} onReanalyze={() => handleAnalyze(currentUrl, true)} />
            </div>
          </div>
        ) : (
          <section className="app-card hero-sky overflow-visible px-5 pb-0 pt-5 sm:px-7">
            <AppNav onReset={handleReset} />
            <div className="mx-auto flex min-h-[660px] max-w-6xl flex-col items-center justify-center px-2 pb-12 pt-16 text-center">
              <div className="mb-9 inline-flex items-center gap-2 rounded-full border border-white/80 bg-white/80 py-1 pl-3 pr-1.5 text-[11.5px] font-medium text-white/70 shadow-[var(--shadow-sm)] backdrop-blur-xl">
                Read with
                <span className="inline-flex items-center gap-1 rounded-full bg-[#0E0E0D] px-2.5 py-1 text-[11px] text-[#FBFAF7]">
                  <svg className="h-3 w-3" viewBox="0 0 16 16" fill="currentColor">
                    <path d="M8 1l2 5 5 .5-3.5 3.5L13 15l-5-3-5 3 1.5-5L1 6.5 6 6z" />
                  </svg>
                  GDPR · CCPA
                </span>
              </div>

              <h1 className="max-w-[14ch] font-display text-[clamp(52px,9vw,116px)] font-light leading-[0.96] tracking-[-0.012em] text-white">
                Read every word,<br />
                so <em className="font-light italic">you don't</em><br />
                have to.
              </h1>

              <p className="mt-8 max-w-2xl text-[15px] leading-7 text-white/60">
                Generate an evidence-backed privacy nutrition label for any website:
                policy text, live trackers, cookies, consent behaviour, user rights,
                dark patterns, and a weighted verdict.
              </p>

              <div className="mt-9 w-full">
                <SearchBar onAnalyze={handleAnalyze} />
              </div>

              {error && (
                <div className="mt-5 max-w-lg rounded-xl border border-red-500/20 bg-white/60 px-4 py-3 text-center font-mono text-sm text-red-400">
                  {error}
                </div>
              )}

              <div className="mt-10 grid w-full max-w-4xl grid-cols-2 gap-2 sm:grid-cols-4">
                {[
                  ['80+', 'trackers'],
                  ['20+', 'data categories'],
                  ['9', 'dark patterns'],
                  ['15', 'privacy rights'],
                ].map(([big, label]) => (
                  <div key={label} className="glass-panel rounded-2xl px-4 py-3 text-left">
                    <div className="font-display text-4xl font-light leading-none text-white">{big}</div>
                    <div className="mt-1 font-mono text-[10px] uppercase tracking-[0.12em] text-white/40">{label}</div>
                  </div>
                ))}
              </div>

              <RecentDomains onSelect={handleAnalyze} />
            </div>
          </section>
        )}

        {!loading && !result && error && (
          <div className="mt-4 text-center">
            <p className="text-red-400 text-sm font-mono">{error}</p>
          </div>
        )}
        </main>
      </div>
    </div>
  );
}

function AppNav({ onReset }: { onReset: () => void }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <button onClick={onReset} className="flex items-center gap-2 font-sans text-sm font-medium text-white transition-opacity hover:opacity-70">
        <span className="grid h-[22px] w-[22px] place-items-center rounded-md bg-[#0E0E0D] text-[#FBFAF7]">
          <svg className="h-3 w-3" viewBox="0 0 16 16" fill="currentColor">
            <path d="M2 2h6v6H2zM10 2h4v4h-4zM10 8h4v6h-4zM2 10h6v4H2z" />
          </svg>
        </span>
        Privacy Label
      </button>

      <nav className="glass-panel hidden rounded-full p-1 sm:flex">
        {[
          ['Overview', 'grid'],
          ['Trackers', 'target'],
          ['Cookies', 'cookie'],
          ['History', 'history'],
        ].map(([label, icon], index) => (
          <button
            key={label}
            type="button"
            aria-label={label}
            title={label}
            className={`grid h-9 w-9 place-items-center rounded-full transition-colors ${
              index === 0 ? 'bg-[#0E0E0D] text-[#FBFAF7]' : 'text-white/70 hover:bg-black/5'
            }`}
          >
            <NavIcon icon={icon} />
          </button>
        ))}
      </nav>

      <button
        type="button"
        onClick={onReset}
        className="rounded-full border border-white/80 bg-white/80 px-4 py-2 text-sm font-medium text-white shadow-[var(--shadow-sm)] transition-transform hover:-translate-y-0.5"
      >
        New scan
      </button>
    </div>
  );
}

function NavIcon({ icon }: { icon: string }) {
  if (icon === 'grid') {
    return (
      <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <rect x="3" y="3" width="7.5" height="7.5" rx="1.5" />
        <rect x="13.5" y="3" width="7.5" height="7.5" rx="1.5" />
        <rect x="3" y="13.5" width="7.5" height="7.5" rx="1.5" />
        <rect x="13.5" y="13.5" width="7.5" height="7.5" rx="1.5" />
      </svg>
    );
  }

  if (icon === 'target') {
    return (
      <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
        <circle cx="12" cy="12" r="9" />
        <circle cx="12" cy="12" r="5" />
        <circle cx="12" cy="12" r="1.4" fill="currentColor" stroke="none" />
      </svg>
    );
  }

  if (icon === 'cookie') {
    return (
      <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
        <path d="M12 3a9 9 0 1 0 9 9c-3 0-5-2-5-4 0-3-2-5-4-5z" />
        <circle cx="9" cy="10" r=".9" fill="currentColor" stroke="none" />
        <circle cx="14" cy="14" r=".9" fill="currentColor" stroke="none" />
        <circle cx="10" cy="16" r=".9" fill="currentColor" stroke="none" />
      </svg>
    );
  }

  return (
    <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2.5" />
    </svg>
  );
}
