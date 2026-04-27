import React, { useState } from 'react';
import type { MismatchAnalysis, Mismatch } from '../../types';

interface Props {
  mismatch?: MismatchAnalysis;
}

const SEV_COLOR: Record<string, string> = {
  critical: '#ff1744',
  high:     '#ff9100',
  medium:   '#ffd740',
  low:      '#40c4ff',
};
const SEV_BG: Record<string, string> = {
  critical: 'rgba(255,23,68,0.10)',
  high:     'rgba(255,145,0,0.10)',
  medium:   'rgba(255,215,64,0.10)',
  low:      'rgba(64,196,255,0.10)',
};
const SEV_ICON: Record<string, string> = {
  critical: '🔴',
  high:     '🟠',
  medium:   '🟡',
  low:      '🔵',
};

function MismatchCard({ m }: { m: Mismatch }) {
  const [open, setOpen] = useState(false);
  const color = SEV_COLOR[m.severity] ?? '#888';
  const bg    = SEV_BG[m.severity]   ?? 'rgba(255,255,255,0.04)';

  return (
    <div
      className="rounded-xl border overflow-hidden transition-all"
      style={{ borderColor: `${color}30`, background: bg }}
    >
      {/* Header row */}
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full text-left p-4 flex items-start gap-3"
      >
        <span className="text-lg mt-0.5 flex-shrink-0">{SEV_ICON[m.severity]}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono text-sm font-semibold text-white/80">{m.title}</span>
            <span
              className="text-[10px] font-mono font-bold uppercase px-2 py-0.5 rounded-full"
              style={{ color, background: `${color}20`, border: `1px solid ${color}40` }}
            >
              {m.severity}
            </span>
            <span className="text-[10px] font-mono text-white/30 uppercase">{m.mismatch_type.replace(/_/g, ' ')}</span>
          </div>
        </div>
        <span className="text-white/30 text-xs mt-0.5 flex-shrink-0">{open ? '▲' : '▼'}</span>
      </button>

      {/* Expanded detail */}
      {open && (
        <div className="px-4 pb-4 space-y-3 border-t border-border/30 pt-3">

          {/* Claims vs. observed */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="rounded-lg p-3" style={{ background: 'rgba(64,196,255,0.06)', border: '1px solid rgba(64,196,255,0.15)' }}>
              <div className="text-[10px] font-mono text-blue-400/70 uppercase tracking-wider mb-1.5">📄 Policy Claims</div>
              <p className="text-xs text-white/60 leading-relaxed">{m.policy_claim}</p>
              {m.evidence_policy && (
                <p className="text-[10px] font-mono text-white/30 mt-2 italic">"{m.evidence_policy}"</p>
              )}
            </div>
            <div className="rounded-lg p-3" style={{ background: 'rgba(255,23,68,0.06)', border: '1px solid rgba(255,23,68,0.15)' }}>
              <div className="text-[10px] font-mono text-red-400/70 uppercase tracking-wider mb-1.5">🔍 Observed Behaviour</div>
              <p className="text-xs text-white/60 leading-relaxed">{m.observed_behavior}</p>
            </div>
          </div>

          {/* Evidence data points */}
          {m.evidence_observed && Object.keys(m.evidence_observed).length > 0 && (
            <div className="rounded-lg p-3" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)' }}>
              <div className="text-[10px] font-mono text-white/40 uppercase tracking-wider mb-2">Evidence</div>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {Object.entries(m.evidence_observed).slice(0, 6).map(([k, v]) => (
                  <div key={k} className="text-xs">
                    <span className="text-white/30">{k.replace(/_/g, ' ')}: </span>
                    <span className="text-white/60 font-mono">
                      {typeof v === 'boolean' ? (v ? '✓' : '✗') : String(v)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* GDPR reference + recommendation */}
          <div className="flex flex-col sm:flex-row gap-3">
            {m.gdpr_reference && (
              <div className="flex items-start gap-2 flex-1">
                <span className="text-violet-400 text-xs">⚖</span>
                <span className="text-xs text-violet-300/60 font-mono">{m.gdpr_reference}</span>
              </div>
            )}
            {m.recommendation && (
              <div className="flex items-start gap-2 flex-1">
                <span className="text-accent-green text-xs mt-0.5">→</span>
                <span className="text-xs text-white/50 leading-relaxed">{m.recommendation}</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function MismatchPanel({ mismatch }: Props) {
  const [severityFilter, setSeverityFilter] = useState<string>('all');

  if (!mismatch) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-white/30">
        <div className="text-4xl mb-4">🔄</div>
        <p className="font-mono text-sm">Mismatch data not available</p>
        <p className="font-mono text-xs mt-1">(Requires dynamic crawl — re-analyze with crawling enabled)</p>
      </div>
    );
  }

  const hasMismatches = mismatch.total_count > 0;
  const filtered = mismatch.mismatches.filter(
    m => severityFilter === 'all' || m.severity === severityFilter
  );

  const summary = mismatch.summary || '';
  const isInconclusive =
    /inconclusive/i.test(summary) ||
    /usable_for_mismatch\s*=\s*false/i.test(summary) ||
    (mismatch.mismatch_score === 50 && mismatch.total_count === 0 && /Dynamic crawl/i.test(summary));

  const counts = [
    { key: 'all',      label: 'All',      n: mismatch.total_count,    color: '#888' },
    { key: 'critical', label: 'Critical', n: mismatch.critical_count, color: SEV_COLOR.critical },
    { key: 'high',     label: 'High',     n: mismatch.high_count,     color: SEV_COLOR.high },
    { key: 'medium',   label: 'Medium',   n: mismatch.medium_count,   color: SEV_COLOR.medium },
    { key: 'low',      label: 'Low',      n: mismatch.low_count,      color: SEV_COLOR.low },
  ].filter(c => c.n > 0 || c.key === 'all');

  const consentPct  = Math.round(mismatch.consent_effectiveness_pct);
  const consentGood = mismatch.consent_effective;
  const consentColor = isInconclusive
    ? '#9ca3af'
    : consentGood
      ? '#00e676'
      : mismatch.consent_effectiveness_pct > 30
        ? '#ffd740'
        : '#ff1744';

  return (
    <div className="space-y-6">

      {/* ── Summary cards ── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {/* Mismatch score */}
        <div className="bg-panel border border-border rounded-xl p-4 flex flex-col gap-1">
          <div className="text-[10px] font-mono text-white/30 uppercase tracking-wider">Compliance Score</div>
          <div className={`text-3xl font-mono font-bold ${mismatch.mismatch_score >= 80 ? 'text-accent-green' : mismatch.mismatch_score >= 50 ? 'text-yellow-400' : 'text-red-400'}`}>
            {mismatch.mismatch_score}
          </div>
          <div className="text-[10px] font-mono text-white/30">/100</div>
        </div>

        {/* Total mismatches */}
        <div className="bg-panel border border-border rounded-xl p-4 flex flex-col gap-1">
          <div className="text-[10px] font-mono text-white/30 uppercase tracking-wider">Violations</div>
          <div className={`text-3xl font-mono font-bold ${hasMismatches ? 'text-red-400' : 'text-accent-green'}`}>
            {mismatch.total_count}
          </div>
          <div className="text-[10px] font-mono text-white/30">found</div>
        </div>

        {/* Pre-consent tracking */}
        <div className="bg-panel border border-border rounded-xl p-4 flex flex-col gap-1">
          <div className="text-[10px] font-mono text-white/30 uppercase tracking-wider">Pre-Consent Tracking</div>
          <div className={`text-2xl font-mono font-bold mt-1 ${mismatch.pre_consent_tracking ? 'text-red-400' : 'text-accent-green'}`}>
            {mismatch.pre_consent_tracking ? '⚠ Yes' : '✓ No'}
          </div>
          {mismatch.pre_consent_tracking && (
            <div className="text-[10px] font-mono text-red-400/70">
              {mismatch.pre_consent_tracker_count} tracker{mismatch.pre_consent_tracker_count !== 1 ? 's' : ''}
            </div>
          )}
        </div>

        {/* Undeclared trackers */}
        <div className="bg-panel border border-border rounded-xl p-4 flex flex-col gap-1">
          <div className="text-[10px] font-mono text-white/30 uppercase tracking-wider">Undeclared Trackers</div>
          <div className={`text-3xl font-mono font-bold ${mismatch.undeclared_tracker_count > 0 ? 'text-orange-400' : 'text-accent-green'}`}>
            {mismatch.undeclared_tracker_count}
          </div>
          <div className="text-[10px] font-mono text-white/30">not in policy</div>
        </div>
      </div>

      {/* ── Consent effectiveness bar ── */}
      <div className="bg-panel border border-border rounded-xl p-5">
        <div className="flex items-center justify-between mb-3">
          <div>
            <span className="font-mono text-sm text-white/70">Consent Effectiveness</span>
            <p className="text-xs font-mono text-white/30 mt-0.5">
                {isInconclusive
              ? 'Dynamic crawl could not reliably verify reject/accept behavior.'
                  : '% of trackers deactivated after rejecting consent'}
            </p>
          </div>
          <div className="flex items-center gap-2">
              <span className="font-mono text-2xl font-bold" style={{ color: consentColor }}>
                {isInconclusive ? 'Inconclusive' : `${consentPct}%`}
              </span>
            <span
              className="text-[10px] font-mono font-bold uppercase px-2 py-0.5 rounded-full"
              style={{ color: consentColor, background: `${consentColor}20`, border: `1px solid ${consentColor}40` }}
            >
              {isInconclusive ? 'Neutral' : consentGood ? 'Effective' : 'Ineffective'}
            </span>
          </div>
        </div>
          <div className="score-bar h-3">
            <div
              className="score-bar-fill h-3 rounded-full transition-all duration-700"
              style={{ width: isInconclusive ? '50%' : `${consentPct}%`, background: consentColor }}
            />
          </div>
          {isInconclusive ? (
            <p className="text-xs text-white/40 font-mono mt-2">
              Consent effectiveness: Inconclusive. Dynamic crawl could not reliably verify reject/accept behavior.
            </p>
          ) : !consentGood && mismatch.consent_effectiveness_pct < 50 ? (
            <p className="text-xs text-red-400/70 font-mono mt-2">
              ⚠ Rejecting consent has little effect on tracking — this may violate GDPR Art. 7.
            </p>
          ) : null}
      </div>

      {/* ── Undeclared tracker names ── */}
      {mismatch.undeclared_tracker_names.length > 0 && (
        <div className="bg-panel border border-border rounded-xl p-5">
          <div className="text-[10px] font-mono text-orange-400/70 uppercase tracking-wider mb-3">
            Trackers Active But Not Named in Policy
          </div>
          <div className="flex flex-wrap gap-2">
            {mismatch.undeclared_tracker_names.map((name, i) => (
              <span
                key={i}
                className="text-xs font-mono px-3 py-1 rounded-full"
                style={{ background: 'rgba(255,145,0,0.10)', border: '1px solid rgba(255,145,0,0.25)', color: '#ff9100' }}
              >
                {name}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* ── Summary ── */}
      {summary && (
        <div className="bg-panel border border-border rounded-xl p-5">
          <div className="text-[10px] font-mono text-white/30 uppercase tracking-wider mb-2">Analysis Summary</div>
          <p className="text-sm font-sans text-white/60 leading-relaxed">{summary}</p>
        </div>
      )}

      {/* ── Mismatch list ── */}
      {hasMismatches ? (
        <div>
          {/* Severity filter tabs */}
          <div className="flex gap-2 flex-wrap mb-4">
            {counts.map(c => (
              <button
                key={c.key}
                onClick={() => setSeverityFilter(c.key)}
                className="text-xs font-mono px-3 py-1.5 rounded-full border transition-colors"
                style={{
                  borderColor: severityFilter === c.key ? c.color : 'rgba(255,255,255,0.10)',
                  color: severityFilter === c.key ? c.color : 'rgba(255,255,255,0.40)',
                  background: severityFilter === c.key ? `${c.color}15` : 'transparent',
                }}
              >
                {c.label} ({c.n})
              </button>
            ))}
          </div>

          <div className="space-y-3">
            {filtered.map((m, i) => <MismatchCard key={i} m={m} />)}
          </div>
        </div>
      ) : isInconclusive ? (
        <div className="bg-panel border border-border rounded-xl p-8 flex flex-col items-center">
          <div className="text-4xl mb-3">ℹ️</div>
          <div className="font-mono text-sm text-white/70">Mismatch analysis inconclusive</div>
          <div className="text-xs font-mono text-white/30 mt-1 text-center max-w-md">
            Dynamic crawl could not reliably verify reject/accept behavior, so no mismatch verdict is shown.
          </div>
        </div>
      ) : (
        <div className="bg-panel border border-border rounded-xl p-8 flex flex-col items-center">
          <div className="text-4xl mb-3">✅</div>
          <div className="font-mono text-sm text-accent-green">No policy-behaviour mismatches detected</div>
          <div className="text-xs font-mono text-white/30 mt-1">
            The site's behaviour appears consistent with its privacy policy claims.
          </div>
        </div>
      )}
    </div>
  );
}
