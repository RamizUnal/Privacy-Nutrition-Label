import React from 'react';
import type { AnalysisResult, RetentionAnalysis } from '../../types';
import PolicyTextPanel from './PolicyTextPanel';

interface Props {
  retention: RetentionAnalysis;
  result: AnalysisResult;
}

const RATING_CONFIG: Record<string, { color: string; label: string; description: string }> = {
  excellent: { color: '#00e676', label: 'Excellent', description: 'Short, well-defined retention periods' },
  good: { color: '#40c4ff', label: 'Good', description: 'Reasonable retention periods stated' },
  fair: { color: '#ffd740', label: 'Fair', description: 'Some specific periods, could be shorter' },
  poor: { color: '#ff9100', label: 'Poor', description: 'Long retention or vague periods' },
  very_poor: { color: '#ff1744', label: 'Very Poor', description: 'No specific retention or indefinite' },
  unknown: { color: '#888', label: 'Unknown', description: 'No retention information found' },
};

function ExtractionSource({ result }: { result: AnalysisResult }) {
  const source = result.ai_extraction?.retention_source;
  const isAI = source === 'ai';

  return (
    <div className={`rounded-xl border px-4 py-3 ${
      isAI ? 'border-violet-500/30 bg-violet-950/15' : 'border-white/10 bg-panel'
    }`}>
      <div className="font-mono text-xs uppercase tracking-wider text-white/35">
        Extraction source
      </div>
      <div className={`mt-1 font-mono text-sm ${isAI ? 'text-violet-300' : 'text-white/45'}`}>
        {isAI ? 'Claude AI with policy quotes' : 'Regex fallback'}
      </div>
    </div>
  );
}

export default function Retention({ retention, result }: Props) {
  if (!retention) {
    return (
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.75fr)] gap-6 items-start">
        <div className="text-center py-16 text-white/30 font-mono text-sm">Retention data unavailable.</div>
        <div className="xl:sticky xl:top-32">
          <PolicyTextPanel result={result} />
        </div>
      </div>
    );
  }

  const config = RATING_CONFIG[retention.overall_rating] || RATING_CONFIG.unknown;

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.75fr)] gap-6 items-start">
      <div className="space-y-6">
        <ExtractionSource result={result} />

        {/* Overall rating */}
        <div className="bg-panel border rounded-xl p-6 flex items-start gap-6" style={{ borderColor: `${config.color}30` }}>
          <div className="text-center flex-shrink-0">
            <div className="text-5xl font-display font-bold" style={{ color: config.color }}>
              {config.label.charAt(0)}
            </div>
            <div className="text-xs font-mono mt-1" style={{ color: `${config.color}70` }}>
              {config.label}
            </div>
          </div>
          <div className="flex-1">
            <h2 className="font-mono text-sm text-white/60 uppercase tracking-wider mb-2">Data Retention Rating</h2>
            <p className="font-sans text-white/70">{config.description}</p>
            <p className="text-xs font-mono text-white/30 mt-2">
              GDPR Art. 5(1)(e) – Storage Limitation Principle: Data must be kept "no longer than is necessary
              for the purposes for which the personal data are processed."
            </p>
          </div>
        </div>

        {/* Signal cards — each card explains in plain language what the
            check / cross actually means for THIS policy, plus the relevant
            evidence (e.g. shortest/longest period in days) when available. */}
        {(() => {
          // Pre-format the period range so we can drop it into the description.
          const fmtDays = (d: number | null | undefined): string | null => {
            if (d == null) return null;
            if (d >= 365) return `${(d / 365).toFixed(d % 365 === 0 ? 0 : 1)}y`;
            if (d >= 30) return `${Math.round(d / 30)} mo`;
            return `${d}d`;
          };
          const shortest = fmtDays(retention.shortest_days);
          const longest = fmtDays(retention.longest_days);
          const periodRange =
            shortest && longest && shortest !== longest
              ? `Range: ${shortest} – ${longest}`
              : (shortest || longest || null);

          const signals: {
            label: string;
            value: boolean;
            good: boolean;          // is "true" the desirable outcome?
            descTrue: string;       // what shown when value === true
            descFalse: string;      // what shown when value === false
          }[] = [
            {
              label: 'Specific Periods Stated',
              value: !!retention.has_specific_periods,
              good: true,
              descTrue: periodRange
                ? `Concrete time periods given. ${periodRange}.`
                : 'Concrete time periods given in the policy.',
              descFalse: 'No exact retention period is stated in the policy.',
            },
            {
              label: 'Event-Based Deletion',
              value: !!retention.has_event_based_deletion,
              good: true,
              descTrue: 'Data is deleted on a triggering event (e.g. when you close your account).',
              descFalse: 'No event-based deletion clause found (e.g. "deleted upon account closure").',
            },
            {
              label: 'Deletion on Request',
              value: !!retention.deletion_on_request,
              good: true,
              descTrue: 'You can ask the company to delete your data and they commit to doing so.',
              descFalse: 'The policy does not promise to delete your data when you ask.',
            },
            {
              label: 'Vague Retention',
              value: !!retention.has_vague_retention,
              good: false,
              descTrue: 'Policy uses non-specific language like "as long as necessary" or "as required by law".',
              descFalse: 'Retention language is reasonably specific — no vague "as needed" phrasing.',
            },
            {
              label: 'Indefinite Retention',
              value: !!retention.has_indefinite_retention,
              good: false,
              descTrue: 'Policy says some data is kept indefinitely — i.e. forever.',
              descFalse: 'No indefinite-retention clause detected.',
            },
            {
              label: 'Storage Limitation Mentioned',
              value: !!retention.storage_limitation_mentioned,
              good: true,
              descTrue: 'Policy explicitly acknowledges the GDPR Art. 5(1)(e) storage-limitation principle.',
              descFalse: 'The storage-limitation principle (GDPR Art. 5(1)(e)) is not referenced.',
            },
          ];

          return (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {signals.map(s => {
                const isPositiveOutcome = (s.good && s.value) || (!s.good && !s.value);
                const isWarning = !s.good && s.value;
                const isMissing = s.good && !s.value;
                const borderClass = isWarning
                  ? 'border-red-800/40'
                  : isPositiveOutcome
                  ? 'border-green-800/40'
                  : 'border-border';
                const iconColor = isWarning
                  ? 'text-red-400'
                  : isPositiveOutcome
                  ? 'text-green-400'
                  : 'text-white/30';
                const icon = isWarning ? '⚠' : isPositiveOutcome ? '✓' : '✗';
                const desc = s.value ? s.descTrue : s.descFalse;
                return (
                  <div key={s.label} className={`bg-panel border rounded-xl p-4 ${borderClass}`}>
                    <div className="flex items-start gap-2 mb-1.5">
                      <span className={`text-lg font-mono font-bold leading-none ${iconColor}`}>{icon}</span>
                      <span className="font-mono text-xs text-white/65 uppercase tracking-wide leading-tight">
                        {s.label}
                      </span>
                    </div>
                    <p className={`text-[11px] font-sans leading-relaxed ${
                      isMissing ? 'text-white/35 italic' : 'text-white/55'
                    }`}>
                      {desc}
                    </p>
                  </div>
                );
              })}
            </div>
          );
        })()}

        {/* Retention items */}
        {retention.items && retention.items.length > 0 && (
          <div className="bg-panel border border-border rounded-xl overflow-hidden">
            <div className="px-5 py-3 border-b border-border">
              <h3 className="font-mono text-xs text-white/40 uppercase tracking-wider">Detected Retention Periods</h3>
            </div>
            <div className="divide-y divide-border">
              {retention.items.map((item, i) => {
                const cfg = RATING_CONFIG[item.rating] || RATING_CONFIG.unknown;
                return (
                  <div key={i} className="px-5 py-4">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1.5">
                          <span
                            className="px-2 py-0.5 rounded text-xs font-mono font-semibold"
                            style={{ color: cfg.color, background: `${cfg.color}15`, border: `1px solid ${cfg.color}30` }}
                          >
                            {item.period_text}
                          </span>
                          <span className={`text-xs font-mono px-1.5 py-0.5 rounded border ${
                            item.period_type === 'vague' ? 'text-red-400/70 border-red-800/30 bg-red-900/10' :
                            item.period_type === 'event_based' ? 'text-green-400/70 border-green-800/30 bg-green-900/10' :
                            'text-blue-400/70 border-blue-800/30 bg-blue-900/10'
                          }`}>
                            {item.period_type.replace('_', ' ')}
                          </span>
                        </div>
                        {item.context && (
                          <p className="text-xs font-mono text-white/30 leading-relaxed break-words">{item.context}</p>
                        )}
                      </div>
                      <div className="flex-shrink-0 text-right">
                        <div className="text-xs font-mono font-semibold" style={{ color: cfg.color }}>{cfg.label}</div>
                        {item.period_days && (
                          <div className="text-xs font-mono text-white/25 mt-0.5">
                            {item.period_days >= 365
                              ? `${(item.period_days / 365).toFixed(1)}y`
                              : `${item.period_days}d`}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* GDPR reference */}
        <div className="bg-surface border border-border rounded-xl p-5">
          <h3 className="font-mono text-xs text-white/40 uppercase tracking-wider mb-3">Regulatory Context</h3>
          <div className="space-y-2 text-xs font-mono text-white/35 leading-relaxed">
            <p>→ GDPR Art. 5(1)(e): Storage Limitation – data must be "kept in a form which permits identification of data subjects for no longer than is necessary."</p>
            <p>→ EDPB Guidelines recommend specific retention periods for each data category/processing purpose.</p>
            <p>→ Best practice: 30 days for session data, 13 months for analytics, 3 years for contract data, per ICO guidance.</p>
            <p>→ Indefinite retention without documented justification is a common GDPR enforcement finding (see CNIL, DPC decisions).</p>
          </div>
        </div>
      </div>

      <div className="xl:sticky xl:top-32">
        <PolicyTextPanel result={result} />
      </div>
    </div>
  );
}
