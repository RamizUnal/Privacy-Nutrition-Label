import React, { useMemo, useState } from 'react';
import type { AnalysisResult, PolicyAIAnalysis } from '../../types';

interface Props {
  domain: string;
  result: AnalysisResult;
  onLoad: () => Promise<PolicyAIAnalysis>;
}

const SEVERITY_STYLES: Record<string, { border: string; bg: string; badge: string; text: string; rank: number }> = {
  critical: { border: 'border-red-500/40', bg: 'bg-red-500/10', badge: 'bg-red-500/20 text-red-300 border-red-500/30', text: 'text-red-300', rank: 0 },
  high: { border: 'border-orange-500/40', bg: 'bg-orange-500/10', badge: 'bg-orange-500/20 text-orange-300 border-orange-500/30', text: 'text-orange-300', rank: 1 },
  medium: { border: 'border-yellow-500/40', bg: 'bg-yellow-500/10', badge: 'bg-yellow-400/20 text-yellow-200 border-yellow-400/30', text: 'text-yellow-200', rank: 2 },
  low: { border: 'border-sky-500/30', bg: 'bg-sky-500/10', badge: 'bg-sky-500/20 text-sky-300 border-sky-500/30', text: 'text-sky-300', rank: 3 },
};

const POSTURE_STYLES: Record<string, string> = {
  excellent: 'border-green-500/35 bg-green-500/10 text-green-300',
  good: 'border-emerald-500/35 bg-emerald-500/10 text-emerald-300',
  mixed: 'border-yellow-500/35 bg-yellow-500/10 text-yellow-200',
  concerning: 'border-orange-500/35 bg-orange-500/10 text-orange-300',
  dangerous: 'border-red-500/35 bg-red-500/10 text-red-300',
  unknown: 'border-white/10 bg-white/5 text-white/40',
};

const REG_COLORS: Record<string, string> = {
  GDPR: 'border-blue-500/30 bg-blue-500/10 text-blue-300',
  CCPA: 'border-violet-500/30 bg-violet-500/10 text-violet-300',
  ePrivacy: 'border-teal-500/30 bg-teal-500/10 text-teal-300',
  COPPA: 'border-pink-500/30 bg-pink-500/10 text-pink-300',
};

function gradeColor(score: number) {
  if (score >= 85) return '#00e676';
  if (score >= 70) return '#40c4ff';
  if (score >= 55) return '#ffd740';
  if (score >= 40) return '#ff9100';
  return '#ff1744';
}

function Section({ title, kicker, children }: { title: string; kicker?: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-border bg-panel overflow-hidden">
      <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
        <h3 className="font-mono text-xs font-semibold uppercase tracking-wider text-white/60">{title}</h3>
        {kicker && <span className="font-mono text-[11px] text-white/30">{kicker}</span>}
      </div>
      <div className="p-4">{children}</div>
    </section>
  );
}

function Metric({ label, value, tone }: { label: string; value: React.ReactNode; tone?: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface/35 px-4 py-3">
      <div className={`font-mono text-xl font-bold ${tone || 'text-white/105'}`}>{value}</div>
      <div className="mt-1 font-mono text-[11px] uppercase tracking-wider text-white/30">{label}</div>
    </div>
  );
}

function EmptyLine({ text }: { text: string }) {
  return <p className="text-sm text-white/35">{text}</p>;
}

export default function AIInsights({ domain, result, onLoad }: Props) {
  const [state, setState] = useState<'idle' | 'loading' | 'done' | 'error'>('idle');
  const [data, setData] = useState<PolicyAIAnalysis | null>(null);
  const [error, setError] = useState('');
  const [expandedFlag, setExpandedFlag] = useState<number | null>(null);

  const snapshot = useMemo(() => {
    const trackerCount = result.trackers?.total_tracker_count ?? result.trackers?.trackers?.length ?? 0;
    const cookies = result.trackers?.cookies?.length ?? 0;
    const rightsScore = result.rights
      ? Math.round(((result.rights.gdpr_score || 0) + (result.rights.ccpa_score || 0)) / 2)
      : 0;
    return {
      trackerCount,
      cookies,
      rightsScore,
      dataTypes: result.data_types?.length ?? 0,
      parties: result.third_parties?.count ?? 0,
      darkPatterns: result.dark_patterns?.count ?? 0,
      sold: !!result.third_parties?.data_sold,
      fingerprinting: !!result.trackers?.fingerprinting_detected,
      aiComplete: result.ai_extraction?.complete === true,
    };
  }, [result]);

  async function run() {
    setState('loading');
    setError('');
    try {
      const loaded = await onLoad();
      setData(loaded);
      setState('done');
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'AI analysis failed');
      setState('error');
    }
  }

  const redFlags = [...(data?.red_flags || [])].sort((a, b) => {
    const aStyle = SEVERITY_STYLES[a.severity] || SEVERITY_STYLES.low;
    const bStyle = SEVERITY_STYLES[b.severity] || SEVERITY_STYLES.low;
    return aStyle.rank - bStyle.rank;
  });
  const postureKey = (data?.privacy_posture || 'unknown').toLowerCase();
  const postureStyle = POSTURE_STYLES[postureKey] || POSTURE_STYLES.unknown;

  return (
    <div className="space-y-5">
      <div className="rounded-lg border border-violet-500/25 bg-violet-500/10 p-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="font-mono text-xs uppercase tracking-wider text-violet-300/75">AI Analysis Desk</div>
            <div className="mt-2 flex items-end gap-3">
              <span className="font-display text-5xl font-bold" style={{ color: gradeColor(result.overall_score) }}>
                {result.grade}
              </span>
              <div className="pb-1">
                <div className="font-mono text-sm text-white/100">{result.overall_score}/100 privacy score</div>
                <div className="font-mono text-xs text-white/35">{domain} · {result.risk_level} risk</div>
              </div>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {data && (
              <span className={`rounded border px-3 py-1.5 font-mono text-xs ${postureStyle}`}>
                {data.privacy_posture || 'AI complete'}
              </span>
            )}
            <span className={`rounded border px-3 py-1.5 font-mono text-xs ${
              snapshot.aiComplete ? 'border-green-500/25 bg-green-500/10 text-green-300' : 'border-white/10 bg-white/5 text-white/40'
            }`}>
              {snapshot.aiComplete ? 'AI extraction complete' : 'mixed extraction'}
            </span>
            <button
              onClick={run}
              disabled={state === 'loading'}
              className="rounded-lg border border-violet-400/35 bg-violet-500/10 px-4 py-2 font-mono text-xs text-violet-200 transition-colors hover:border-violet-300/60 hover:bg-violet-500/20 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {state === 'loading' ? 'Running...' : data ? 'Run Again' : 'Run Deep Analysis'}
            </button>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-6">
          <Metric label="data types" value={snapshot.dataTypes} />
          <Metric label="third parties" value={snapshot.parties} tone={snapshot.parties > 10 ? 'text-orange-300' : undefined} />
          <Metric label="trackers" value={snapshot.trackerCount} tone={snapshot.trackerCount > 5 ? 'text-red-300' : undefined} />
          <Metric label="cookies" value={snapshot.cookies} />
          <Metric label="rights" value={`${snapshot.rightsScore}%`} tone={snapshot.rightsScore >= 70 ? 'text-green-300' : 'text-orange-300'} />
          <Metric label="alerts" value={snapshot.darkPatterns + (snapshot.sold ? 1 : 0) + (snapshot.fingerprinting ? 1 : 0)} tone="text-red-300" />
        </div>
      </div>

      {state === 'loading' && (
        <Section title="Analysis Running">
          <div className="flex items-center gap-4">
            <div className="relative h-10 w-10 shrink-0">
              <div className="absolute inset-0 rounded-full border border-violet-300/30 animate-ping" />
              <div className="absolute inset-2 rounded-full border border-violet-300/50 animate-pulse" />
            </div>
            <div>
              <p className="font-mono text-sm text-white/60">Reading policy evidence and automated findings...</p>
              <p className="mt-1 text-xs text-white/35">This uses the stored policy and latest analysis for {domain}.</p>
            </div>
          </div>
        </Section>
      )}

      {state === 'error' && (
        <Section title="Analysis Error">
          <div className="flex items-center justify-between gap-4">
            <p className="font-mono text-sm text-red-300/100">{error}</p>
            <button
              onClick={run}
              className="rounded border border-border px-3 py-1.5 font-mono text-xs text-white/50 hover:text-white/100"
            >
              Retry
            </button>
          </div>
        </Section>
      )}

      {!data && state !== 'loading' && state !== 'error' && (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <Section title="What The Automated Scan Already Knows">
            <div className="space-y-3 text-sm text-white/60">
              <p>{result.summary}</p>
              <div className="flex flex-wrap gap-2">
                {(result.data_types || []).slice(0, 8).map(dt => (
                  <span key={dt.category_id} className="rounded border border-white/10 bg-white/5 px-2 py-1 font-mono text-[11px] text-white/50">
                    {dt.name}
                  </span>
                ))}
              </div>
            </div>
          </Section>
          <Section title="Run Output">
            <div className="grid grid-cols-1 gap-2 text-sm text-white/50">
              <p>Plain-language summary, top risks, policy quotes, compliance gaps, and concrete user actions will appear here.</p>
              <p className="font-mono text-xs text-white/30">Uses Claude Haiku and the stored analysis for {domain}.</p>
            </div>
          </Section>
        </div>
      )}

      {data && (
        <>
          {!data.ai_available && (
            <div className="rounded-lg border border-yellow-500/30 bg-yellow-500/10 p-4 text-center font-mono text-xs text-yellow-200">
              AI unavailable. Add ANTHROPIC_API_KEY to backend/.env and restart the backend.
            </div>
          )}

          <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1.1fr)_minmax(340px,0.9fr)]">
            <Section title="Executive Read">
              <div className="space-y-4">
                <div>
                  <div className="font-mono text-xs uppercase tracking-wider text-violet-300/70">TL;DR</div>
                  <p className="mt-1 text-lg font-semibold leading-relaxed text-white/90">{data.tldr}</p>
                </div>
                <p className="text-sm leading-relaxed text-white/60">{data.plain_summary}</p>
                <div className="rounded-lg border border-border bg-surface/35 p-3">
                  <div className="font-mono text-xs uppercase tracking-wider text-white/35">Score Commentary</div>
                  <p className="mt-1 text-sm leading-relaxed text-white/60">{data.ai_score_commentary}</p>
                </div>
              </div>
            </Section>

            <Section title="Fastest Risk Reductions" kicker={`${(data.quick_wins || data.recommended_actions || []).length} actions`}>
              <div className="space-y-2">
                {(data.quick_wins?.length ? data.quick_wins : data.recommended_actions || []).slice(0, 5).map((action, i) => (
                  <div key={i} className="flex items-start gap-3 rounded-lg border border-border bg-surface/30 p-3">
                    <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded bg-green-500/20 font-mono text-xs font-bold text-green-300">
                      {i + 1}
                    </span>
                    <span className="text-sm leading-relaxed text-white/70">{action}</span>
                  </div>
                ))}
                {!(data.quick_wins?.length || data.recommended_actions?.length) && <EmptyLine text="No user actions returned." />}
              </div>
            </Section>
          </div>

          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <Section title="Top Risks">
              {data.headline_risks?.length ? (
                <div className="space-y-2">
                  {data.headline_risks.map((risk, i) => (
                    <div key={i} className="flex items-start gap-3 text-sm text-white/70">
                      <span className="font-mono text-xs text-red-300">#{i + 1}</span>
                      <span className="leading-relaxed">{risk}</span>
                    </div>
                  ))}
                </div>
              ) : <EmptyLine text="No headline risks returned." />}
            </Section>

            <Section title="Data Journey">
              <div className="space-y-3 text-sm leading-relaxed text-white/60">
                <p>{data.data_story}</p>
                <p className="border-t border-border pt-3 text-white/50">{data.risk_narrative}</p>
              </div>
            </Section>
          </div>

          {redFlags.length > 0 && (
            <Section title="Red Flags" kicker={`${redFlags.length} findings`}>
              <div className="space-y-3">
                {redFlags.map((flag, i) => {
                  const style = SEVERITY_STYLES[flag.severity] || SEVERITY_STYLES.low;
                  const open = expandedFlag === i;
                  return (
                    <div key={i} className={`overflow-hidden rounded-lg border ${style.border} ${style.bg}`}>
                      <button
                        onClick={() => setExpandedFlag(open ? null : i)}
                        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
                      >
                        <div className="flex min-w-0 items-center gap-2">
                          <span className={`shrink-0 rounded border px-2 py-0.5 font-mono text-[10px] font-bold uppercase ${style.badge}`}>
                            {flag.severity}
                          </span>
                          <span className="truncate text-sm font-semibold text-white/105">{flag.issue}</span>
                        </div>
                        <span className="shrink-0 font-mono text-xs text-white/30">{open ? 'close' : 'open'}</span>
                      </button>
                      {open && (
                        <div className="space-y-3 border-t border-white/10 px-4 pb-4 pt-3">
                          <div>
                            <div className="font-mono text-[11px] uppercase tracking-wider text-white/35">Evidence</div>
                            <p className="mt-1 text-sm leading-relaxed text-white/60">{flag.evidence}</p>
                          </div>
                          <div>
                            <div className="font-mono text-[11px] uppercase tracking-wider text-white/35">Action</div>
                            <p className="mt-1 text-sm leading-relaxed text-white/70">{flag.action}</p>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </Section>
          )}

          {(data.important_quotes || []).length > 0 && (
            <Section title="Important Policy Quotes">
              <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                {(data.important_quotes || []).slice(0, 6).map((item, i) => (
                  <div key={i} className="rounded-lg border border-border bg-surface/30 p-3">
                    <div className="font-mono text-xs uppercase tracking-wider text-violet-300/70">{item.label || `Quote ${i + 1}`}</div>
                    <p className="mt-2 text-sm leading-relaxed text-white/70">"{item.quote}"</p>
                    {item.why_it_matters && <p className="mt-2 border-t border-border pt-2 text-xs leading-relaxed text-white/40">{item.why_it_matters}</p>}
                  </div>
                ))}
              </div>
            </Section>
          )}

          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <Section title="Compliance Gaps">
              {data.compliance_gaps?.length ? (
                <div className="space-y-3">
                  {data.compliance_gaps.map((gap, i) => (
                    <div key={i} className="rounded-lg border border-border bg-surface/30 p-3">
                      <span className={`rounded border px-2 py-0.5 font-mono text-[10px] ${REG_COLORS[gap.regulation] || 'border-white/10 bg-white/5 text-white/40'}`}>
                        {gap.regulation}
                      </span>
                      <p className="mt-2 text-sm leading-relaxed text-white/70">{gap.gap}</p>
                      <p className="mt-1 text-xs leading-relaxed text-white/40">{gap.recommendation}</p>
                    </div>
                  ))}
                </div>
              ) : <EmptyLine text="No compliance gaps returned." />}
            </Section>

            <Section title="Positive Findings">
              {data.positive_findings?.length ? (
                <div className="space-y-2">
                  {data.positive_findings.map((finding, i) => (
                    <div key={i} className="flex items-start gap-2 rounded-lg border border-green-500/20 bg-green-500/5 p-3 text-sm text-green-100/75">
                      <span className="mt-0.5 text-green-300">✓</span>
                      <span className="leading-relaxed">{finding}</span>
                    </div>
                  ))}
                </div>
              ) : <EmptyLine text="No positive findings returned." />}
            </Section>
          </div>

          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <Section title="Rights Summary">
              <p className="text-sm leading-relaxed text-white/60">{data.user_rights_summary}</p>
            </Section>

            <Section title="Confidence Notes">
              {(data.confidence_notes || []).length ? (
                <div className="space-y-2">
                  {(data.confidence_notes || []).map((note, i) => (
                    <p key={i} className="rounded-lg border border-border bg-surface/30 p-3 text-sm leading-relaxed text-white/50">{note}</p>
                  ))}
                </div>
              ) : <EmptyLine text="No confidence notes returned." />}
            </Section>
          </div>
        </>
      )}
    </div>
  );
}
