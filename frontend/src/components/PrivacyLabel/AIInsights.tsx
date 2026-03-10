import React, { useState } from 'react';
import type { PolicyAIAnalysis } from '../../types';

interface Props {
  domain: string;
  onLoad: () => Promise<PolicyAIAnalysis>;
}

const SEVERITY_STYLES: Record<string, { border: string; bg: string; badge: string; color: string }> = {
  critical: { border: 'border-red-500/40', bg: 'bg-red-500/5', badge: 'bg-red-500/20 text-red-400', color: '#ff1744' },
  high:     { border: 'border-orange-500/40', bg: 'bg-orange-500/5', badge: 'bg-orange-500/20 text-orange-400', color: '#ff9100' },
  medium:   { border: 'border-yellow-500/40', bg: 'bg-yellow-500/5', badge: 'bg-yellow-400/20 text-yellow-300', color: '#ffd740' },
  low:      { border: 'border-blue-500/30', bg: 'bg-blue-500/5', badge: 'bg-blue-500/20 text-blue-400', color: '#40c4ff' },
};

const REG_COLORS: Record<string, string> = {
  GDPR: 'bg-blue-500/20 text-blue-300',
  CCPA: 'bg-purple-500/20 text-purple-300',
  ePrivacy: 'bg-teal-500/20 text-teal-300',
  COPPA: 'bg-pink-500/20 text-pink-300',
};

function Section({ title, icon, children }: { title: string; icon: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-border bg-surface/40 overflow-hidden">
      <div className="px-5 py-3 border-b border-border flex items-center gap-2">
        <span className="text-base">{icon}</span>
        <span className="font-mono text-xs font-semibold text-white/70 uppercase tracking-wider">{title}</span>
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}

export default function AIInsights({ domain, onLoad }: Props) {
  const [state, setState] = useState<'idle' | 'loading' | 'done' | 'error'>('idle');
  const [data, setData] = useState<PolicyAIAnalysis | null>(null);
  const [error, setError] = useState('');
  const [expandedFlag, setExpandedFlag] = useState<number | null>(null);

  async function run() {
    setState('loading');
    setError('');
    try {
      const result = await onLoad();
      setData(result);
      setState('done');
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'AI analysis failed');
      setState('error');
    }
  }

  if (state === 'idle') {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-6">
        <div className="text-center space-y-2">
          <div className="text-5xl mb-4">🤖</div>
          <h3 className="text-lg font-semibold text-white">AI-Powered Policy Analysis</h3>
          <p className="text-sm text-white/50 max-w-md">
            Claude analyzes this site's privacy policy and tracking behavior to produce plain-language summaries,
            red flags, compliance gaps, and actionable recommendations.
          </p>
        </div>
        <button
          onClick={run}
          className="px-6 py-3 rounded-lg bg-accent-green/10 border border-accent-green/30 text-accent-green font-mono text-sm
                     hover:bg-accent-green/20 transition-all hover:border-accent-green/60 flex items-center gap-2"
        >
          <span>✦</span> Run AI Analysis
        </button>
        <p className="text-xs text-white/20 font-mono">Requires ANTHROPIC_API_KEY · ~10s</p>
      </div>
    );
  }

  if (state === 'loading') {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-4">
        <div className="relative w-14 h-14">
          <div className="absolute inset-0 rounded-full border-2 border-accent-green/20 animate-ping" />
          <div className="absolute inset-2 rounded-full border-2 border-accent-green/40 animate-pulse" />
          <div className="absolute inset-4 rounded-full bg-accent-green/20" />
        </div>
        <div className="text-center">
          <p className="text-sm text-white/60 font-mono">Claude is analyzing {domain}…</p>
          <p className="text-xs text-white/30 mt-1">Examining policy, trackers, and compliance</p>
        </div>
      </div>
    );
  }

  if (state === 'error') {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-4">
        <div className="text-4xl">⚠️</div>
        <p className="text-sm text-red-400 font-mono">{error}</p>
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

  const redFlagsByLevel = [...(data.red_flags || [])].sort((a, b) => {
    const order = { critical: 0, high: 1, medium: 2, low: 3 };
    return (order[a.severity as keyof typeof order] ?? 3) - (order[b.severity as keyof typeof order] ?? 3);
  });

  return (
    <div className="space-y-5">
      {/* TL;DR Banner */}
      <div className="rounded-xl border border-accent-green/30 bg-accent-green/5 p-5 flex items-start gap-4">
        <span className="text-2xl shrink-0 mt-0.5">🧠</span>
        <div>
          <div className="text-xs font-mono text-accent-green/70 uppercase tracking-wider mb-1">AI Summary</div>
          <p className="text-sm text-white/90 font-medium leading-relaxed">{data.tldr}</p>
          <p className="text-sm text-white/60 mt-2 leading-relaxed">{data.plain_summary}</p>
        </div>
      </div>

      {!data.ai_available && (
        <div className="rounded-xl border border-yellow-500/30 bg-yellow-500/5 p-4 text-center text-xs font-mono text-yellow-400">
          ⚠ AI unavailable — add ANTHROPIC_API_KEY to backend/.env for full analysis
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Risk Narrative */}
        <Section title="Risk Narrative" icon="📖">
          <p className="text-sm text-white/70 leading-relaxed">{data.risk_narrative}</p>
          <div className="mt-3 pt-3 border-t border-border">
            <div className="text-xs font-mono text-white/40 mb-1.5">Data Journey</div>
            <p className="text-sm text-white/60 leading-relaxed">{data.data_story}</p>
          </div>
          <div className="mt-3 pt-3 border-t border-border text-xs font-mono text-white/30">
            {data.ai_score_commentary}
          </div>
        </Section>

        {/* Headline Risks */}
        <Section title="Top Risks for You" icon="⚡">
          {data.headline_risks?.length > 0 ? (
            <ul className="space-y-2">
              {data.headline_risks.map((risk, i) => (
                <li key={i} className="flex items-start gap-2.5 text-sm text-white/70">
                  <span className="text-red-400 mt-0.5 shrink-0 font-mono text-xs">#{i+1}</span>
                  <span className="leading-relaxed">{risk}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-white/40">No major risks identified.</p>
          )}
          {data.user_rights_summary && (
            <div className="mt-4 pt-3 border-t border-border">
              <div className="text-xs font-mono text-white/40 mb-1.5">Your Rights</div>
              <p className="text-sm text-white/60 leading-relaxed">{data.user_rights_summary}</p>
            </div>
          )}
        </Section>
      </div>

      {/* Red Flags */}
      {redFlagsByLevel.length > 0 && (
        <Section title={`Red Flags (${redFlagsByLevel.length})`} icon="🚩">
          <div className="space-y-3">
            {redFlagsByLevel.map((flag, i) => {
              const sty = SEVERITY_STYLES[flag.severity] || SEVERITY_STYLES.low;
              const isOpen = expandedFlag === i;
              return (
                <div key={i} className={`rounded-lg border ${sty.border} ${sty.bg} overflow-hidden`}>
                  <button
                    onClick={() => setExpandedFlag(isOpen ? null : i)}
                    className="w-full text-left px-4 py-3 flex items-center justify-between gap-3"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <span className={`shrink-0 px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase ${sty.badge}`}>
                        {flag.severity}
                      </span>
                      <span className="text-sm font-medium text-white/85 truncate">{flag.issue}</span>
                    </div>
                    <span className="text-white/30 text-xs shrink-0">{isOpen ? '▲' : '▼'}</span>
                  </button>
                  {isOpen && (
                    <div className="px-4 pb-4 space-y-3">
                      <div>
                        <div className="text-xs font-mono text-white/40 mb-1">Evidence</div>
                        <p className="text-xs text-white/60 leading-relaxed italic">&ldquo;{flag.evidence}&rdquo;</p>
                      </div>
                      <div>
                        <div className="text-xs font-mono text-white/40 mb-1">What you can do</div>
                        <p className="text-xs text-white/70 leading-relaxed">→ {flag.action}</p>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </Section>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Compliance Gaps */}
        {data.compliance_gaps?.length > 0 && (
          <Section title="Compliance Gaps" icon="⚖️">
            <div className="space-y-3">
              {data.compliance_gaps.map((gap, i) => (
                <div key={i} className="border border-border rounded-lg p-3 bg-surface/30">
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${REG_COLORS[gap.regulation] || 'bg-white/10 text-white/50'}`}>
                      {gap.regulation}
                    </span>
                  </div>
                  <p className="text-xs text-white/70 mb-1 leading-relaxed">{gap.gap}</p>
                  <p className="text-xs text-white/40 leading-relaxed">→ {gap.recommendation}</p>
                </div>
              ))}
            </div>
          </Section>
        )}

        {/* Positive Findings */}
        {data.positive_findings?.length > 0 && (
          <Section title="Positive Findings" icon="✅">
            <ul className="space-y-2">
              {data.positive_findings.map((finding, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-white/70">
                  <span className="text-accent-green shrink-0 mt-0.5">✓</span>
                  <span className="leading-relaxed">{finding}</span>
                </li>
              ))}
            </ul>
          </Section>
        )}
      </div>

      {/* Recommended Actions */}
      {data.recommended_actions?.length > 0 && (
        <Section title="Recommended Actions" icon="🎯">
          <div className="grid gap-2 sm:grid-cols-2">
            {data.recommended_actions.map((action, i) => (
              <div key={i} className="flex items-start gap-3 p-3 rounded-lg border border-border bg-surface/30">
                <span className="w-5 h-5 rounded-full bg-accent-green/20 text-accent-green text-xs font-mono font-bold flex items-center justify-center shrink-0 mt-0.5">
                  {i + 1}
                </span>
                <span className="text-sm text-white/70 leading-relaxed">{action}</span>
              </div>
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}
