import React, { useState } from 'react';
import type { EcosystemMap, ThirdPartyDossier } from '../../types';

interface Props {
  domain: string;
  onLoad: () => Promise<EcosystemMap>;
}

function TrustBar({ score }: { score: number }) {
  const color = score >= 70 ? '#00e676' : score >= 45 ? '#ffd740' : score >= 25 ? '#ff9100' : '#ff1744';
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full bg-white/10 overflow-hidden">
        <div className="h-full rounded-full transition-all" style={{ width: `${score}%`, background: color }} />
      </div>
      <span className="text-xs font-mono shrink-0" style={{ color }}>{score}</span>
    </div>
  );
}

function RoleBadge({ role }: { role: string }) {
  const styles: Record<string, string> = {
    'Controller': 'bg-red-500/20 text-red-300 border-red-500/30',
    'Processor': 'bg-blue-500/20 text-blue-300 border-blue-500/30',
    'Joint Controller': 'bg-orange-500/20 text-orange-300 border-orange-500/30',
    'Unknown': 'bg-white/5 text-white/30 border-white/10',
  };
  return (
    <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${styles[role] || styles.Unknown}`}>
      {role}
    </span>
  );
}

function DossierCard({ dossier }: { dossier: ThirdPartyDossier }) {
  const [open, setOpen] = useState(false);
  const hasRisks = dossier.risk_flags?.length > 0;

  return (
    <div className={`rounded-xl border overflow-hidden transition-colors ${
      hasRisks ? 'border-red-500/20' : 'border-border'
    } bg-surface/30`}>
      {/* Header */}
      <button
        onClick={() => setOpen(!open)}
        className="w-full text-left p-4 flex items-start gap-3 hover:bg-white/3 transition-colors"
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-2">
            <span className="text-sm font-semibold text-white/90">{dossier.name}</span>
            <RoleBadge role={dossier.gdpr_role} />
            {dossier.certifications?.length > 0 && (
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-accent-green/10 text-accent-green/70 border border-accent-green/20">
                🔒 Certified
              </span>
            )}
          </div>
          <div className="text-xs text-white/40 font-mono mb-2">{dossier.category}</div>
          <TrustBar score={dossier.trust_score_ai} />
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {hasRisks && (
            <span className="text-xs font-mono text-red-400 bg-red-500/10 px-2 py-0.5 rounded-full">
              {dossier.risk_flags.length} risk{dossier.risk_flags.length > 1 ? 's' : ''}
            </span>
          )}
          <span className="text-white/30 text-xs">{open ? '▲' : '▼'}</span>
        </div>
      </button>

      {open && (
        <div className="border-t border-border px-4 pb-4 pt-3 space-y-4">
          {/* AI Summary */}
          {dossier.ai_summary && (
            <p className="text-sm text-white/60 leading-relaxed">{dossier.ai_summary}</p>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Data Collected */}
            {dossier.data_collected?.length > 0 && (
              <div>
                <div className="text-xs font-mono text-white/40 uppercase tracking-wider mb-2">Data Collected</div>
                <div className="flex flex-wrap gap-1">
                  {dossier.data_collected.slice(0, 8).map((d, i) => (
                    <span key={i} className="text-[10px] bg-white/5 text-white/50 border border-border px-1.5 py-0.5 rounded">
                      {d}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Sub-processors */}
            {dossier.data_shared_with?.length > 0 && (
              <div>
                <div className="text-xs font-mono text-white/40 uppercase tracking-wider mb-2">Shares With</div>
                <div className="flex flex-wrap gap-1">
                  {dossier.data_shared_with.slice(0, 6).map((d, i) => (
                    <span key={i} className="text-[10px] bg-orange-500/10 text-orange-300/70 border border-orange-500/20 px-1.5 py-0.5 rounded">
                      {d}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Data Locations */}
            {dossier.data_location?.length > 0 && (
              <div>
                <div className="text-xs font-mono text-white/40 uppercase tracking-wider mb-2">Data Location</div>
                <div className="flex flex-wrap gap-1">
                  {dossier.data_location.map((loc, i) => (
                    <span key={i} className="text-[10px] bg-blue-500/10 text-blue-300/70 border border-blue-500/20 px-1.5 py-0.5 rounded">
                      🌍 {loc}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Certifications */}
            {dossier.certifications?.filter(Boolean).length > 0 && (
              <div>
                <div className="text-xs font-mono text-white/40 uppercase tracking-wider mb-2">Certifications</div>
                <div className="flex flex-wrap gap-1">
                  {dossier.certifications.filter(Boolean).map((cert, i) => (
                    <span key={i} className="text-[10px] bg-accent-green/10 text-accent-green/70 border border-accent-green/20 px-1.5 py-0.5 rounded">
                      ✓ {cert}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Risk Flags */}
          {dossier.risk_flags?.length > 0 && (
            <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-3">
              <div className="text-xs font-mono text-red-400/80 uppercase tracking-wider mb-2">⚠ Risk Flags</div>
              <ul className="space-y-1">
                {dossier.risk_flags.map((flag, i) => (
                  <li key={i} className="text-xs text-red-300/70 flex items-start gap-1.5">
                    <span className="shrink-0 mt-0.5">•</span>{flag}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Positive Signals */}
          {dossier.positive_signals?.length > 0 && (
            <div className="rounded-lg border border-accent-green/20 bg-accent-green/5 p-3">
              <div className="text-xs font-mono text-accent-green/70 uppercase tracking-wider mb-2">✓ Positive Signals</div>
              <ul className="space-y-1">
                {dossier.positive_signals.map((sig, i) => (
                  <li key={i} className="text-xs text-accent-green/60 flex items-start gap-1.5">
                    <span className="shrink-0 mt-0.5">•</span>{sig}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Retention + Opt-out */}
          <div className="flex flex-wrap gap-3 pt-1">
            {dossier.retention_claimed && dossier.retention_claimed !== 'Not stated' && (
              <div className="text-xs text-white/40">
                <span className="text-white/30 font-mono">Retention:</span>{' '}
                <span className="text-white/60">{dossier.retention_claimed}</span>
              </div>
            )}
            {dossier.opt_out_url && (
              <a
                href={dossier.opt_out_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs font-mono text-orange-400 hover:text-orange-300 underline underline-offset-2"
              >
                Opt-out →
              </a>
            )}
          </div>

          {/* Pages Fetched */}
          {Object.keys(dossier.pages_found || {}).length > 0 && (
            <div>
              <div className="text-xs font-mono text-white/30 mb-1.5">Pages Researched</div>
              <div className="flex flex-wrap gap-2">
                {Object.entries(dossier.pages_found).map(([label, url]) => {
                  const fetched = dossier.pages_fetched?.find(p => p.url === url);
                  return (
                    <a
                      key={label}
                      href={url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={`text-[10px] font-mono px-2 py-1 rounded border transition-colors ${
                        fetched?.success
                          ? 'border-accent-green/20 text-accent-green/60 hover:border-accent-green/40'
                          : 'border-border text-white/30 hover:text-white/50'
                      }`}
                    >
                      {fetched?.success ? '✓' : '○'} {label}
                    </a>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function EcosystemResearch({ domain, onLoad }: Props) {
  const [state, setState] = useState<'idle' | 'loading' | 'done' | 'error'>('idle');
  const [data, setData] = useState<EcosystemMap | null>(null);
  const [error, setError] = useState('');

  async function run() {
    setState('loading');
    setError('');
    try {
      const result = await onLoad();
      setData(result);
      setState('done');
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Ecosystem research failed');
      setState('error');
    }
  }

  if (state === 'idle') {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-6">
        <div className="text-center space-y-2">
          <div className="text-5xl mb-4">🕸️</div>
          <h3 className="text-lg font-semibold text-white">Data Ecosystem Research</h3>
          <p className="text-sm text-white/50 max-w-md">
            For every tracker, analytics provider, and ad partner detected on this site, Claude fetches their privacy policies,
            security pages, DPAs, and trust documentation — then produces a structured dossier answering
            "who gets your data and what do they do with it?"
          </p>
        </div>
        <button
          onClick={run}
          className="px-6 py-3 rounded-lg bg-blue-500/10 border border-blue-500/30 text-blue-300 font-mono text-sm
                     hover:bg-blue-500/20 transition-all hover:border-blue-500/60 flex items-center gap-2"
        >
          <span>🔍</span> Research Data Ecosystem
        </button>
        <p className="text-xs text-white/20 font-mono">Fetches 10–30+ pages · May take 30–60s</p>
      </div>
    );
  }

  if (state === 'loading') {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-5">
        <div className="relative w-16 h-16">
          <div className="absolute inset-0 rounded-full border-2 border-blue-400/20 animate-ping" />
          <div className="absolute inset-3 rounded-full border-2 border-blue-400/40 animate-spin" style={{ animationDuration: '3s' }} />
          <div className="absolute inset-5 rounded-full bg-blue-400/20 animate-pulse" />
        </div>
        <div className="text-center space-y-1">
          <p className="text-sm text-white/60 font-mono">Researching data ecosystem for {domain}…</p>
          <p className="text-xs text-white/30">Fetching privacy pages, DPAs, trust centers…</p>
          <p className="text-xs text-white/20">This may take 30–60 seconds</p>
        </div>
      </div>
    );
  }

  if (state === 'error') {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-4">
        <div className="text-4xl">⚠️</div>
        <p className="text-sm text-red-400 font-mono text-center max-w-sm">{error}</p>
        <button
          onClick={run}
          className="px-4 py-2 rounded-lg border border-border text-white/50 text-xs font-mono hover:text-white/80 transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!data) return null;

  const sortedDossiers = [...data.dossiers].sort((a, b) => a.trust_score_ai - b.trust_score_ai);
  const avgTrust = data.dossiers.length > 0
    ? Math.round(data.dossiers.reduce((s, d) => s + d.trust_score_ai, 0) / data.dossiers.length)
    : 0;

  return (
    <div className="space-y-5">
      {/* Executive Summary */}
      <div className="rounded-xl border border-blue-500/30 bg-blue-500/5 p-5 flex items-start gap-4">
        <span className="text-2xl shrink-0 mt-0.5">🌐</span>
        <div>
          <div className="text-xs font-mono text-blue-300/70 uppercase tracking-wider mb-1">
            Ecosystem Summary · {data.total_parties_researched} parties researched
          </div>
          <p className="text-sm text-white/85 leading-relaxed">{data.executive_summary}</p>
          {data.data_flow_description && (
            <p className="text-sm text-white/55 mt-2 leading-relaxed">{data.data_flow_description}</p>
          )}
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-xl border border-border bg-surface/30 p-4 text-center">
          <div className="text-2xl font-bold font-mono text-white/90">{data.total_parties_researched}</div>
          <div className="text-xs text-white/40 font-mono mt-1">Parties Researched</div>
        </div>
        <div className="rounded-xl border border-border bg-surface/30 p-4 text-center">
          <div className="text-2xl font-bold font-mono" style={{ color: avgTrust >= 60 ? '#00e676' : avgTrust >= 40 ? '#ffd740' : '#ff1744' }}>
            {avgTrust}
          </div>
          <div className="text-xs text-white/40 font-mono mt-1">Avg Trust Score</div>
        </div>
        <div className="rounded-xl border border-border bg-surface/30 p-4 text-center">
          <div className="text-2xl font-bold font-mono text-red-400">
            {data.dossiers.filter(d => d.risk_flags?.length > 0).length}
          </div>
          <div className="text-xs text-white/40 font-mono mt-1">With Risk Flags</div>
        </div>
      </div>

      {/* Highest Risk Warning */}
      {data.highest_risk_party && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-4 flex items-center gap-3">
          <span className="text-xl">⚠️</span>
          <div className="text-sm">
            <span className="text-white/60">Highest risk party: </span>
            <span className="text-red-300 font-semibold">{data.highest_risk_party}</span>
          </div>
        </div>
      )}

      {/* Dossier Cards */}
      <div className="space-y-3">
        <div className="text-xs font-mono text-white/40 uppercase tracking-wider px-1">
          Party Dossiers — sorted by trust score (lowest first)
        </div>
        {sortedDossiers.map((dossier, i) => (
          <DossierCard key={i} dossier={dossier} />
        ))}
      </div>

      {/* Recommended Actions */}
      {data.recommended_actions?.length > 0 && (
        <div className="rounded-xl border border-border bg-surface/40 overflow-hidden">
          <div className="px-5 py-3 border-b border-border flex items-center gap-2">
            <span>🎯</span>
            <span className="font-mono text-xs font-semibold text-white/70 uppercase tracking-wider">Recommended Actions</span>
          </div>
          <div className="p-5 space-y-2">
            {data.recommended_actions.map((action, i) => (
              <div key={i} className="flex items-start gap-3 text-sm text-white/65 leading-relaxed">
                <span className="text-accent-green font-mono text-xs mt-0.5 shrink-0">→</span>
                {action.includes('http') ? (
                  <span>
                    {action.replace(/(https?:\/\/\S+)/g, '')}
                    <a
                      href={action.match(/(https?:\/\/\S+)/)?.[1] || '#'}
                      target="_blank" rel="noopener noreferrer"
                      className="text-accent-green underline underline-offset-2 ml-1"
                    >
                      Link →
                    </a>
                  </span>
                ) : action}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
