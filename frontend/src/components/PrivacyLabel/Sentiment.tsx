import React from 'react';
import type { AnalysisResult, SentimentResult } from '../../types';
import { RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer } from 'recharts';
import PolicyTextPanel from './PolicyTextPanel';

interface Props {
  sentiment: SentimentResult;
  result: AnalysisResult;
}

const TRANSPARENCY_CONFIG: Record<string, { color: string; label: string; description: string }> = {
  high: { color: '#00e676', label: 'High Transparency', description: 'Policy is specific, accountable, and clearly written.' },
  medium: { color: '#ffd740', label: 'Medium Transparency', description: 'Policy has some specific language but could be clearer.' },
  low: { color: '#ff9100', label: 'Low Transparency', description: 'Policy is vague and uses excessive hedging language.' },
  very_low: { color: '#ff1744', label: 'Very Low Transparency', description: 'Policy is extremely vague and opaque.' },
};

const ACCOUNTABILITY_LABELS: Record<string, string> = {
  dpo_named: 'DPO Identified',
  dpo_contact: 'DPO Contact Provided',
  supervisory_authority: 'Supervisory Authority Mentioned',
  legitimate_basis: 'Lawful Basis Stated',
  privacy_by_design: 'Privacy by Design Mentioned',
  security_measures: 'Security Measures Described',
};

function ExtractionSource({ result }: { result: AnalysisResult }) {
  const source = result.ai_extraction?.transparency_source;
  const isAI = source === 'ai';

  return (
    <div className={`rounded-xl border px-4 py-3 ${
      isAI ? 'border-violet-500/30 bg-violet-950/15' : 'border-white/10 bg-panel'
    }`}>
      <div className="font-mono text-xs uppercase tracking-wider text-white/35">
        Extraction source
      </div>
      <div className={`mt-1 font-mono text-sm ${isAI ? 'text-violet-300' : 'text-white/45'}`}>
        {isAI ? 'Claude AI with policy evidence' : 'Regex/readability fallback'}
      </div>
    </div>
  );
}

export default function Sentiment({ sentiment, result }: Props) {
  if (!sentiment) {
    return (
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.75fr)] gap-6 items-start">
        <div className="text-center py-16 text-white/30 font-mono text-sm">Transparency data unavailable.</div>
        <div className="xl:sticky xl:top-32">
          <PolicyTextPanel result={result} />
        </div>
      </div>
    );
  }

  const config = TRANSPARENCY_CONFIG[sentiment.overall_transparency] || TRANSPARENCY_CONFIG.low;

  const radarData = [
    { subject: 'Specificity', value: sentiment.specificity_score },
    { subject: 'Accountability', value: sentiment.accountability_score },
    { subject: 'Transparency', value: sentiment.transparency_score },
    { subject: 'Active Voice', value: Math.round((1 - sentiment.passive_voice_ratio) * 100) },
    { subject: 'Named Parties', value: Math.min(100, sentiment.named_third_party_count * 10) },
    { subject: 'Non-Vague', value: Math.max(0, 100 - sentiment.vagueness_score) },
  ];

  function Gauge({ value, label, color, invert = false }: { value: number; label: string; color: string; invert?: boolean }) {
    const displayVal = invert ? 100 - value : value;
    const displayColor = displayVal >= 70 ? '#00e676' : displayVal >= 40 ? '#ffd740' : '#ff3b3b';
    return (
      <div className="bg-panel border border-border rounded-xl p-4">
        <div className="text-2xl font-mono font-bold" style={{ color: displayColor }}>{displayVal}%</div>
        <div className="text-xs font-mono text-white/40 mt-1">{label}</div>
        <div className="mt-2 h-1.5 rounded-full bg-white/5">
          <div className="h-full rounded-full" style={{ width: `${displayVal}%`, background: displayColor }} />
        </div>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.75fr)] gap-6 items-start">
      <div className="space-y-6">
        <ExtractionSource result={result} />

      {/* Overall */}
      <div className="bg-panel border rounded-xl p-6 flex items-start gap-6" style={{ borderColor: `${config.color}30` }}>
        <div
          className="w-12 h-12 rounded-full border-2 flex items-center justify-center flex-shrink-0"
          style={{ borderColor: config.color }}
        >
          <span className="font-mono text-lg font-bold" style={{ color: config.color }}>
            {sentiment.overall_transparency === 'high' ? 'A' :
             sentiment.overall_transparency === 'medium' ? 'B' :
             sentiment.overall_transparency === 'low' ? 'D' : 'F'}
          </span>
        </div>
        <div>
          <p className="font-mono text-xs text-white/40 uppercase tracking-wider mb-1">Policy Transparency</p>
          <p className="font-display text-lg font-bold" style={{ color: config.color }}>{config.label}</p>
          <p className="text-sm font-sans text-white/50 mt-1">{config.description}</p>
        </div>
      </div>

      {/* Metrics grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <Gauge value={sentiment.specificity_score} label="Specificity Score" color="#00ff88" />
        <Gauge value={sentiment.vagueness_score} label="Vagueness Score" color="#ff3b3b" invert />
        <Gauge value={sentiment.accountability_score} label="Accountability" color="#4488ff" />
        <Gauge value={Math.round((1 - sentiment.passive_voice_ratio) * 100)} label="Active Voice" color="#a855f7" />
        <Gauge value={Math.min(100, sentiment.named_third_party_count * 10)} label="Named Parties ×10" color="#ffd740" />
        <div className="bg-panel border border-border rounded-xl p-4">
          <div className="font-mono text-sm font-bold text-white/70">{sentiment.avg_sentence_length.toFixed(0)}</div>
          <div className="text-xs font-mono text-white/40 mt-1">Avg. Sentence Length</div>
          <div className="text-xs font-mono mt-1" style={{
            color: sentiment.avg_sentence_length > 45 ? '#ff3b3b' : sentiment.avg_sentence_length > 25 ? '#ffd740' : '#00e676'
          }}>
            {sentiment.readability_rating}
          </div>
        </div>
      </div>

      {/* Radar chart */}
      <div className="bg-panel border border-border rounded-xl p-5">
        <h3 className="font-mono text-xs text-white/40 uppercase tracking-wider mb-4">Transparency Radar</h3>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={radarData}>
              <PolarGrid stroke="rgba(255,255,255,0.06)" />
              <PolarAngleAxis dataKey="subject" tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 11, fontFamily: 'JetBrains Mono' }} />
              <Radar name="score" dataKey="value" stroke="#00ff88" fill="#00ff88" fillOpacity={0.12} strokeWidth={1.5} />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Accountability checklist */}
      <div className="bg-panel border border-border rounded-xl p-5">
        <h3 className="font-mono text-xs text-white/40 uppercase tracking-wider mb-3">Accountability Indicators (GDPR Art. 5(2))</h3>
        <div className="space-y-2">
          {Object.entries(sentiment.accountability || {}).map(([key, val]) => (
            <div key={key} className="flex items-center justify-between py-2 border-b border-border last:border-0">
              <span className="text-xs font-sans text-white/60">{ACCOUNTABILITY_LABELS[key] || key}</span>
              <span className={`font-mono text-xs font-bold ${val ? 'text-green-400' : 'text-red-400'}`}>
                {val ? '✓ Present' : '✗ Missing'}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Vague terms */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {sentiment.vague_term_examples.length > 0 && (
          <div className="bg-panel border border-border rounded-xl p-5">
            <h3 className="font-mono text-xs text-red-400/70 uppercase tracking-wider mb-3">
              ⚠ Vague Quantifiers Detected
            </h3>
            <div className="flex flex-wrap gap-2">
              {sentiment.vague_term_examples.map((t, i) => (
                <span key={i} className="px-2 py-1 rounded bg-red-900/20 border border-red-800/30 text-xs font-mono text-red-400/70">
                  {t}
                </span>
              ))}
            </div>
          </div>
        )}
        {sentiment.named_third_parties.length > 0 && (
          <div className="bg-panel border border-border rounded-xl p-5">
            <h3 className="font-mono text-xs text-green-400/70 uppercase tracking-wider mb-3">
              ✓ Named Third Parties ({sentiment.named_third_party_count})
            </h3>
            <div className="flex flex-wrap gap-2">
              {sentiment.named_third_parties.slice(0, 15).map((t, i) => (
                <span key={i} className="px-2 py-1 rounded bg-green-900/20 border border-green-800/30 text-xs font-mono text-green-400/70">
                  {t}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Voice analysis */}
      <div className="bg-panel border border-border rounded-xl p-5">
        <h3 className="font-mono text-xs text-white/40 uppercase tracking-wider mb-3">Active vs. Passive Voice Analysis</h3>
        <p className="text-xs font-sans text-white/35 leading-relaxed mb-3">
          Active voice ("We share your data with X") is more transparent than passive voice
          ("Data may be shared"). High passive voice ratio indicates intentionally vague language
          that obscures who is responsible for data processing.
        </p>
        <div className="flex items-center gap-4">
          <div className="flex-1">
            <div className="flex justify-between text-xs font-mono mb-1">
              <span className="text-green-400">Active ({sentiment.active_voice_count})</span>
              <span className="text-red-400">Passive ({sentiment.passive_voice_count})</span>
            </div>
            <div className="h-3 rounded-full bg-white/5 overflow-hidden flex">
              {sentiment.active_voice_count + sentiment.passive_voice_count > 0 && (
                <>
                  <div
                    className="h-full bg-green-500"
                    style={{ width: `${(sentiment.active_voice_count / (sentiment.active_voice_count + sentiment.passive_voice_count)) * 100}%` }}
                  />
                  <div
                    className="h-full bg-red-500"
                    style={{ width: `${(sentiment.passive_voice_ratio) * 100}%` }}
                  />
                </>
              )}
            </div>
          </div>
          <span className="font-mono text-sm text-white/40 flex-shrink-0">
            {(sentiment.passive_voice_ratio * 100).toFixed(0)}% passive
          </span>
        </div>
      </div>
      </div>

      <div className="xl:sticky xl:top-32">
        <PolicyTextPanel result={result} />
      </div>
    </div>
  );
}
