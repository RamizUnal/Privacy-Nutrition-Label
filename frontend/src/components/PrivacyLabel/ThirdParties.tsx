import React, { useState } from 'react';
import type { AnalysisResult, ThirdPartyAnalysis, ThirdPartyEntry } from '../../types';
import PolicyTextPanel from './PolicyTextPanel';

interface Props {
  analysis: ThirdPartyAnalysis;
  result: AnalysisResult;
}

const TRUST_COLORS: Record<string, string> = {
  trusted: '#00e676', moderate: '#ffd740',
  concerning: '#ff9100', unknown: '#888',
};

const PURPOSE_LABELS: Record<string, string> = {
  analytics: '📊 Analytics', advertising: '📣 Advertising',
  payment: '💳 Payment', customer_support: '💬 Support',
  email_marketing: '📧 Email', social_media: '📱 Social',
  hosting: '☁️ Hosting', legal_compliance: '⚖️ Legal',
};

function ExtractionSource({ result }: { result: AnalysisResult }) {
  const source = result.ai_extraction?.third_parties_source;
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
        {isAI ? 'LLM analysis with policy quotes' : 'Regex/brand-list fallback'}
      </div>
      {result.ai_extraction?.reason && (
        <div className="mt-1 font-mono text-[11px] text-white/30">
          {result.ai_extraction.reason}
        </div>
      )}
    </div>
  );
}

function TrustBar({ score }: { score: number }) {
  const color = score >= 70 ? '#00e676' : score >= 50 ? '#ffd740' : score >= 30 ? '#ff9100' : '#ff3b3b';
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full bg-white/5">
        <div className="h-full rounded-full transition-all" style={{ width: `${score}%`, background: color }} />
      </div>
      <span className="font-mono text-xs w-6 text-right" style={{ color }}>{score}</span>
    </div>
  );
}

function EvidenceQuote({ text }: { text: string }) {
  return (
    <div className="mt-2 rounded bg-black/30 border border-white/5 p-2">
      <div className="mb-1 font-mono text-[10px] uppercase tracking-wider text-white/25">
        Policy evidence
      </div>
      <p className="text-xs font-mono text-white/40 leading-relaxed break-words">
        {text}
      </p>
    </div>
  );
}

export default function ThirdParties({ analysis, result }: Props) {
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState<'trust' | 'name'>('trust');

  if (!analysis) {
    return (
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.75fr)] gap-6 items-start">
        <div className="text-center py-16 text-white/30 font-mono text-sm">No third-party data available.</div>
        <div className="xl:sticky xl:top-32">
          <PolicyTextPanel result={result} />
        </div>
      </div>
    );
  }

  const parties = (analysis.parties || [])
    .filter(p => !search || p.name.toLowerCase().includes(search.toLowerCase()) || p.category.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => sortBy === 'trust' ? a.trust_score - b.trust_score : a.name.localeCompare(b.name));

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.75fr)] gap-6 items-start">
      <div className="space-y-6">
      <ExtractionSource result={result} />

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'Total Recipients', value: analysis.count, danger: analysis.count > 10 },
          { label: 'Named Parties', value: analysis.named_count, neutral: true },
          { label: 'Advertising Partners', value: analysis.advertising_partners, danger: analysis.advertising_partners > 3 },
          { label: 'Data Brokers', value: (analysis.parties || []).filter(p => p.is_data_broker).length, danger: true },
        ].map(s => (
          <div key={s.label} className="bg-panel border border-border rounded-xl p-4">
            <div className={`text-3xl font-mono font-bold ${s.danger && (typeof s.value === 'number' && s.value > 0) ? 'text-red-400' : 'text-white/80'}`}>
              {s.value}
            </div>
            <div className="text-xs font-mono text-white/35 mt-1">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Alert: data sold */}
      {analysis.data_sold && (
        <div className="border border-red-800/50 bg-red-900/15 rounded-xl p-4 flex items-start gap-3">
          <span className="text-red-400 text-xl">💰</span>
          <div>
            <p className="font-mono text-sm text-red-400 font-semibold">Personal Data is Sold</p>
            <p className="text-xs text-red-400/60 mt-1">
              The privacy policy indicates personal data is sold to third parties.
              CCPA §1798.120 gives California residents the right to opt-out of the sale.
              GDPR generally prohibits selling personal data without explicit consent.
            </p>
          </div>
        </div>
      )}

      {/* Transfer safeguards */}
      {analysis.cross_border_transfers && (
        <div className={`border rounded-xl p-4 flex items-start gap-3 ${
          analysis.transfer_safeguards.length
            ? 'border-yellow-800/50 bg-yellow-900/10'
            : 'border-red-800/50 bg-red-900/10'
        }`}>
          <span className="text-xl">{analysis.transfer_safeguards.length ? '✈️' : '⚠️'}</span>
          <div>
            <p className={`font-mono text-sm font-semibold ${analysis.transfer_safeguards.length ? 'text-yellow-400' : 'text-red-400'}`}>
              International Data Transfers
            </p>
            {analysis.transfer_safeguards.length ? (
              <p className="text-xs text-yellow-400/60 mt-1">
                Safeguards documented: {analysis.transfer_safeguards.join(', ')}.
                GDPR Chapter V compliance indicated.
              </p>
            ) : (
              <p className="text-xs text-red-400/60 mt-1">
                Data transferred internationally without documented safeguards (SCCs, BCRs, etc.).
                Potential GDPR Chapter V violation.
              </p>
            )}
          </div>
        </div>
      )}

      {/* Sharing purposes */}
      {analysis.sharing_purposes && (
        <div className="bg-panel border border-border rounded-xl p-5">
          <h3 className="font-mono text-xs text-white/40 uppercase tracking-wider mb-3">Data Sharing Purposes Detected</h3>
          <div className="flex flex-wrap gap-2">
            {Object.entries(analysis.sharing_purposes)
              .filter(([, v]) => v)
              .map(([k]) => (
                <span key={k} className="px-3 py-1.5 rounded-full border border-border bg-surface text-xs font-mono text-white/60">
                  {PURPOSE_LABELS[k] || k}
                </span>
              ))}
          </div>
        </div>
      )}

      {/* Party list */}
      {parties.length > 0 ? (
        <div className="bg-panel border border-border rounded-xl overflow-hidden">
          <div className="p-4 border-b border-border flex items-center gap-4 flex-wrap">
            <input
              type="text" value={search} onChange={e => setSearch(e.target.value)}
              placeholder="Search parties…"
              className="bg-surface border border-border rounded px-3 py-1.5 text-sm font-mono text-white/60 placeholder-white/20 outline-none focus:border-accent-green/50 flex-1 min-w-0"
            />
            <div className="flex gap-2">
              {['trust', 'name'].map(s => (
                <button
                  key={s}
                  onClick={() => setSortBy(s as any)}
                  className={`px-3 py-1.5 rounded text-xs font-mono border transition-colors ${
                    sortBy === s ? 'border-accent-green/50 text-accent-green' : 'border-border text-white/40 hover:text-white/60'
                  }`}
                >
                  Sort: {s}
                </button>
              ))}
            </div>
          </div>

          <div className="divide-y divide-border">
            {parties.map((party, i) => (
              <div key={i} className="p-4 hover:bg-surface/50 transition-colors">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-sans text-sm font-semibold text-white/85">{party.name}</span>
                      {party.category === 'Unnamed recipient category' && (
                        <span className="px-1.5 py-0.5 rounded text-xs font-mono bg-white/5 text-white/40 border border-white/10">
                          Unnamed
                        </span>
                      )}
                      {party.is_data_broker && (
                        <span className="px-1.5 py-0.5 rounded text-xs font-mono bg-red-900/30 text-red-400 border border-red-800/40">
                          Data Broker
                        </span>
                      )}
                      {party.cross_border_transfer && (
                        <span className="px-1.5 py-0.5 rounded text-xs font-mono bg-orange-900/20 text-orange-400/70 border border-orange-800/30">
                          US-based
                        </span>
                      )}
                      {party.gdpr_compliant === true && (
                        <span className="px-1.5 py-0.5 rounded text-xs font-mono bg-green-900/20 text-green-400/70 border border-green-800/30">
                          GDPR ✓
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-3 mt-1">
                      <span className="text-xs font-mono text-white/35">{party.category}</span>
                      {party.purposes.length > 0 && (
                        <span className="text-xs font-mono text-white/25">
                          · {party.purposes.map(p => PURPOSE_LABELS[p] || p).join(', ')}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="w-32 flex-shrink-0">
                    <div className="text-xs font-mono text-white/30 mb-1.5 text-right">
                      Trust: {party.trust_label}
                    </div>
                    <TrustBar score={party.trust_score} />
                    <div className="flex gap-2 mt-2 justify-end">
                      {party.opt_out_url && (
                        <a
                          href={party.opt_out_url}
                          target="_blank" rel="noopener noreferrer"
                          className="text-xs font-mono text-accent-green/70 hover:text-accent-green transition-colors"
                          onClick={e => e.stopPropagation()}
                        >
                          Opt-Out →
                        </a>
                      )}
                    </div>
                  </div>
                </div>

                {party.evidence.length > 0 && <EvidenceQuote text={party.evidence[0]} />}
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="text-center py-8 text-white/30 font-mono text-sm">
          {analysis.unnamed_count > 0
            ? `${analysis.unnamed_count} unnamed third parties referenced but not identified.`
            : 'No specific third parties identified in the policy.'}
        </div>
      )}
      </div>

      <div className="xl:sticky xl:top-32">
        <PolicyTextPanel result={result} />
      </div>
    </div>
  );
}
