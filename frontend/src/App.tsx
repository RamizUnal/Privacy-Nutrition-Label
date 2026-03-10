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
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-border bg-bg/90 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <button onClick={handleReset} className="flex items-center gap-3 group">
            <div className="w-8 h-8 rounded border border-accent-green/40 flex items-center justify-center group-hover:border-accent-green/80 transition-colors">
              <svg className="w-4 h-4 text-accent-green" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
            </div>
            <span className="font-mono text-sm font-semibold text-white/80 group-hover:text-accent-green transition-colors tracking-wider">
              PRIVACY LABEL
            </span>
          </button>

          <div className="flex items-center gap-3 text-xs font-mono text-white/30">
            <span className="w-2 h-2 rounded-full bg-accent-green animate-pulse" />
            <span>GDPR · CCPA · LGPD</span>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-4 pb-16">
        {loading ? (
          <LoadingScreen url={currentUrl} />
        ) : result ? (
          <div className="animate-fade-in">
            <div className="py-6">
              <SearchBar
                onAnalyze={handleAnalyze}
                compact
                initialUrl={currentUrl}
                onRefresh={() => handleAnalyze(currentUrl, true)}
              />
            </div>
            <PrivacyLabel result={result} onReanalyze={() => handleAnalyze(currentUrl, true)} />
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center min-h-[80vh] gap-12">
            {/* Hero */}
            <div className="text-center max-w-2xl">
              <div className="mb-6 inline-flex items-center gap-2 px-3 py-1 rounded-full border border-accent-green/30 bg-accent-green/5 text-accent-green text-xs font-mono">
                <span className="w-1.5 h-1.5 rounded-full bg-accent-green" />
                Data Privacy Analysis Engine v1.0
              </div>
              <h1 className="font-display text-5xl md:text-6xl font-bold text-white mb-4 leading-tight">
                Privacy
                <span className="text-gradient-green"> Nutrition</span>
                <br />Label Generator
              </h1>
              <p className="text-white/50 text-lg font-sans leading-relaxed">
                Enter any website URL to generate a comprehensive privacy analysis. We scan privacy policies, detect trackers, identify dark patterns, and score compliance with GDPR & CCPA.
              </p>
            </div>

            <SearchBar onAnalyze={handleAnalyze} />

            {error && (
              <div className="px-4 py-3 rounded border border-red-800/50 bg-red-900/20 text-red-400 text-sm font-mono max-w-lg text-center">
                {error}
              </div>
            )}

            {/* Feature pills */}
            <div className="flex flex-wrap gap-2 justify-center max-w-2xl">
              {[
                '🔍 Privacy Policy Crawler',
                '🕵️ Tracker Detection',
                '🍪 Cookie Analysis',
                '⚖️ GDPR/CCPA Rights Check',
                '🎭 Dark Pattern Detection',
                '📊 Sentiment Analysis',
                '🔄 Historical Tracking',
                '💯 Privacy Score',
              ].map(f => (
                <span key={f} className="px-3 py-1 rounded-full border border-border bg-panel text-white/40 text-xs font-mono">
                  {f}
                </span>
              ))}
            </div>

            <RecentDomains onSelect={handleAnalyze} />
          </div>
        )}

        {!loading && !result && error && (
          <div className="mt-4 text-center">
            <p className="text-red-400 text-sm font-mono">{error}</p>
          </div>
        )}
      </main>
    </div>
  );
}
