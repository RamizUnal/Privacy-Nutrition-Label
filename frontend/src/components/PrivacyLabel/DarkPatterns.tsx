import React, { useState } from 'react';
import type { AnalysisResult, DarkPatternAnalysis, DarkPattern } from '../../types';
import PolicyTextPanel from './PolicyTextPanel';

interface Props {
  analysis: DarkPatternAnalysis;
  result: AnalysisResult;
}

const SEVERITY_COLORS: Record<string, string> = {
  high: '#ff1744', medium: '#ff9100', low: '#ffd740',
};
const RISK_CONFIG: Record<string, { color: string; icon: string; label: string }> = {
  critical: { color: '#ff1744', icon: '🚨', label: 'Critical' },
  high: { color: '#ff6b00', icon: '⚠️', label: 'High' },
  medium: { color: '#ffd740', icon: '⚠', label: 'Medium' },
  low: { color: '#22c55e', icon: 'ℹ', label: 'Low' },
  none: { color: '#00e676', icon: '✓', label: 'None Detected' },
};

function ExtractionSource({ result }: { result: AnalysisResult }) {
  const source = result.ai_extraction?.dark_patterns_source;
  const isAI = source === 'ai';

  return (
    <div className={`rounded-xl border px-4 py-3 ${
      isAI ? 'border-violet-500/30 bg-violet-950/15' : 'border-white/10 bg-panel'
    }`}>
      <div className="font-mono text-xs uppercase tracking-wider text-white/35">
        Extraction source
      </div>
      <div className={`mt-1 font-mono text-sm ${isAI ? 'text-violet-300' : 'text-white/45'}`}>
        {isAI ? 'LLM analysis with policy quotes' : 'Pattern fallback'}
      </div>
    </div>
  );
}

export default function DarkPatterns({ analysis, result }: Props) {
  const [expanded, setExpanded] = useState<string | null>(null);

  if (!analysis) {
    return (
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.75fr)] gap-6 items-start">
        <div className="text-center py-16 text-white/30 font-mono text-sm">Dark pattern data unavailable.</div>
        <div className="xl:sticky xl:top-32">
          <PolicyTextPanel result={result} />
        </div>
      </div>
    );
  }

  const riskConfig = RISK_CONFIG[analysis.overall_risk] || RISK_CONFIG.none;

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.75fr)] gap-6 items-start">
      <div className="space-y-6">
        <ExtractionSource result={result} />

      {/* Overall risk */}
      <div className="bg-panel border rounded-xl p-6 flex items-center gap-6" style={{ borderColor: `${riskConfig.color}30` }}>
        <div className="text-5xl">{riskConfig.icon}</div>
        <div>
          <div className="font-mono text-xs text-white/40 uppercase tracking-wider mb-1">Dark Pattern Risk</div>
          <div className="font-display text-2xl font-bold" style={{ color: riskConfig.color }}>
            {riskConfig.label}
          </div>
          <div className="flex gap-4 mt-2 text-xs font-mono">
            <span className="text-red-400">{analysis.high_severity_count} high</span>
            <span className="text-orange-400">{analysis.medium_severity_count} medium</span>
            <span className="text-yellow-400">{analysis.low_severity_count} low</span>
          </div>
          <div className="mt-2 text-xs font-mono text-white/30">
            Consent quality: <span className={`${
              analysis.consent_mechanism_quality === 'good' ? 'text-green-400' :
              analysis.consent_mechanism_quality === 'adequate' ? 'text-yellow-400' : 'text-red-400'
            }`}>{analysis.consent_mechanism_quality}</span>
          </div>
        </div>
      </div>

      {/* Regulatory context */}
      <div className="bg-surface border border-border rounded-xl p-4">
        <p className="text-xs font-mono text-white/30 leading-relaxed">
          Dark patterns in consent interfaces are explicitly prohibited under{' '}
          <span className="text-white/50">EDPB Guidelines 03/2022</span> (effective Aug 2022).
          The EDPB identifies patterns including: Interface Interference, Nagging, Obstruction,
          Forced Action, Misdirection, and Confirmshaming as invalid consent mechanisms under GDPR Art. 4(11).
          Fines: up to €20M or 4% of global turnover.
        </p>
      </div>

      {/* Detected patterns */}
      {analysis.detected.length > 0 ? (
        <div className="space-y-3">
          <h3 className="font-mono text-xs text-white/40 uppercase tracking-wider">
            Detected Patterns ({analysis.detected.length})
          </h3>
          {analysis.detected.map((dp, i) => {
            const isExpanded = expanded === dp.pattern_type;
            const color = SEVERITY_COLORS[dp.severity] || '#888';
            return (
              <div
                key={i}
                className="rounded-xl border overflow-hidden cursor-pointer hover:border-white/20 transition-all"
                style={{ borderColor: `${color}30`, background: `${color}05` }}
                onClick={() => setExpanded(isExpanded ? null : dp.pattern_type)}
              >
                <div className="p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        <span className="font-sans text-sm font-semibold text-white/85">{dp.name}</span>
                        <span
                          className="px-2 py-0.5 rounded text-xs font-mono font-bold uppercase"
                          style={{ color, background: `${color}15`, border: `1px solid ${color}30` }}
                        >
                          {dp.severity}
                        </span>
                        <span className="text-xs font-mono text-white/25">
                          Confidence: {(dp.confidence * 100).toFixed(0)}%
                        </span>
                      </div>
                      <p className="text-xs font-sans text-white/40 leading-relaxed">{dp.description}</p>
                      <p className="text-xs font-mono text-white/20 mt-1">Ref: {dp.gdpr_reference}</p>
                    </div>
                    <span className="text-white/30 text-xs font-mono flex-shrink-0">
                      {isExpanded ? '▲' : '▼'}
                    </span>
                  </div>

                  {isExpanded && dp.evidence.length > 0 && (
                    <div className="mt-4 pt-4 border-t" style={{ borderColor: `${color}20` }}>
                      <p className="text-xs font-mono text-white/30 uppercase tracking-wider mb-2">Evidence:</p>
                      {dp.evidence.map((ev, j) => (
                        <div key={j} className="p-3 rounded bg-black/30 border border-white/5 mb-2">
                          <p className="text-xs font-mono leading-relaxed break-words" style={{ color: `${color}70` }}>
                            {ev}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="bg-panel border border-green-800/40 rounded-xl p-6 text-center">
          <div className="text-4xl mb-3">✓</div>
          <p className="font-mono text-sm text-green-400 font-semibold">No Dark Patterns Detected</p>
          <p className="text-xs text-green-400/50 mt-2">
            The policy text does not contain common dark pattern language.
            Note: visual inspection of cookie banners may reveal additional patterns not detectable from text alone.
          </p>
        </div>
      )}

      {/* Dark pattern glossary */}
      <div className="bg-panel border border-border rounded-xl p-5">
        <h3 className="font-mono text-xs text-white/40 uppercase tracking-wider mb-3">Dark Pattern Reference (EDPB 03/2022)</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs font-mono">
          {[
            ['Confirmshaming', 'Guilt-inducing opt-out language'],
            ['Hidden Opt-Out', 'Withdrawal harder than consent'],
            ['Pre-Ticked Boxes', 'Invalid under GDPR Art. 4(11)'],
            ['Bundled Consent', 'Tied to service terms'],
            ['Nagging', 'Repeatedly re-requesting after refusal'],
            ['Misdirection', 'Framing data sale as user benefit'],
            ['Obstruction', 'Making rights exercise difficult'],
            ['False Urgency', 'Pressure to accept immediately'],
          ].map(([name, desc]) => (
            <div key={name} className="flex gap-2 text-white/35">
              <span className="text-red-400/60 flex-shrink-0">→</span>
              <span><span className="text-white/50">{name}:</span> {desc}</span>
            </div>
          ))}
        </div>
      </div>
      </div>

      <div className="xl:sticky xl:top-32">
        <PolicyTextPanel result={result} />
      </div>
    </div>
  );
}
