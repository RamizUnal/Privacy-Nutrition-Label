import React, { useMemo, useState } from 'react';
import type { AnalysisResult, EcosystemMap, ThirdPartyDossier } from '../../types';

interface Props {
  domain: string;
  result: AnalysisResult;
  onLoad: (maxParties: number) => Promise<EcosystemMap>;
}

type SortMode = 'risk' | 'trust' | 'name' | 'docs';
type RoleFilter = 'all' | 'Controller' | 'Processor' | 'Joint Controller' | 'Unknown';

function trustColor(score: number) {
  if (score >= 75) return '#00e676';
  if (score >= 55) return '#40c4ff';
  if (score >= 35) return '#ffd740';
  if (score >= 20) return '#ff9100';
  return '#ff1744';
}

function canonicalName(name: string) {
  return name
    .toLowerCase()
    .replace(/\b(inc|llc|ltd|limited|corp|corporation|company|co)\b\.?/g, '')
    .replace(/[^a-z0-9.]+/g, ' ')
    .trim();
}

function isGenericName(name: string) {
  const key = canonicalName(name);
  return !key || [
    'service provider',
    'service providers',
    'business partner',
    'business partners',
    'partner',
    'partners',
    'affiliate',
    'affiliates',
    'vendor',
    'vendors',
    'advertising partners',
    'analytics providers',
    'payment processors',
    'cloud providers',
    'third parties',
    'third party',
  ].includes(key);
}

function Metric({ label, value, tone }: { label: string; value: React.ReactNode; tone?: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface/35 px-4 py-3">
      <div className={`font-mono text-2xl font-bold ${tone || 'text-white/105'}`}>{value}</div>
      <div className="mt-1 font-mono text-[11px] uppercase tracking-wider text-white/35">{label}</div>
    </div>
  );
}

function RoleBadge({ role }: { role: string }) {
  const styles: Record<string, string> = {
    Controller: 'border-red-500/30 bg-red-500/10 text-red-300',
    Processor: 'border-blue-500/30 bg-blue-500/10 text-blue-300',
    'Joint Controller': 'border-orange-500/30 bg-orange-500/10 text-orange-300',
    Unknown: 'border-white/10 bg-white/5 text-white/35',
  };
  return (
    <span className={`rounded border px-2 py-0.5 font-mono text-[10px] ${styles[role] || styles.Unknown}`}>
      {role || 'Unknown'}
    </span>
  );
}

function PagePill({ label, ok, url }: { label: string; ok?: boolean; url: string }) {
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className={`rounded border px-2 py-1 font-mono text-[10px] transition-colors ${
        ok ? 'border-green-500/25 bg-green-500/10 text-green-300/75 hover:border-green-400/40' : 'border-white/10 bg-white/5 text-white/35 hover:text-white/50'
      }`}
    >
      {ok ? '✓' : '○'} {label}
    </a>
  );
}

function LinkifiedAction({ action }: { action: string }) {
  const match = action.match(/https?:\/\/\S+/);
  if (!match) return <span>{action}</span>;
  return (
    <span>
      {action.slice(0, match.index).trim()}
      <a href={match[0]} target="_blank" rel="noopener noreferrer" className="ml-1 text-green-300 underline underline-offset-2">
        Open link
      </a>
    </span>
  );
}

function DossierCard({ dossier }: { dossier: ThirdPartyDossier }) {
  const [open, setOpen] = useState(false);
  const pagesFetched = dossier.pages_fetched || [];
  const successfulPages = pagesFetched.filter(p => p.success).length;
  const hasRisks = (dossier.risk_flags || []).length > 0 || !!dossier.error;
  const color = trustColor(dossier.trust_score_ai || 0);

  return (
    <article className={`overflow-hidden rounded-lg border bg-panel ${hasRisks ? 'border-red-500/25' : 'border-border'}`}>
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-start gap-4 px-4 py-4 text-left transition-colors hover:bg-white/[0.03]"
      >
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="truncate text-sm font-semibold text-white/90">{dossier.name}</h3>
            <RoleBadge role={dossier.gdpr_role || 'Unknown'} />
            {dossier.certifications?.filter(Boolean).length > 0 && (
              <span className="rounded border border-green-500/20 bg-green-500/10 px-2 py-0.5 font-mono text-[10px] text-green-300">
                certified
              </span>
            )}
            {dossier.error && (
              <span className="rounded border border-red-500/25 bg-red-500/10 px-2 py-0.5 font-mono text-[10px] text-red-300">
                partial
              </span>
            )}
          </div>
          <div className="mt-1 font-mono text-xs text-white/35">{dossier.category || 'Unknown category'}</div>
          <div className="mt-3 flex items-center gap-3">
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/10">
              <div className="h-full rounded-full" style={{ width: `${Math.max(0, Math.min(100, dossier.trust_score_ai || 0))}%`, background: color }} />
            </div>
            <span className="w-8 text-right font-mono text-xs font-bold" style={{ color }}>{dossier.trust_score_ai ?? 0}</span>
          </div>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-2">
          {hasRisks && (
            <span className="rounded-full border border-red-500/20 bg-red-500/10 px-2 py-0.5 font-mono text-[10px] text-red-300">
              {(dossier.risk_flags || []).length || 1} risk
            </span>
          )}
          <span className="font-mono text-xs text-white/30">{open ? 'close' : 'open'}</span>
        </div>
      </button>

      {open && (
        <div className="space-y-4 border-t border-border px-4 pb-4 pt-4">
          {dossier.ai_summary && <p className="text-sm leading-relaxed text-white/60">{dossier.ai_summary}</p>}

          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            <div className="rounded-lg border border-border bg-surface/30 p-3">
              <div className="font-mono text-[11px] uppercase tracking-wider text-white/35">Docs fetched</div>
              <div className="mt-1 font-mono text-lg font-bold text-white/75">{successfulPages}/{pagesFetched.length || Object.keys(dossier.pages_found || {}).length}</div>
            </div>
            <div className="rounded-lg border border-border bg-surface/30 p-3">
              <div className="font-mono text-[11px] uppercase tracking-wider text-white/35">Retention</div>
              <div className="mt-1 truncate text-sm text-white/60">{dossier.retention_claimed || 'Not stated'}</div>
            </div>
            <div className="rounded-lg border border-border bg-surface/30 p-3">
              <div className="font-mono text-[11px] uppercase tracking-wider text-white/35">Data location</div>
              <div className="mt-1 truncate text-sm text-white/60">{(dossier.data_location || []).join(', ') || 'Not stated'}</div>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {(dossier.data_collected || []).length > 0 && (
              <div>
                <div className="mb-2 font-mono text-[11px] uppercase tracking-wider text-white/35">Data collected</div>
                <div className="flex flex-wrap gap-1.5">
                  {dossier.data_collected.slice(0, 14).map((item, i) => (
                    <span key={i} className="rounded border border-white/10 bg-white/5 px-2 py-1 text-[11px] text-white/50">{item}</span>
                  ))}
                </div>
              </div>
            )}

            {(dossier.data_shared_with || []).length > 0 && (
              <div>
                <div className="mb-2 font-mono text-[11px] uppercase tracking-wider text-white/35">Sub-processors / sharing</div>
                <div className="flex flex-wrap gap-1.5">
                  {dossier.data_shared_with.slice(0, 12).map((item, i) => (
                    <span key={i} className="rounded border border-orange-500/20 bg-orange-500/10 px-2 py-1 text-[11px] text-orange-200/75">{item}</span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {(dossier.risk_flags || []).length > 0 && (
            <div className="rounded-lg border border-red-500/25 bg-red-500/10 p-3">
              <div className="mb-2 font-mono text-[11px] uppercase tracking-wider text-red-300/100">Risk flags</div>
              <div className="space-y-1.5">
                {dossier.risk_flags.map((flag, i) => (
                  <p key={i} className="text-sm leading-relaxed text-red-100/70">{flag}</p>
                ))}
              </div>
            </div>
          )}

          {(dossier.positive_signals || []).length > 0 && (
            <div className="rounded-lg border border-green-500/20 bg-green-500/10 p-3">
              <div className="mb-2 font-mono text-[11px] uppercase tracking-wider text-green-300/100">Positive signals</div>
              <div className="space-y-1.5">
                {dossier.positive_signals.map((signal, i) => (
                  <p key={i} className="text-sm leading-relaxed text-green-100/70">{signal}</p>
                ))}
              </div>
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            {Object.entries(dossier.pages_found || {}).map(([label, url]) => {
              const fetched = pagesFetched.find(p => p.url === url);
              return <PagePill key={label} label={label} url={url} ok={fetched?.success} />;
            })}
            {dossier.opt_out_url && <PagePill label="opt out" url={dossier.opt_out_url} ok />}
          </div>
        </div>
      )}
    </article>
  );
}

export default function EcosystemResearch({ domain, result, onLoad }: Props) {
  const [state, setState] = useState<'idle' | 'loading' | 'done' | 'error'>('idle');
  const [data, setData] = useState<EcosystemMap | null>(null);
  const [error, setError] = useState('');
  const [maxParties, setMaxParties] = useState(12);
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState<SortMode>('risk');
  const [roleFilter, setRoleFilter] = useState<RoleFilter>('all');

  const candidates = useMemo(() => {
    const seen = new Set<string>();
    const items: Array<{ name: string; category: string; source: string }> = [];
    for (const party of result.third_parties?.parties || []) {
      const name = party.name || '';
      const key = canonicalName(name);
      if (!isGenericName(name) && !seen.has(key)) {
        seen.add(key);
        items.push({ name, category: party.category || 'Third party', source: 'policy' });
      }
    }
    for (const tracker of result.trackers?.trackers || []) {
      const name = tracker.name || tracker.domain || '';
      const key = canonicalName(name);
      if (!isGenericName(name) && !seen.has(key)) {
        seen.add(key);
        items.push({ name, category: tracker.category || 'Tracker', source: 'runtime' });
      }
    }
    return items;
  }, [result]);

  async function run() {
    setState('loading');
    setError('');
    try {
      const loaded = await onLoad(maxParties);
      setData(loaded);
      setState('done');
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Ecosystem research failed');
      setState('error');
    }
  }

  const dossiers = useMemo(() => {
    const all = [...(data?.dossiers || [])];
    return all
      .filter(d => roleFilter === 'all' || d.gdpr_role === roleFilter)
      .filter(d => {
        const haystack = `${d.name} ${d.category} ${d.ai_summary} ${(d.risk_flags || []).join(' ')}`.toLowerCase();
        return !search.trim() || haystack.includes(search.trim().toLowerCase());
      })
      .sort((a, b) => {
        if (sort === 'name') return a.name.localeCompare(b.name);
        if (sort === 'trust') return (b.trust_score_ai || 0) - (a.trust_score_ai || 0);
        if (sort === 'docs') return (b.pages_fetched || []).filter(p => p.success).length - (a.pages_fetched || []).filter(p => p.success).length;
        const aRisk = (a.risk_flags || []).length * 25 + (100 - (a.trust_score_ai || 0));
        const bRisk = (b.risk_flags || []).length * 25 + (100 - (b.trust_score_ai || 0));
        return bRisk - aRisk;
      });
  }, [data, roleFilter, search, sort]);

  const avgTrust = data?.dossiers?.length
    ? Math.round(data.dossiers.reduce((sum, dossier) => sum + (dossier.trust_score_ai || 0), 0) / data.dossiers.length)
    : 0;
  const docsFetched = data?.dossiers?.reduce((sum, dossier) => sum + (dossier.pages_fetched || []).filter(p => p.success).length, 0) ?? 0;
  const riskCount = data?.dossiers?.filter(d => (d.risk_flags || []).length > 0).length ?? 0;

  return (
    <div className="space-y-5">
      <section className="rounded-lg border border-blue-500/25 bg-blue-500/10 p-4">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <div className="font-mono text-xs uppercase tracking-wider text-blue-300/75">Data Ecosystem</div>
            <h2 className="mt-2 font-display text-2xl font-bold text-white/90">{domain}</h2>
            <div className="mt-3 flex flex-wrap gap-2">
              {candidates.slice(0, 12).map(item => (
                <span key={`${item.source}-${item.name}`} className="rounded border border-white/10 bg-white/5 px-2 py-1 font-mono text-[11px] text-white/40">
                  {item.name}
                </span>
              ))}
              {candidates.length > 12 && (
                <span className="rounded border border-white/10 bg-white/5 px-2 py-1 font-mono text-[11px] text-white/35">
                  +{candidates.length - 12} more
                </span>
              )}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <label className="flex items-center gap-2 rounded-lg border border-border bg-surface/40 px-3 py-2">
              <span className="font-mono text-xs text-white/35">limit</span>
              <select
                value={maxParties}
                onChange={e => setMaxParties(Number(e.target.value))}
                disabled={state === 'loading'}
                className="bg-transparent font-mono text-xs text-white/75 outline-none"
              >
                {[4, 8, 12, 16, 20].map(value => <option key={value} value={value}>{value}</option>)}
              </select>
            </label>
            <button
              onClick={run}
              disabled={state === 'loading' || candidates.length === 0}
              className="rounded-lg border border-blue-400/35 bg-blue-500/10 px-4 py-2 font-mono text-xs text-blue-200 transition-colors hover:border-blue-300/60 hover:bg-blue-500/20 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {state === 'loading' ? 'Researching...' : data ? 'Research Again' : 'Research Parties'}
            </button>
          </div>
        </div>
      </section>

      {candidates.length === 0 && (
        <section className="rounded-lg border border-border bg-panel p-5 text-center">
          <p className="font-mono text-sm text-white/40">No named third parties or trackers are available to research.</p>
        </section>
      )}

      {state === 'loading' && (
        <section className="rounded-lg border border-border bg-panel p-5">
          <div className="flex items-center gap-4">
            <div className="relative h-11 w-11 shrink-0">
              <div className="absolute inset-0 rounded-full border border-blue-300/25 animate-ping" />
              <div className="absolute inset-2 rounded-full border border-blue-300/40 animate-spin" style={{ animationDuration: '2.8s' }} />
            </div>
            <div>
              <p className="font-mono text-sm text-white/60">Researching up to {maxParties} parties...</p>
              <p className="mt-1 text-xs text-white/35">Fetching privacy pages, trust centers, security docs, and DPAs where available.</p>
            </div>
          </div>
        </section>
      )}

      {state === 'error' && (
        <section className="rounded-lg border border-red-500/25 bg-red-500/10 p-4">
          <div className="flex items-center justify-between gap-3">
            <p className="font-mono text-sm text-red-300">{error}</p>
            <button onClick={run} className="rounded border border-border px-3 py-1.5 font-mono text-xs text-white/50 hover:text-white/100">
              Retry
            </button>
          </div>
        </section>
      )}

      {!data && state === 'idle' && candidates.length > 0 && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <Metric label="research candidates" value={candidates.length} />
          <Metric label="policy recipients" value={result.third_parties?.named_count ?? 0} />
          <Metric label="runtime trackers" value={result.trackers?.total_tracker_count ?? 0} tone={(result.trackers?.total_tracker_count ?? 0) > 5 ? 'text-red-300' : undefined} />
        </div>
      )}

      {data && (
        <>
          <section className="rounded-lg border border-blue-500/25 bg-blue-500/10 p-4">
            <div className="font-mono text-xs uppercase tracking-wider text-blue-300/75">
              Ecosystem Summary · {data.total_parties_researched} researched
            </div>
            <p className="mt-2 text-sm leading-relaxed text-white/75">{data.executive_summary}</p>
            {data.data_flow_description && (
              <p className="mt-2 border-t border-blue-500/20 pt-2 text-sm leading-relaxed text-white/50">{data.data_flow_description}</p>
            )}
          </section>

          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Metric label="parties researched" value={data.total_parties_researched} />
            <Metric label="avg trust" value={avgTrust} tone={avgTrust >= 60 ? 'text-green-300' : avgTrust >= 40 ? 'text-yellow-200' : 'text-red-300'} />
            <Metric label="risk dossiers" value={riskCount} tone={riskCount ? 'text-red-300' : 'text-green-300'} />
            <Metric label="docs fetched" value={docsFetched} />
          </div>

          {data.highest_risk_party && (
            <section className="rounded-lg border border-red-500/25 bg-red-500/10 p-4">
              <div className="font-mono text-xs uppercase tracking-wider text-red-300/70">Highest risk party</div>
              <p className="mt-1 text-lg font-semibold text-red-100/105">{data.highest_risk_party}</p>
            </section>
          )}

          <section className="rounded-lg border border-border bg-panel p-4">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <input
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search parties, risks, categories..."
                className="min-w-0 flex-1 rounded-lg border border-border bg-surface/50 px-3 py-2 font-mono text-sm text-white/75 outline-none placeholder:text-white/25 focus:border-blue-400/40"
              />
              <div className="flex flex-wrap gap-2">
                <select value={roleFilter} onChange={e => setRoleFilter(e.target.value as RoleFilter)} className="rounded-lg border border-border bg-surface/50 px-3 py-2 font-mono text-xs text-white/60 outline-none">
                  {(['all', 'Controller', 'Processor', 'Joint Controller', 'Unknown'] as const).map(value => <option key={value} value={value}>{value}</option>)}
                </select>
                <select value={sort} onChange={e => setSort(e.target.value as SortMode)} className="rounded-lg border border-border bg-surface/50 px-3 py-2 font-mono text-xs text-white/60 outline-none">
                  <option value="risk">risk first</option>
                  <option value="trust">trust score</option>
                  <option value="docs">docs fetched</option>
                  <option value="name">name</option>
                </select>
              </div>
            </div>
          </section>

          <div className="space-y-3">
            <div className="flex items-center justify-between px-1">
              <h3 className="font-mono text-xs uppercase tracking-wider text-white/40">Party dossiers</h3>
              <span className="font-mono text-xs text-white/30">{dossiers.length}/{data.dossiers.length}</span>
            </div>
            {dossiers.length > 0 ? (
              dossiers.map(dossier => <DossierCard key={`${dossier.name}-${dossier.category}`} dossier={dossier} />)
            ) : (
              <div className="rounded-lg border border-border bg-panel p-5 text-center font-mono text-sm text-white/40">
                No dossiers match the current filters.
              </div>
            )}
          </div>

          {(data.recommended_actions || []).length > 0 && (
            <section className="rounded-lg border border-border bg-panel overflow-hidden">
              <div className="border-b border-border px-4 py-3 font-mono text-xs font-semibold uppercase tracking-wider text-white/60">
                Recommended Actions
              </div>
              <div className="space-y-2 p-4">
                {data.recommended_actions.map((action, i) => (
                  <div key={i} className="flex items-start gap-3 rounded-lg border border-border bg-surface/30 p-3 text-sm leading-relaxed text-white/60">
                    <span className="mt-0.5 font-mono text-xs text-green-300">→</span>
                    <LinkifiedAction action={action} />
                  </div>
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
