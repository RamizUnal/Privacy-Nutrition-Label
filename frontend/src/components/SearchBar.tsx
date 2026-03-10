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
          'flex items-center gap-0 rounded-lg border transition-all duration-300 overflow-hidden',
          focused
            ? 'border-accent-green/60 shadow-[0_0_0_1px_rgba(0,255,136,0.15)]'
            : 'border-border hover:border-white/20',
          'bg-panel',
        )}>
          {/* Lock icon */}
          <div className="pl-4 pr-2 flex-shrink-0">
            <svg
              className={clsx('w-4 h-4 transition-colors', focused ? 'text-accent-green' : 'text-white/30')}
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
            className="flex-1 bg-transparent py-3.5 pr-2 text-sm font-mono text-white placeholder-white/25 outline-none"
            autoComplete="off"
            spellCheck={false}
          />

          {onRefresh && (
            <button
              type="button"
              onClick={onRefresh}
              className="px-3 py-3.5 text-white/30 hover:text-white/60 transition-colors border-r border-border"
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
              'px-5 py-3.5 font-mono text-sm font-semibold transition-all duration-200 flex-shrink-0',
              url.trim()
                ? 'bg-accent-green text-black hover:bg-accent-green/90'
                : 'bg-white/5 text-white/30 cursor-not-allowed',
            )}
          >
            ANALYZE
          </button>
        </div>
      </form>

      {!compact && (
        <div className="mt-3 flex items-center gap-2 flex-wrap">
          <span className="text-white/25 text-xs font-mono">Try:</span>
          {EXAMPLE_SITES.map(site => (
            <button
              key={site}
              onClick={() => { setUrl(site); onAnalyze(site); }}
              className="text-xs font-mono text-white/35 hover:text-accent-green/80 transition-colors underline underline-offset-2"
            >
              {site}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
