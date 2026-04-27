import React, { useState } from 'react';
import type { TrackerResult, RuntimeObservations } from '../../types';

interface Props {
  trackers: TrackerResult;
  runtime?: RuntimeObservations;
}

const CAT_COLORS: Record<string, string> = {
  necessary: '#22c55e', analytics: '#3b82f6',
  advertising: '#ef4444', functional: '#a855f7', unknown: '#6b7280',
};

export default function Cookies({ trackers, runtime }: Props) {
  const [filter, setFilter] = useState('all');

  if (!trackers) return <div className="text-center py-16 text-white/30 font-mono text-sm">Cookie data unavailable.</div>;

  const cookies = trackers.cookies || [];
  const filtered = filter === 'all' ? cookies : cookies.filter(c => c.category === filter);
  const sec = trackers.cookie_security || {};
  const runtimeAvailable = !!runtime?.available;
  const runtimeQuality = runtime?.quality || {};
  const runtimeInconclusive =
    !!runtime?.requires_human ||
    runtimeQuality.usable_for_scoring === false ||
    runtimeQuality.usable_for_mismatch === false;

  const s0 = runtime?.states?.S0;
  const s1 = runtime?.states?.S1;
  const s2 = runtime?.states?.S2;
  const runtimeCookieTotal = (s0?.total_cookies || 0) + (s1?.total_cookies || 0) + (s2?.total_cookies || 0);
  const runtimeCookieNamesSample = Array.from(new Set([...(s0?.cookie_names || []), ...(s1?.cookie_names || []), ...(s2?.cookie_names || [])])).slice(0, 12);

  const catCounts: Record<string, number> = {};
  cookies.forEach(c => { catCounts[c.category] = (catCounts[c.category] || 0) + 1; });

  function SecurityBadge({ flag, value, label }: { flag: boolean; value?: string; label: string }) {
    return (
      <div className={`flex items-center gap-1.5 px-2 py-1 rounded border text-xs font-mono ${
        flag ? 'border-green-800/40 bg-green-900/15 text-green-400' : 'border-red-800/40 bg-red-900/15 text-red-400'
      }`}>
        <span>{flag ? '✓' : '✗'}</span>
        <span>{label}</span>
        {value && <span className="text-white/30">({value})</span>}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {runtimeAvailable && (
        <div className="bg-panel border border-border rounded-xl p-5">
          <h3 className="font-mono text-xs text-white/40 uppercase tracking-wider mb-3">Runtime browser cookies (primary)</h3>
          <p className="text-xs font-mono text-white/45 mb-3">
            Runtime cookies come from the Playwright browser crawl and may differ from static Set-Cookie header detection.
          </p>
          {runtimeInconclusive && (
            <p className="text-xs font-mono text-yellow-300/70 mb-3">
              Runtime crawl inconclusive{(runtime?.human_reasons || runtimeQuality.reasons || []).length ? `: ${[...(runtime?.human_reasons || []), ...(runtimeQuality.reasons || [])].join(', ')}` : '.'}
            </p>
          )}

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
            {[
              { label: 'S0 Baseline', state: s0 },
              { label: 'S1 Reject', state: s1 },
              { label: 'S2 Accept', state: s2 },
            ].map(({ label, state }) => (
              <div key={label} className="border border-border rounded-lg p-3 bg-surface/30">
                <div className="font-mono text-[11px] text-white/50 uppercase mb-2">{label}</div>
                <div className="text-xs text-white/60 flex justify-between"><span>Runtime cookies</span><span className="font-mono text-white/80">{state?.total_cookies ?? 0}</span></div>
                <div className="text-xs text-white/60 flex justify-between mt-1"><span>3rd-party requests</span><span className="font-mono text-white/80">{state?.third_party_request_count ?? 0}</span></div>
              </div>
            ))}
          </div>

          <div className="text-xs font-mono text-white/50 space-y-1">
            <div>S1 - S0 cookie delta: {(s1?.total_cookies ?? 0) - (s0?.total_cookies ?? 0)}</div>
            <div>S2 - S1 cookie delta: {(s2?.total_cookies ?? 0) - (s1?.total_cookies ?? 0)}</div>
          </div>

          {runtimeCookieNamesSample.length > 0 && (
            <div className="mt-3">
              <div className="text-[10px] font-mono text-white/35 uppercase tracking-wider mb-2">Runtime cookie names (sample)</div>
              <div className="flex flex-wrap gap-2">
                {runtimeCookieNamesSample.map((name) => (
                  <span key={name} className="px-2 py-1 rounded text-xs font-mono border border-border text-white/45 bg-surface">{name}</span>
                ))}
              </div>
            </div>
          )}

          {((s1?.click_verification as any)?.evidence || (s2?.click_verification as any)?.evidence) && (
            <p className="text-xs font-mono text-white/40 mt-3">
              Click verification evidence is available in Dynamic Scan (S1/S2).
            </p>
          )}
        </div>
      )}

      {cookies.length === 0 ? (
        // Clean empty state — no point in showing 0% security cards, empty
        // category panels, or filter chips when there's nothing to filter.
        <div className="bg-panel border border-border rounded-xl p-8 text-center">
          <div className="font-mono text-xs text-white/35 uppercase tracking-wider mb-2">
            Static HTTP cookie detection
          </div>
          <p className="font-mono text-sm text-white/45">
            {runtimeCookieTotal > 0
              ? 'No cookies were set in the initial HTTP response.'
              : 'No cookies detected.'}
          </p>
          {runtimeCookieTotal > 0 && (
            <p className="font-mono text-xs text-white/30 mt-2">
              The runtime browser crawl observed {runtimeCookieTotal} cookies — see the panel above.
            </p>
          )}
        </div>
      ) : (
      <>
      <div className="font-mono text-[11px] text-white/40 uppercase tracking-wider">Static HTTP cookie detection</div>

      {/* Security metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {[
          { label: 'Secure Flag', pct: sec.secure_pct ?? 0, note: 'HTTPS-only transmission' },
          { label: 'HttpOnly Flag', pct: sec.httponly_pct ?? 0, note: 'JS inaccessible' },
          { label: 'SameSite Attr.', pct: sec.samesite_pct ?? 0, note: 'CSRF protection' },
        ].map(m => {
          const color = m.pct >= 70 ? '#00e676' : m.pct >= 40 ? '#ffd740' : '#ff3b3b';
          return (
            <div key={m.label} className="bg-panel border border-border rounded-xl p-4">
              <div className="flex items-end gap-1 mb-1">
                <span className="font-mono text-3xl font-bold" style={{ color }}>{m.pct.toFixed(0)}%</span>
              </div>
              <p className="font-mono text-xs text-white/60">{m.label}</p>
              <p className="font-mono text-xs text-white/25 mt-0.5">{m.note}</p>
              <div className="mt-2 h-1.5 rounded-full bg-white/5">
                <div className="h-full rounded-full" style={{ width: `${m.pct}%`, background: color }} />
              </div>
            </div>
          );
        })}
      </div>

      {/* Category breakdown */}
      <div className="bg-panel border border-border rounded-xl p-5">
        <h3 className="font-mono text-xs text-white/40 uppercase tracking-wider mb-3">Cookie Categories</h3>
        <div className="flex flex-wrap gap-2">
          {Object.entries(catCounts).map(([cat, count]) => (
            <div
              key={cat}
              className="flex items-center gap-2 px-3 py-2 rounded border cursor-pointer hover:border-white/20 transition-colors"
              style={{ borderColor: `${CAT_COLORS[cat] || '#888'}40`, background: `${CAT_COLORS[cat] || '#888'}08` }}
              onClick={() => setFilter(filter === cat ? 'all' : cat)}
            >
              <div className="w-2 h-2 rounded-full" style={{ background: CAT_COLORS[cat] || '#888' }} />
              <span className="font-mono text-xs capitalize" style={{ color: CAT_COLORS[cat] || '#888' }}>{cat}</span>
              <span className="font-mono text-xs text-white/40">{count}</span>
            </div>
          ))}
        </div>

        {/* Cookie law note */}
        <div className="mt-4 p-3 rounded bg-surface border border-border">
          <p className="text-xs font-mono text-white/30 leading-relaxed">
            Under PECR (UK) / ePrivacy Directive (EU), all non-essential cookies require prior informed consent.
            Only "strictly necessary" cookies may be set without consent. {
              catCounts.advertising ? `${catCounts.advertising} advertising cookies detected — these require explicit opt-in consent under GDPR.` : ''
            }
          </p>
        </div>
      </div>

      {/* Filter tabs */}
      <div className="flex items-center gap-2 flex-wrap">
        <button
          onClick={() => setFilter('all')}
          className={`px-3 py-1 rounded-full text-xs font-mono border transition-all ${filter === 'all' ? 'border-white/40 text-white' : 'border-border text-white/35'}`}
        >
          All ({cookies.length})
        </button>
        {Object.entries(catCounts).map(([cat, count]) => (
          <button
            key={cat}
            onClick={() => setFilter(cat)}
            className="px-3 py-1 rounded-full text-xs font-mono border transition-all"
            style={filter === cat
              ? { borderColor: CAT_COLORS[cat], color: CAT_COLORS[cat] }
              : { borderColor: 'rgba(255,255,255,0.1)', color: 'rgba(255,255,255,0.4)' }
            }
          >
            {cat} ({count})
          </button>
        ))}
      </div>

      {/* Cookie table */}
      {filtered.length > 0 ? (
        <div className="bg-panel border border-border rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono">
              <thead>
                <tr className="border-b border-border">
                  {['Name', 'Category', 'Duration', 'HttpOnly', 'Secure', 'SameSite', 'Domain'].map(h => (
                    <th key={h} className="px-4 py-3 text-left text-white/30 font-medium whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filtered.slice(0, 50).map((c, i) => (
                  <tr key={i} className="hover:bg-surface/50 transition-colors">
                    <td className="px-4 py-2.5 text-white/70 max-w-[140px] truncate" title={c.name}>{c.name}</td>
                    <td className="px-4 py-2.5">
                      <span
                        className="px-1.5 py-0.5 rounded capitalize"
                        style={{ color: CAT_COLORS[c.category], background: `${CAT_COLORS[c.category]}15` }}
                      >{c.category}</span>
                    </td>
                    <td className="px-4 py-2.5 text-white/50">{c.duration_label}</td>
                    <td className="px-4 py-2.5">
                      <span className={c.httponly ? 'text-green-400' : 'text-red-400'}>
                        {c.httponly ? '✓' : '✗'}
                      </span>
                    </td>
                    <td className="px-4 py-2.5">
                      <span className={c.secure ? 'text-green-400' : 'text-red-400'}>
                        {c.secure ? '✓' : '✗'}
                      </span>
                    </td>
                    <td className="px-4 py-2.5">
                      <span className={c.samesite ? 'text-yellow-400' : 'text-white/25'}>
                        {c.samesite || '–'}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-white/30 max-w-[120px] truncate" title={c.domain || ''}>
                      {c.domain || '–'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {filtered.length > 50 && (
            <div className="px-4 py-2 text-xs font-mono text-white/30 border-t border-border text-center">
              Showing 50 of {filtered.length} cookies
            </div>
          )}
        </div>
      ) : (
        // Filter narrowed everything out (e.g. user clicked "advertising" but
        // there are none). The full empty-page case is handled above.
        <div className="text-center py-8 text-white/30 font-mono text-sm">
          No cookies in the “{filter}” category.
        </div>
      )}
      </>
      )}
    </div>
  );
}
