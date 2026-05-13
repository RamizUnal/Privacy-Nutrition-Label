import React, { useState } from 'react';
import clsx from 'clsx';

interface Props {
  onAnalyze: (url: string) => void;
  compact?: boolean;
  initialUrl?: string;
  onRefresh?: () => void;
}

const EXAMPLE_SITES = [
  'google.com', 'facebook.com', 'amazon.com', 'twitter.com', 'netflix.com',
];

export default function SearchBar({ onAnalyze, compact, initialUrl, onRefresh }: Props) {
  const [url, setUrl] = useState(initialUrl || '');
  const [focused, setFocused] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (url.trim()) {
      onAnalyze(url.trim());
    }
  };

  return (
    <div className={clsx('w-full', compact ? 'max-w-3xl' : 'max-w-2xl mx-auto')}>
      <form onSubmit={handleSubmit} className="relative">
        <div className={clsx(
          'glass-panel flex items-center gap-0 overflow-hidden rounded-full transition-all duration-300',
          focused
            ? 'border-accent-green/60 shadow-[0_1px_0_rgba(255,255,255,0.7)_inset,0_18px_44px_-24px_rgba(14,14,13,0.28)]'
            : 'hover:border-white/90',
        )}>
          {/* Lock icon */}
          <div className="pl-4 pr-2 flex-shrink-0">
            <svg
              className={clsx('w-4 h-4 transition-colors', focused ? 'text-accent-green' : 'text-white/35')}
              fill="none" stroke="currentColor" viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>

          <input
            type="text"
            value={url}
            onChange={e => setUrl(e.target.value)}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            placeholder="Enter website URL (e.g. facebook.com)"
            className="flex-1 bg-transparent py-4 pr-2 text-sm font-mono text-white outline-none placeholder:text-[rgba(14,14,13,0.34)]"
            autoComplete="off"
            spellCheck={false}
          />

          {onRefresh && (
            <button
              type="button"
              onClick={onRefresh}
              className="px-3 py-4 text-white/35 hover:text-white/70 transition-colors border-r border-border"
              title="Force re-analyze"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </button>
          )}

          <button
            type="submit"
            className={clsx(
              'mr-1.5 rounded-full px-5 py-3 font-mono text-xs font-semibold uppercase tracking-[0.08em] transition-all duration-200 flex-shrink-0',
              url.trim()
                ? 'bg-[#0E0E0D] text-[#FBFAF7] hover:-translate-y-0.5'
                : 'bg-white/60 text-white/40 cursor-not-allowed',
            )}
          >
            ANALYZE
          </button>
        </div>
      </form>

      {!compact && (
        <div className="mt-4 flex items-center justify-center gap-2 flex-wrap">
          <span className="text-white/35 text-xs font-mono uppercase tracking-[0.12em]">Try</span>
          {EXAMPLE_SITES.map(site => (
            <button
              key={site}
              onClick={() => { setUrl(site); onAnalyze(site); }}
              className="rounded-full border border-white/80 bg-white/50 px-3 py-1 text-xs font-mono text-white/55 transition-colors hover:border-accent-green/40 hover:text-accent-green"
            >
              {site}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
