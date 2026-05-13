import React, { useEffect, useRef, useState } from 'react';
import type { AnalysisResult } from '../../types';
import { RadialBarChart, RadialBar, ResponsiveContainer, PolarAngleAxis } from 'recharts';
import DiscoveryDebugPanel from './DiscoveryDebugPanel';

// Each dimension's score is computed as:
//   final = baseline − Σ penalties + Σ bonuses, clamped to 0–100.
// The baseline itself comes from the backend (score_breakdown.baselines) — for
// some dimensions it's a fixed 100, for others (transparency, rights, retention,
// mismatch) it's *computed* from sub-scores, which is why it must come from the
// server rather than being hardcoded here.

interface DimExplainer {
  /** One-sentence plain-language description of what this dimension measures. */
  what: string;
  /** Why this matters to a regular user — the consequence in everyday terms. */
  why: string;
  /** How the baseline is computed (fixed-100 or derived from sub-scores). */
  baseline: string;
  /** What kind of things move the score down. */
  deductions: string;
  /** What kind of things move the score up. */
  bonuses: string;
}

const DIMENSION_EXPLAINERS: Record<string, DimExplainer> = {
  data_collection: {
    what: 'How much personal information the website asks for, and how sensitive that information is.',
    why: 'The more they collect — especially health data, financial details, ID numbers, or precise location — the more there is to leak, sell, or misuse.',
    baseline: 'Every site starts at a perfect 100. Points are then taken away for each kind of sensitive data the policy says they collect.',
    deductions: '−10 for each "special category" item under EU law (health, biometrics, race, etc.); −8 for other highly sensitive items (passwords, exact location); −4 for high-sensitivity items; −1 for medium-sensitivity items; −20 if data is sold to third parties.',
    bonuses: 'No automatic bonuses — collecting less is itself the reward.',
  },
  sharing: {
    what: 'How widely the website shares your data with other companies — advertisers, analytics firms, data brokers, and so on.',
    why: 'Every extra company that gets a copy of your data is another place it can be hacked, profiled against, or resold. Big sharing networks are how online tracking works.',
    baseline: 'Starts at 100. Penalties grow with the number of third parties named in the policy.',
    deductions: 'Up to −15 for 1–5 partners, −15 then −4 for each partner beyond 5, +−2 per partner beyond 15; −4 for each advertising partner over 3; −25 if data is sold (CCPA opt-out required); −15 for international transfers without legal safeguards; −10 for ≥10 unnamed "trusted partners".',
    bonuses: '+5 if no third-party sharing at all; +5 when the policy lists specific safeguards (Standard Contractual Clauses, adequacy decisions) for international transfers.',
  },
  transparency: {
    what: 'How clear, specific, and honest the privacy policy actually reads — instead of being long, vague legalese.',
    why: 'A policy full of "we may, from time to time, share certain information with selected partners" tells you nothing. Real transparency means you can actually figure out what happens to your data.',
    baseline: 'Computed from the policy text itself: less vague language ("may", "might", "as needed"), more named third parties, more specifically stated purposes, and shorter sentences all push the baseline up.',
    deductions: '−5 if no Data Protection Officer (DPO) is identified; −8 if the lawful basis for processing (consent, contract, legitimate interest…) isn\'t clearly stated.',
    bonuses: '+5 each for: naming a DPO, stating the lawful basis, mentioning Privacy-by-Design principles, or naming more than 5 specific third parties.',
  },
  rights: {
    what: 'How well the policy explains the rights you have over your own data — like requesting a copy, deleting it, opting out of sales, or correcting mistakes.',
    why: 'These rights only mean something if the company tells you they exist and how to use them. A policy that hides them is effectively denying them.',
    baseline: 'Average of two coverage scores: GDPR (the EU\'s General Data Protection Regulation, which gives rights like access, deletion, portability, objection) and CCPA (California Consumer Privacy Act, which gives the right to know, delete, opt out of sale, and non-discrimination). Each is scored on how many of those rights the policy actually addresses.',
    deductions: 'No direct penalties — the baseline already reflects missing rights.',
    bonuses: '+5 if the site honours Do Not Track (a browser setting that asks sites not to track you); +5 if it supports Global Privacy Control (a newer, legally enforceable opt-out signal); +3 if the policy references named privacy frameworks (e.g. COPPA for children, HIPAA for health); +2 if DNT is at least mentioned.',
  },
  retention: {
    what: 'How long the company keeps your data after they collect it — and whether they ever actually delete it.',
    why: 'Data that\'s deleted can\'t be leaked. Sites that keep your data "indefinitely" or never specify how long are a long-term liability for you.',
    baseline: 'Mapped from the overall retention rating: excellent (specific, short periods) → 100, good → 80, fair → 55, poor → 30, very poor → 5, unknown (no retention info at all) → 0.',
    deductions: '−30 if the policy says data is kept indefinitely; −20 if no specific retention periods are stated and there\'s no event-based deletion (e.g. "deleted when you close your account"), which violates GDPR Article 5(1)(e).',
    bonuses: '+10 for event-based deletion (e.g. on account closure); +10 if data is deleted on user request; +5 if the storage-limitation principle is explicitly acknowledged.',
  },
  dark_patterns: {
    what: 'Whether the site uses manipulative design tricks to push you toward giving more consent or more data than you would freely choose.',
    why: '"Dark patterns" are things like a giant green "Accept All" button next to a tiny hidden "Reject" link, pre-ticked consent boxes, or guilt-tripping you when you try to opt out. They turn consent into a charade.',
    baseline: 'Starts at a perfect 100. Each detected manipulative pattern subtracts points based on how harmful it is.',
    deductions: '−15 per high-severity pattern (e.g. forced consent, no reject button); −8 per medium-severity (e.g. pre-ticked boxes, friction on opt-out); −4 per low-severity (e.g. confusingly worded buttons).',
    bonuses: '+10 for a "good" consent flow (explicit, granular, easy to withdraw); +5 for an "adequate" one.',
  },
  technical: {
    what: 'What the website actually does in your browser — how many trackers fire, how cookies are configured, whether fingerprinting or session recording is happening.',
    why: 'Privacy policies are promises. This dimension measures the *behaviour*: are they running 30 ad-tech trackers? Recording every mouse movement? Using fingerprinting to follow you across the web even if you clear cookies?',
    baseline: 'Starts at 100. Deductions reflect what was observed when the site was actually loaded in a browser.',
    deductions: '−30 for >20 trackers, −18 for 11–20, −10 for 6–10; −25 if browser fingerprinting is detected (often unconsented, hard to block); −15 for session recording (full keystroke / mouse capture); −10 / −8 / −5 if too few cookies use the Secure / HttpOnly / SameSite security flags.',
    bonuses: '+8 if a Consent Management Platform (cookie banner system) is present; +15 if no trackers are detected at all; +10 if rejecting consent meaningfully reduces the tracker count.',
  },
  mismatch: {
    what: 'Whether what the website *does* in practice matches what the privacy policy *promises*.',
    why: 'A policy claiming "we don\'t share your data with advertisers" while 14 ad-tech requests fire on page load is the most important kind of red flag — it means the legal document is fiction. This dimension catches that gap.',
    baseline: 'Starts at the runtime mismatch score from observed behaviour (50 if no live observation could be made). Higher is better — fewer mismatches detected.',
    deductions: '−25 per critical mismatch (e.g. tracking continues identically after the user clicks "Reject All"); −15 per high-severity mismatch (e.g. trackers active before any consent is given, undeclared third parties firing).',
    bonuses: '+10 if every observed behaviour matches the policy claims and consent actually works.',
  },
};

interface Props {
  result: AnalysisResult;
  onReanalyze?: () => void;
}

const GRADE_COLORS: Record<string, string> = {
  A: '#6B8453', B: '#6F8791', C: '#B98F2A', D: '#A96F3C', F: '#A04535',
};
const RISK_COLORS: Record<string, string> = {
  low: '#6B8453', medium: '#B98F2A', high: '#A96F3C', critical: '#A04535',
};

type DiscoveryMethod = NonNullable<AnalysisResult['policy_discovery_method']>;

const DISCOVERY_METHOD_META: Record<DiscoveryMethod, { label: string; className: string }> = {
  link_scan: { label: 'link scan', className: 'text-white/50' },
  known_url: { label: 'known policy URL', className: 'text-emerald-400' },
  brave_search: { label: 'Brave Search', className: 'text-amber-300' },
  canonical_path: { label: 'canonical path', className: 'text-white/50' },
  sitemap: { label: 'sitemap', className: 'text-blue-400' },
  ai_discovery: { label: 'AI discovery', className: 'text-violet-400' },
};

function CountUp({ target, duration = 1200 }: { target: number; duration?: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    let start = 0;
    const increment = target / (duration / 16);
    const timer = setInterval(() => {
      start = Math.min(start + increment, target);
      if (ref.current) ref.current.textContent = Math.floor(start).toString();
      if (start >= target) clearInterval(timer);
    }, 16);
    return () => clearInterval(timer);
  }, [target, duration]);
  return <span ref={ref}>0</span>;
}

export default function ScoreHeader({ result, onReanalyze }: Props) {
  const gradeColor = GRADE_COLORS[result.grade] || '#888';
  const riskColor = RISK_COLORS[result.risk_level] || '#888';
  const discoveryMethod = result.policy_discovery_method
    ? DISCOVERY_METHOD_META[result.policy_discovery_method]
    : null;

  const [expandedDim, setExpandedDim] = useState<string | null>(null);

  const chartData = [
    { name: 'score', value: result.overall_score, fill: gradeColor },
  ];

  const breakdown = result.score_breakdown;
  const dims = [
    { key: 'data_collection', label: 'Data Collection',   score: breakdown?.data_collection },
    { key: 'sharing',         label: 'Third-Party Share', score: breakdown?.sharing },
    { key: 'transparency',    label: 'Transparency',       score: breakdown?.transparency },
    { key: 'rights',          label: 'User Rights',        score: breakdown?.rights },
    { key: 'retention',       label: 'Data Retention',     score: breakdown?.retention },
    { key: 'dark_patterns',   label: 'Dark Patterns',      score: breakdown?.dark_patterns },
    { key: 'technical',       label: 'Technical Safety',   score: breakdown?.technical },
    { key: 'mismatch',        label: 'Policy–Behaviour',   score: breakdown?.mismatch },
  ];

  const getBarColor = (score: number) => {
    if (score >= 75) return '#6B8453';
    if (score >= 50) return '#B98F2A';
    if (score >= 30) return '#A96F3C';
    return '#A04535';
  };

  return (
    <div className="grid grid-cols-1 gap-4 pt-1 lg:grid-cols-3">
      {/* Main score card */}
      <div className="glass-panel overflow-hidden rounded-[22px] lg:col-span-1">
        <div className="p-6 flex flex-col items-center">
          {/* Domain */}
          <div className="flex items-center gap-2 mb-4">
            <div className="w-4 h-4 rounded-full bg-panel border border-border flex-shrink-0 overflow-hidden">
              <img
                src={`https://www.google.com/s2/favicons?domain=${result.domain}&sz=16`}
                alt=""
                className="w-full h-full"
                onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }}
              />
            </div>
            <span className="font-mono text-sm text-white/60 truncate max-w-[180px]">{result.domain}</span>
          </div>

          {/* Radial score — domain pinned to 0–100 so the arc fills proportionally
              to the score (56 paints just over half the ring, not the whole one). */}
          <div className="relative w-44 h-44">
            <ResponsiveContainer width="100%" height="100%">
              <RadialBarChart
                cx="50%" cy="50%"
                innerRadius="70%" outerRadius="100%"
                startAngle={90} endAngle={-270}
                data={chartData}
              >
                <PolarAngleAxis
                  type="number"
                  domain={[0, 100]}
                  tick={false}
                  axisLine={false}
                />
                <RadialBar
                  dataKey="value"
                  cornerRadius={8}
            background={{ fill: 'rgba(14,14,13,0.06)' }}
                />
              </RadialBarChart>
            </ResponsiveContainer>
            {/* Center text */}
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <div className="text-5xl font-mono font-semibold number-pop" style={{ color: gradeColor }}>
                <CountUp target={result.overall_score} />
              </div>
              <div className="text-xs font-mono text-white/40 mt-0.5">/100</div>
            </div>
          </div>

          {/* Grade badge */}
          <div
            className="mt-3 text-7xl font-display font-light italic number-pop"
            style={{ color: gradeColor }}
          >
            {result.grade}
          </div>

          {/* Risk level */}
          <div
            className="mt-2 px-3 py-1 rounded-full text-xs font-mono font-semibold uppercase tracking-wider"
            style={{
              color: riskColor,
              background: `${riskColor}15`,
              border: `1px solid ${riskColor}40`,
            }}
          >
            {result.risk_level} risk
          </div>

          {/* Summary */}
          <p className="mt-4 text-sm font-sans text-white/55 text-center leading-relaxed">
            {result.summary}
          </p>

          {/* Meta */}
          <div className="mt-4 w-full pt-4 border-t border-border flex flex-col gap-1.5">
            <div className="flex justify-between text-xs font-mono">
              <span className="text-white/30">Policy found</span>
              <span className={result.policy_found ? 'text-accent-green' : 'text-red-400'}>
                {result.policy_found ? '✓ Yes' : '✗ No'}
              </span>
            </div>
            {result.policy_url && (
              <div className="flex justify-between items-start text-xs font-mono gap-2">
                <span className="text-white/30 flex-shrink-0">Policy URL</span>
                <a
                  href={result.policy_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-accent-green/70 hover:text-accent-green truncate max-w-[160px] text-right transition-colors underline underline-offset-2"
                  title={result.policy_url}
                >
                  {(() => {
                    try {
                      return new URL(result.policy_url).hostname.replace('www.', '');
                    } catch {
                      return result.policy_url.slice(0, 40);
                    }
                  })()}
                </a>
              </div>
            )}
            {result.policy_word_count > 0 && (
              <div className="flex justify-between text-xs font-mono">
                <span className="text-white/30">Policy length</span>
                <span className="text-white/60">{result.policy_word_count.toLocaleString()} words</span>
              </div>
            )}
            {discoveryMethod && (
              <div className="flex justify-between text-xs font-mono">
                <span className="text-white/30">Found via</span>
                <span className={discoveryMethod.className}>{discoveryMethod.label}</span>
              </div>
            )}
            {result.cached && (
              <div className="flex justify-between text-xs font-mono">
                <span className="text-white/30">Source</span>
                <span className="text-white/40">cached result</span>
              </div>
            )}
          </div>

          {onReanalyze && (
            <button
              onClick={onReanalyze}
              className="mt-4 w-full rounded-full border border-border bg-white/50 py-2 text-xs font-mono text-white/50 transition-colors hover:border-white/30 hover:text-white/70"
            >
              ↺ Force Re-analyze
            </button>
          )}

          {result.domain && <DiscoveryDebugPanel domain={result.domain} />}
        </div>
      </div>

      {/* Dimension breakdown */}
      <div className="glass-panel rounded-[22px] p-6 lg:col-span-2">
        <h3 className="font-mono text-xs text-white/40 uppercase tracking-wider mb-5">Score Breakdown</h3>

        <div className="space-y-3">
          {dims.map(dim => {
            const score = dim.score ?? 0;
            const color = getBarColor(score);
            const weight = breakdown?.weights?.[dim.key] ?? 0;
            const isOpen = expandedDim === dim.key;

            const dimPenalties = (result.penalties || []).filter(p => p.dimension === dim.key);
            const dimBonuses = (result.bonuses || []).filter(b => b.dimension === dim.key);
            const totalPenalty = dimPenalties.reduce((s, p) => s + (p.penalty || 0), 0);
            const totalBonus = dimBonuses.reduce((s, b) => s + (b.bonus || 0), 0);
            const baseline = breakdown?.baselines?.[dim.key];
            const clampMode = breakdown?.clamped?.[dim.key]; // 'floor' | 'ceiling' | undefined
            const explainer = DIMENSION_EXPLAINERS[dim.key];
            const rawMath = baseline !== undefined ? baseline - totalPenalty + totalBonus : null;

            // Pull live, dimension-specific facts from the result so we can
            // show the user EXACT sub-scores rather than a generic description.
            const liveFacts = (() => {
              switch (dim.key) {
                case 'rights': {
                  const g = result.rights?.gdpr_score;
                  const c = result.rights?.ccpa_score;
                  if (g !== undefined && c !== undefined) {
                    // Use the server-computed baseline (Python int() truncates,
                    // so we must show that same value, not Math.round).
                    const avg = baseline ?? Math.floor((g + c) / 2);
                    return `GDPR coverage: ${g}/100 · CCPA coverage: ${c}/100 → average = ${avg}`;
                  }
                  return null;
                }
                case 'transparency': {
                  const t = result.sentiment?.transparency_score;
                  const named = result.sentiment?.named_third_party_count;
                  if (t !== undefined) {
                    return `Policy clarity score: ${t}/100${named !== undefined ? ` · ${named} third parties named by name` : ''}`;
                  }
                  return null;
                }
                case 'retention': {
                  const r = result.retention?.overall_rating;
                  if (r) return `Retention rating from policy text: "${r}"`;
                  return null;
                }
                case 'data_collection': {
                  const total = result.data_types?.length ?? 0;
                  const crit = result.data_types?.filter(d => d.sensitivity === 'critical').length ?? 0;
                  const high = result.data_types?.filter(d => d.sensitivity === 'high').length ?? 0;
                  const med = result.data_types?.filter(d => d.sensitivity === 'medium').length ?? 0;
                  if (total > 0) {
                    return `${total} data categories collected: ${crit} critical, ${high} high-sensitivity, ${med} medium-sensitivity`;
                  }
                  return null;
                }
                case 'sharing': {
                  const tp = result.third_parties?.count ?? 0;
                  const ad = result.third_parties?.advertising_partners ?? 0;
                  const sold = result.third_parties?.data_sold;
                  return `${tp} third-party recipients · ${ad} advertising partners${sold ? ' · data is sold' : ''}`;
                }
                case 'technical': {
                  const tc = result.trackers?.total_tracker_count ?? 0;
                  const fp = result.trackers?.fingerprinting_detected;
                  const sr = result.trackers?.session_recording_detected;
                  return `${tc} trackers fired on page load${fp ? ' · fingerprinting detected' : ''}${sr ? ' · session recording detected' : ''}`;
                }
                case 'dark_patterns': {
                  const dp = result.dark_patterns?.count ?? 0;
                  const high = result.dark_patterns?.high_severity_count ?? 0;
                  if (dp > 0) return `${dp} manipulative patterns detected (${high} high severity)`;
                  return 'No manipulative patterns detected';
                }
                case 'mismatch': {
                  const m = result.mismatch_analysis?.total_count;
                  const eff = result.mismatch_analysis?.consent_effective;
                  if (m !== undefined) {
                    return `${m} policy–behaviour mismatches found · consent ${eff ? 'works as advertised' : 'does NOT change observed behaviour'}`;
                  }
                  return null;
                }
                default:
                  return null;
              }
            })();

            return (
              <div key={dim.key}>
                <button
                  type="button"
                  onClick={() => setExpandedDim(isOpen ? null : dim.key)}
                  className="w-full text-left group"
                  aria-expanded={isOpen}
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-2">
                      <span
                        className="font-mono text-xs text-white/30 transition-transform inline-block w-3"
                        style={{ transform: isOpen ? 'rotate(90deg)' : 'rotate(0deg)' }}
                      >
                        ▸
                      </span>
                      <span className="font-mono text-xs text-white/60 group-hover:text-white/80 transition-colors">
                        {dim.label}
                      </span>
                      <span className="font-mono text-xs text-white/20">({(weight * 100).toFixed(0)}%)</span>
                      {(dimPenalties.length > 0 || dimBonuses.length > 0) && (
                        <span className="font-mono text-[10px] text-white/30">
                          {dimPenalties.length > 0 && (
                            <span className="text-red-400/60">−{totalPenalty}</span>
                          )}
                          {dimPenalties.length > 0 && dimBonuses.length > 0 && (
                            <span className="text-white/20"> · </span>
                          )}
                          {dimBonuses.length > 0 && (
                            <span className="text-accent-green/60">+{totalBonus}</span>
                          )}
                        </span>
                      )}
                    </div>
                    <span className="font-mono text-xs font-semibold" style={{ color }}>
                      {score}/100
                    </span>
                  </div>
                  <div className="score-bar">
                    <div
                      className="score-bar-fill"
                      style={{ width: `${score}%`, background: color }}
                    />
                  </div>
                </button>

                {isOpen && (
                  <div className="mt-2 ml-5 pl-3 border-l border-border/60 space-y-3 pb-2">
                    {explainer && (
                      <>
                        {/* What this dimension actually measures */}
                        <div>
                          <h5 className="font-mono text-[10px] uppercase tracking-wider text-white/50 mb-1">
                            What this measures
                          </h5>
                          <p className="text-[11px] font-sans text-white/65 leading-relaxed">
                            {explainer.what}
                          </p>
                        </div>

                        {/* Why it matters in everyday terms */}
                        <div>
                          <h5 className="font-mono text-[10px] uppercase tracking-wider text-white/50 mb-1">
                            Why it matters
                          </h5>
                          <p className="text-[11px] font-sans text-white/55 leading-relaxed">
                            {explainer.why}
                          </p>
                        </div>

                        {/* Live facts about THIS site */}
                        {liveFacts && (
                          <div>
                            <h5 className="font-mono text-[10px] uppercase tracking-wider text-amber-300/70 mb-1">
                              Findings on this site
                            </h5>
                            <p className="text-[11px] font-mono text-white/70 leading-relaxed">
                              {liveFacts}
                            </p>
                          </div>
                        )}

                        {/* How the baseline is computed */}
                        <div>
                          <h5 className="font-mono text-[10px] uppercase tracking-wider text-white/50 mb-1">
                            How the baseline is calculated
                          </h5>
                          <p className="text-[11px] font-sans text-white/55 leading-relaxed">
                            {explainer.baseline}
                          </p>
                        </div>
                      </>
                    )}

                    {/* Math line: baseline − penalties + bonuses = score.
                        If the backend didn't return a baseline (old cached
                        result), fall back to the conventional starting value
                        of 100 so the user still sees the arithmetic. */}
                    {(() => {
                      const effBaseline = baseline ?? 100;
                      const effRaw = effBaseline - totalPenalty + totalBonus;
                      // Did the displayed math actually land where the score
                      // ended up? If not, an internal deduction wasn't surfaced.
                      const inferredFloor = effRaw < 0 && score === 0;
                      const inferredCeil = effRaw > 100 && score === 100;
                      const explicitClamp = clampMode === 'floor' || clampMode === 'ceiling';
                      const unexplained = !explicitClamp && !inferredFloor && !inferredCeil && effRaw !== score;
                      return (
                        <div className="space-y-1">
                          <p className="text-[11px] font-mono text-white/55 leading-snug">
                            <span className="text-white/40">Math for this site:</span>{' '}
                            <span className="text-white/70" title="baseline">{effBaseline}</span>
                            {totalPenalty > 0 && (
                              <> {' '}<span className="text-red-400/80">− {totalPenalty}</span></>
                            )}
                            {totalBonus > 0 && (
                              <> {' '}<span className="text-accent-green/80">+ {totalBonus}</span></>
                            )}
                            {' '}<span className="text-white/40">=</span>{' '}
                            <span className="text-white/70">{effRaw}</span>
                            {(clampMode === 'floor' || inferredFloor) && (
                              <span className="text-amber-400/80">
                                {' '}→ clamped to 0 (scores can't go below 0)
                              </span>
                            )}
                            {(clampMode === 'ceiling' || inferredCeil) && (
                              <span className="text-amber-400/80">
                                {' '}→ clamped to 100 (scores can't exceed 100)
                              </span>
                            )}
                            {unexplained && (
                              <span className="text-white/40"> → {score} (rounding / weighting)</span>
                            )}
                          </p>
                          {baseline === undefined && (
                            <p className="text-[10px] font-sans text-amber-300/60 italic leading-snug">
                              This is an older cached analysis — re-analyze the site
                              to get the full per-dimension breakdown with every
                              deduction listed.
                            </p>
                          )}
                        </div>
                      );
                    })()}

                    {dimPenalties.length === 0 && dimBonuses.length === 0 && (
                      <p className="text-[11px] font-mono text-white/30">
                        No specific deductions or bonuses recorded for this dimension —
                        the score reflects the baseline calculation only.
                      </p>
                    )}

                    {dimPenalties.length > 0 && (
                      <div>
                        <h5 className="font-mono text-[10px] uppercase tracking-wider text-red-400/60 mb-1">
                          Why points were deducted
                        </h5>
                        <ul className="space-y-1">
                          {dimPenalties.map((p, i) => (
                            <li key={i} className="flex items-start gap-2 text-[11px] font-sans text-white/55 leading-snug">
                              <span className="text-red-400/80 font-mono flex-shrink-0">−{p.penalty}</span>
                              <span>{p.reason}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {dimBonuses.length > 0 && (
                      <div>
                        <h5 className="font-mono text-[10px] uppercase tracking-wider text-green-400/60 mb-1">
                          Why points were awarded
                        </h5>
                        <ul className="space-y-1">
                          {dimBonuses.map((b, i) => (
                            <li key={i} className="flex items-start gap-2 text-[11px] font-sans text-white/55 leading-snug">
                              <span className="text-accent-green/80 font-mono flex-shrink-0">+{b.bonus}</span>
                              <span>{b.reason}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Reference: what kinds of things deduct/award points in general */}
                    {explainer && (
                      <div className="mt-2 pt-2 border-t border-border/40 grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div>
                          <h5 className="font-mono text-[10px] uppercase tracking-wider text-white/35 mb-1">
                            What lowers this score (reference)
                          </h5>
                          <p className="text-[11px] font-sans text-white/40 leading-relaxed">
                            {explainer.deductions}
                          </p>
                        </div>
                        <div>
                          <h5 className="font-mono text-[10px] uppercase tracking-wider text-white/35 mb-1">
                            What raises this score (reference)
                          </h5>
                          <p className="text-[11px] font-sans text-white/40 leading-relaxed">
                            {explainer.bonuses}
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <p className="mt-3 text-[10px] font-mono text-white/25">
          Click any dimension above to see what it measures, why it matters, what we found on this site, and the exact math behind the number.
        </p>

        {/* Penalties/bonuses */}
        <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Top penalties */}
          <div>
            <h4 className="font-mono text-xs text-red-400/70 uppercase tracking-wider mb-2">
              Top Findings
            </h4>
            <div className="space-y-1.5">
              {(result.penalties || []).slice(0, 4).map((p, i) => (
                <div key={i} className="flex items-start gap-2">
                  <span className="text-red-400 text-xs mt-0.5 flex-shrink-0">▼</span>
                  <span className="text-xs font-sans text-white/40 leading-snug">{p.reason}</span>
                </div>
              ))}
            </div>
          </div>
          {/* Bonuses */}
          <div>
            <h4 className="font-mono text-xs text-green-400/70 uppercase tracking-wider mb-2">
              Positive Signals
            </h4>
            <div className="space-y-1.5">
              {(result.bonuses || []).slice(0, 4).map((b, i) => (
                <div key={i} className="flex items-start gap-2">
                  <span className="text-accent-green text-xs mt-0.5 flex-shrink-0">▲</span>
                  <span className="text-xs font-sans text-white/40 leading-snug">{b.reason}</span>
                </div>
              ))}
              {!(result.bonuses || []).length && (
                <span className="text-xs font-mono text-white/20">No notable positives found.</span>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
