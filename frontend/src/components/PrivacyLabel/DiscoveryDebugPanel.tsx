import React, { useEffect, useState } from 'react';
import { getPolicyDiscoveryDebug } from '../../api';
import type { PolicyDiscoveryDebug } from '../../types';

interface Props {
  domain: string;
}

function UrlList({ urls, empty }: { urls: string[]; empty: string }) {
  if (!urls.length) {
    return <div className="font-mono text-[11px] text-white/25">{empty}</div>;
  }

  return (
    <div className="space-y-1">
      {urls.slice(0, 5).map((url, index) => (
        <div key={`${url}-${index}`} className="flex gap-2 font-mono text-[11px] leading-4">
          <span className="w-4 shrink-0 text-white/25">{index + 1}</span>
          <span className="truncate text-white/55" title={url}>{url}</span>
        </div>
      ))}
    </div>
  );
}

export default function DiscoveryDebugPanel({ domain }: Props) {
  const [open, setOpen] = useState(false);
  const [debug, setDebug] = useState<PolicyDiscoveryDebug | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open || debug || loading) return;

    setLoading(true);
    setError('');
    getPolicyDiscoveryDebug(domain)
      .then(setDebug)
      .catch(() => setError('Discovery debug unavailable'))
      .finally(() => setLoading(false));
  }, [debug, domain, loading, open]);

  return (
    <div className="mt-3 border-t border-border pt-3">
      <button
        type="button"
        onClick={() => setOpen(value => !value)}
        className="w-full rounded border border-border px-3 py-2 text-left font-mono text-[11px] text-white/45 transition-colors hover:border-white/30 hover:text-white/70"
      >
        {open ? 'Hide' : 'Show'} discovery debug
      </button>

      {open && (
        <div className="mt-3 space-y-3 rounded border border-border/80 bg-bg/40 p-3">
          {loading && (
            <div className="font-mono text-[11px] text-white/35">Loading Brave and Claude trace...</div>
          )}

          {!loading && error && (
            <div className="font-mono text-[11px] text-red-300/70">{error}</div>
          )}

          {!loading && debug && (
            <>
              <div className="grid grid-cols-2 gap-2 font-mono text-[11px]">
                <div>
                  <div className="text-white/25">Query</div>
                  <div className="truncate text-amber-300" title={debug.query}>{debug.query}</div>
                </div>
                <div>
                  <div className="text-white/25">Claude</div>
                  <div className={debug.claude_configured ? 'text-violet-300' : 'text-white/35'}>
                    {debug.claude_configured && debug.claude_rerank_enabled ? 'ranking on' : 'not used'}
                  </div>
                </div>
              </div>

              <div>
                <div className="mb-1 font-mono text-[11px] uppercase tracking-wider text-violet-300/70">
                  Claude picked
                </div>
                <UrlList urls={debug.ai_candidates} empty="No Claude pick returned." />
              </div>

              <div>
                <div className="mb-1 font-mono text-[11px] uppercase tracking-wider text-amber-300/70">
                  Combined try order
                </div>
                <UrlList urls={debug.combined_candidates} empty="No Brave candidates passed filtering." />
              </div>

              <div>
                <div className="mb-1 font-mono text-[11px] uppercase tracking-wider text-white/35">
                  Brave raw results
                </div>
                <div className="space-y-2">
                  {debug.raw_results.slice(0, 5).map((item, index) => (
                    <div key={`${item.url}-${index}`} className="border-l border-white/10 pl-2">
                      <div className="truncate font-mono text-[11px] text-white/60" title={item.url}>
                        {index + 1}. {item.url}
                      </div>
                      {item.title && (
                        <div className="truncate text-[11px] text-white/35" title={item.title}>
                          {item.title}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <div className="mb-1 font-mono text-[11px] uppercase tracking-wider text-emerald-300/70">
                  Known URL map
                </div>
                <UrlList
                  urls={debug.known_policy_candidates}
                  empty={debug.known_policy_urls_skipped ? 'Skipped by env setting.' : 'No known URL for this domain.'}
                />
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
