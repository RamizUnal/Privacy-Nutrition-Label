import React, { useState } from 'react';
import type { AnalysisResult, DataType } from '../../types';
import PolicyTextPanel from './PolicyTextPanel';

interface Props {
  dataTypes: DataType[];
  result: AnalysisResult;
}

const SENSITIVITY_ORDER = { critical: 0, high: 1, medium: 2, low: 3 };

function ExtractionSource({ result }: { result: AnalysisResult }) {
  const source = result.ai_extraction?.data_categories_source;
  const isAI = source === 'ai';

  return (
    <div className={`rounded-xl border px-4 py-3 ${
      isAI
        ? 'border-violet-500/30 bg-violet-950/15'
        : 'border-white/10 bg-panel'
    }`}>
      <div className="font-mono text-xs uppercase tracking-wider text-white/35">
        Extraction source
      </div>
      <div className={`mt-1 font-mono text-sm ${isAI ? 'text-violet-300' : 'text-white/45'}`}>
        {isAI ? 'LLM analysis with policy quotes' : 'Regex/taxonomy fallback'}
      </div>
      {result.ai_extraction?.reason && (
        <div className="mt-1 font-mono text-[11px] text-white/30">
          {result.ai_extraction.reason}
        </div>
      )}
    </div>
  );
}

function EvidenceQuote({ text }: { text: string }) {
  return (
    <div className="rounded bg-black/30 border border-white/5 p-2">
      <p className="text-xs font-mono text-white/45 leading-relaxed break-words">
        {text}
      </p>
    </div>
  );
}

export default function DataTypes({ dataTypes, result }: Props) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>('all');

  const filtered = dataTypes.filter(d =>
    filter === 'all' || d.sensitivity === filter
  );

  const grouped = {
    critical: dataTypes.filter(d => d.sensitivity === 'critical'),
    high: dataTypes.filter(d => d.sensitivity === 'high'),
    medium: dataTypes.filter(d => d.sensitivity === 'medium'),
    low: dataTypes.filter(d => d.sensitivity === 'low'),
  };

  if (!dataTypes.length) {
    return (
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.75fr)] gap-6 items-start">
        <div className="text-center py-16 text-white/30 font-mono text-sm">
          No data types detected. Policy may not have been found or is very limited.
        </div>
        <div className="xl:sticky xl:top-32">
          <PolicyTextPanel result={result} />
        </div>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.75fr)] gap-6 items-start">
      <div className="space-y-6">
        <ExtractionSource result={result} />

        {/* Filters */}
        <div className="flex items-center gap-2 flex-wrap">
          {([
            ['all', 'All', undefined],
            ['critical', 'Critical', '#ff2d2d'],
            ['high', 'High', '#ff6b00'],
            ['medium', 'Medium', '#f59e0b'],
            ['low', 'Low', '#22c55e'],
          ] as const).map(([val, label, color]) => (
            <button
              key={val}
              onClick={() => setFilter(val)}
              className={`px-3 py-1 rounded-full text-xs font-mono border transition-all ${
                filter === val ? 'border-white/40 text-white' : 'border-border text-white/40 hover:border-white/20'
              }`}
              style={filter === val && color ? { borderColor: color, color } : {}}
            >
              {label} {val !== 'all' && `(${grouped[val as keyof typeof grouped]?.length ?? 0})`}
            </button>
          ))}
          <span className="ml-auto font-mono text-xs text-white/30">
            {filtered.length} type{filtered.length !== 1 ? 's' : ''} collected
          </span>
        </div>

        {/* GDPR special categories banner */}
        {grouped.critical.some(d => d.gdpr_special_category) && (
          <div className="border border-red-800/50 bg-red-900/10 rounded-xl p-4">
            <div className="flex items-start gap-3">
              <span className="text-2xl">!</span>
              <div>
                <p className="font-mono text-sm text-red-400 font-semibold">GDPR Special Categories Detected</p>
                <p className="text-xs text-red-400/60 mt-1">
                  The following data types are classified as "special categories" under GDPR Article 9 and require
                  explicit consent, a legal exception, and typically a Data Protection Impact Assessment (DPIA):
                </p>
                <div className="flex flex-wrap gap-2 mt-2">
                  {grouped.critical.filter(d => d.gdpr_special_category).map(d => (
                    <span key={d.category_id} className="px-2 py-0.5 rounded text-xs font-mono bg-red-900/30 text-red-400 border border-red-800/40">
                      {d.icon} {d.name}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Data type cards */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          {filtered.map(dt => {
            const isExpanded = expanded === dt.category_id;
            return (
              <div
                key={dt.category_id}
                className="rounded-xl border overflow-hidden cursor-pointer transition-all hover:border-white/20"
                style={{
                  borderColor: isExpanded ? dt.color : `${dt.color}30`,
                  background: `${dt.color}05`,
                }}
                onClick={() => setExpanded(isExpanded ? null : dt.category_id)}
              >
                <div className="p-4">
                  {/* Header */}
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xl">{dt.icon}</span>
                      <div>
                        <p className="font-sans text-sm font-semibold text-white/85">{dt.name}</p>
                        <p className="font-mono text-xs" style={{ color: `${dt.color}90` }}>
                          {dt.gdpr_article}
                        </p>
                      </div>
                    </div>
                    <div className="flex flex-col items-end gap-1 flex-shrink-0">
                      <span
                        className="px-2 py-0.5 rounded text-xs font-mono font-bold uppercase"
                        style={{ color: dt.color, background: `${dt.color}15`, border: `1px solid ${dt.color}30` }}
                      >
                        {dt.sensitivity}
                      </span>
                      {dt.gdpr_special_category && (
                        <span className="text-xs font-mono text-red-400 border border-red-800/40 px-1.5 py-0.5 rounded">
                          Art.9
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Sharing badge */}
                  {dt.shared && (
                    <div className="flex items-center gap-1.5 mt-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-orange-400" />
                      <span className="text-xs font-mono text-orange-400/80">Shared with 3rd parties</span>
                    </div>
                  )}

                  {/* CCPA category */}
                  <p className="text-xs font-mono text-white/25 mt-1.5">{dt.ccpa_category}</p>

                  {dt.evidence.length > 0 && (
                    <div className="mt-3">
                      <p className="mb-1 text-xs font-mono text-white/30 uppercase tracking-wider">
                        Policy evidence
                      </p>
                      <EvidenceQuote text={dt.evidence[0]} />
                    </div>
                  )}

                  {/* Expanded content */}
                  {isExpanded && (
                    <div className="mt-3 pt-3 border-t" style={{ borderColor: `${dt.color}20` }}>
                      <p className="text-xs font-sans text-white/50 leading-relaxed mb-2">
                        {dt.risk_description}
                      </p>
                      {dt.evidence.length > 1 && (
                        <div className="space-y-2">
                          <p className="text-xs font-mono text-white/30 uppercase tracking-wider">More evidence</p>
                          {dt.evidence.slice(1).map((ev, i) => (
                            <EvidenceQuote key={i} text={ev} />
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Expand indicator */}
                  <div className="mt-2 flex justify-end">
                    <span className="text-xs font-mono" style={{ color: `${dt.color}50` }}>
                      {isExpanded ? 'less' : 'details'}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="xl:sticky xl:top-32">
        <PolicyTextPanel result={result} />
      </div>
    </div>
  );
}
