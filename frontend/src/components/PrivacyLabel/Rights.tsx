import React, { useState } from 'react';
import type { AnalysisResult, RightsAnalysis, RightCoverage } from '../../types';
import PolicyTextPanel from './PolicyTextPanel';

interface Props {
  rights: RightsAnalysis;
  result: AnalysisResult;
}

function RightRow({ right }: { right: RightCoverage }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div
      className={`p-4 border-b border-border hover:bg-surface/50 cursor-pointer transition-colors`}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3 flex-1">
          <div className={`mt-0.5 w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 ${
            right.covered ? 'bg-green-900/40 border border-green-800/60' : 'bg-red-900/40 border border-red-800/60'
          }`}>
            <span className={`text-xs ${right.covered ? 'text-green-400' : 'text-red-400'}`}>
              {right.covered ? '✓' : '✗'}
            </span>
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-sans text-sm text-white/80">{right.name}</span>
              <span className="font-mono text-xs text-white/25 px-1.5 py-0.5 border border-border rounded">
                {right.article}
              </span>
            </div>
            <p className="text-xs font-sans text-white/35 mt-0.5 leading-relaxed">{right.description}</p>
          </div>
        </div>
        <span className="text-white/20 text-xs font-mono flex-shrink-0">{expanded ? '▲' : '▼'}</span>
      </div>
      {expanded && right.evidence && (
        <div className="mt-3 ml-8 p-3 rounded bg-black/30 border border-white/5">
          <p className="text-xs font-mono text-white/40 leading-relaxed break-words">{right.evidence}</p>
        </div>
      )}
      {expanded && !right.covered && (
        <div className="mt-3 ml-8 p-3 rounded bg-red-900/10 border border-red-800/30">
          <p className="text-xs font-mono text-red-400/60">
            This right is not mentioned in the policy. Under {right.article}, the controller
            must inform data subjects of this right in their privacy notice.
          </p>
        </div>
      )}
    </div>
  );
}

function ExtractionSource({ result }: { result: AnalysisResult }) {
  const source = result.ai_extraction?.rights_source;
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

export default function Rights({ rights, result }: Props) {
  const [view, setView] = useState<'gdpr' | 'ccpa'>('gdpr');

  if (!rights) {
    return (
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.75fr)] gap-6 items-start">
        <div className="text-center py-16 text-white/30 font-mono text-sm">Rights data unavailable.</div>
        <div className="xl:sticky xl:top-32">
          <PolicyTextPanel result={result} />
        </div>
      </div>
    );
  }

  const gdprItems = Object.values(rights.gdpr || {});
  const ccpaItems = Object.values(rights.ccpa || {});

  function ScoreBadge({ score, grade }: { score: number; grade: string }) {
    const color = score >= 75 ? '#00e676' : score >= 50 ? '#ffd740' : score >= 30 ? '#ff9100' : '#ff1744';
    return (
      <div className="flex items-center gap-2">
        <div className="h-1.5 w-20 rounded-full bg-white/5">
          <div className="h-full rounded-full" style={{ width: `${score}%`, background: color }} />
        </div>
        <span className="font-mono text-sm font-bold" style={{ color }}>{score}%</span>
        <span className="font-mono text-sm font-bold" style={{ color }}>{grade}</span>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.75fr)] gap-6 items-start">
      <div className="space-y-6">
        <ExtractionSource result={result} />

      {/* Score overview */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="bg-panel border border-border rounded-xl p-5">
          <div className="font-mono text-xs text-white/40 uppercase tracking-wider mb-3">GDPR Rights Coverage</div>
          <ScoreBadge score={rights.gdpr_score} grade={rights.gdpr_grade} />
          <p className="text-xs font-mono text-white/25 mt-2">
            {gdprItems.filter(r => r.covered).length}/{gdprItems.length} rights addressed
          </p>
        </div>
        <div className="bg-panel border border-border rounded-xl p-5">
          <div className="font-mono text-xs text-white/40 uppercase tracking-wider mb-3">CCPA/CPRA Rights Coverage</div>
          <ScoreBadge score={rights.ccpa_score} grade={rights.ccpa_grade} />
          <p className="text-xs font-mono text-white/25 mt-2">
            {ccpaItems.filter(r => r.covered).length}/{ccpaItems.length} rights addressed
          </p>
        </div>
      </div>

      {/* Special signals */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'DNT Mentioned', value: rights.dnt_mentioned, icon: '🔕' },
          { label: 'DNT Honored', value: rights.dnt_honored, icon: '✋' },
          { label: 'Global Privacy Control', value: rights.global_privacy_control, icon: '🌐' },
          { label: 'Other Frameworks', value: (rights.frameworks_mentioned || []).length > 0, icon: '📋' },
        ].map(s => (
          <div key={s.label} className={`bg-panel border rounded-xl p-4 ${s.value ? 'border-green-800/40' : 'border-border'}`}>
            <div className="text-xl mb-1">{s.icon}</div>
            <div className={`text-xs font-mono font-bold ${s.value ? 'text-green-400' : 'text-white/30'}`}>
              {s.value ? 'Yes' : 'No'}
            </div>
            <div className="text-xs font-mono text-white/35 mt-0.5">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Frameworks */}
      {(rights.frameworks_mentioned || []).length > 0 && (
        <div className="bg-panel border border-border rounded-xl p-4">
          <h3 className="font-mono text-xs text-white/40 uppercase tracking-wider mb-2">Regulatory Frameworks Referenced</h3>
          <div className="flex flex-wrap gap-2">
            {rights.frameworks_mentioned.map(f => (
              <span key={f} className="px-3 py-1.5 rounded border border-accent-green/30 bg-accent-green/5 text-accent-green text-xs font-mono">
                ✓ {f}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Tab: GDPR / CCPA */}
      <div className="bg-panel border border-border rounded-xl overflow-hidden">
        <div className="flex border-b border-border">
          {(['gdpr', 'ccpa'] as const).map(v => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`flex-1 py-3 font-mono text-xs uppercase tracking-wider transition-colors ${
                view === v ? 'text-accent-green border-b-2 border-accent-green' : 'text-white/40 hover:text-white/60'
              }`}
            >
              {v === 'gdpr' ? 'GDPR (EU) Rights' : 'CCPA/CPRA (CA) Rights'}
            </button>
          ))}
        </div>

        <div className="divide-y divide-border">
          {(view === 'gdpr' ? gdprItems : ccpaItems).map(right => (
            <RightRow key={right.right_id} right={right} />
          ))}
        </div>
      </div>

      {/* Cookie compliance */}
      {rights.cookie_compliance && (
        <div className="bg-panel border border-border rounded-xl p-5">
          <h3 className="font-mono text-xs text-white/40 uppercase tracking-wider mb-3">Cookie Compliance Signals</h3>
          <div className="grid grid-cols-2 gap-3">
            {Object.entries(rights.cookie_compliance).map(([key, val]) => (
              <div key={key} className="flex items-center gap-2">
                <span className={val ? 'text-green-400' : 'text-red-400'}>
                  {val ? '✓' : '✗'}
                </span>
                <span className="text-xs font-mono text-white/50">{key.replace(/_/g, ' ')}</span>
              </div>
            ))}
          </div>
        </div>
      )}
      </div>

      <div className="xl:sticky xl:top-32">
        <PolicyTextPanel result={result} />
      </div>
    </div>
  );
}
