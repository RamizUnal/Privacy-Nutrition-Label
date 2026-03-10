import React, { useState } from 'react';
import type { TrackerResult, DetectedTracker } from '../../types';

interface Props { trackers: TrackerResult; }

const RISK_COLORS: Record<string, string> = {
  low: '#22c55e', medium: '#f59e0b', high: '#ff6b00', critical: '#ff2d2d',
};
const SOURCE_ICONS: Record<string, string> = {
  script: '📜', pixel: '🔲', iframe: '🖼️', inline: '⚙️',
};

export default function Trackers({ trackers }: Props) {
  const [filter, setFilter] = useState('all');

  if (!trackers) return (
    <div className="text-center py-16 text-white/30 font-mono text-sm">
      Tracker data unavailable. Homepage may not have been accessible.
    </div>
  );

  const allTrackers = trackers.trackers || [];
  const filtered = filter === 'all' ? allTrackers : allTrackers.filter(t => t.risk === filter);

  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className={`bg-panel border rounded-xl p-4 ${trackers.total_tracker_count > 10 ? 'border-red-800/50' : 'border-border'}`}>
          <div className={`text-3xl font-mono font-bold ${trackers.total_tracker_count > 10 ? 'text-red-400' : 'text-white/80'}`}>
            {trackers.total_tracker_count}
          </div>
          <div className="text-xs font-mono text-white/35 mt-1">Total Trackers</div>
        </div>
        <div className={`bg-panel border rounded-xl p-4 ${trackers.high_risk_count > 0 ? 'border-orange-800/50' : 'border-border'}`}>
          <div className={`text-3xl font-mono font-bold ${trackers.high_risk_count > 0 ? 'text-orange-400' : 'text-white/80'}`}>
            {trackers.high_risk_count}
          </div>
          <div className="text-xs font-mono text-white/35 mt-1">High-Risk</div>
        </div>
        <div className={`bg-panel border rounded-xl p-4 ${trackers.fingerprinting_detected ? 'border-red-800/50' : 'border-border'}`}>
          <div className={`text-sm font-mono font-bold mt-1 ${trackers.fingerprinting_detected ? 'text-red-400' : 'text-green-400'}`}>
            {trackers.fingerprinting_detected ? '⚠ DETECTED' : '✓ None'}
          </div>
          <div className="text-xs font-mono text-white/35 mt-1">Fingerprinting</div>
        </div>
        <div className={`bg-panel border rounded-xl p-4 ${trackers.session_recording_detected ? 'border-orange-800/50' : 'border-border'}`}>
          <div className={`text-sm font-mono font-bold mt-1 ${trackers.session_recording_detected ? 'text-orange-400' : 'text-green-400'}`}>
            {trackers.session_recording_detected ? '⚠ ACTIVE' : '✓ None'}
          </div>
          <div className="text-xs font-mono text-white/35 mt-1">Session Recording</div>
        </div>
      </div>

      {/* Fingerprinting alert */}
      {trackers.fingerprinting_detected && trackers.fingerprinting_evidence.length > 0 && (
        <div className="border border-red-800/50 bg-red-900/10 rounded-xl p-4">
          <p className="font-mono text-sm text-red-400 font-semibold mb-2">🔮 Fingerprinting Evidence</p>
          {trackers.fingerprinting_evidence.map((e, i) => (
            <p key={i} className="text-xs font-mono text-red-400/60 mt-1">→ {e}</p>
          ))}
          <p className="text-xs text-red-400/50 mt-3">
            Browser fingerprinting creates a unique identifier from your device's hardware and software characteristics.
            Unlike cookies, it cannot be cleared and persists across browsers. Most cookie consent banners do NOT cover fingerprinting.
          </p>
        </div>
      )}

      {/* Session recording alert */}
      {trackers.session_recording_detected && (
        <div className="border border-orange-800/50 bg-orange-900/10 rounded-xl p-4">
          <p className="font-mono text-sm text-orange-400 font-semibold mb-1">🎥 Session Recording Active</p>
          <p className="text-xs text-orange-400/60">
            Session recording software captures every mouse movement, click, scroll, and keystroke.
            This may inadvertently record passwords, credit card numbers, and other sensitive inputs.
            Under GDPR, this constitutes high-risk processing and typically requires a DPIA.
          </p>
        </div>
      )}

      {/* CMP detected */}
      {trackers.cmp_detected && (
        <div className="border border-green-800/40 bg-green-900/10 rounded-xl p-4 flex items-center gap-3">
          <span className="text-green-400 text-xl">✓</span>
          <div>
            <p className="font-mono text-sm text-green-400 font-semibold">Consent Manager Detected: {trackers.cmp_detected}</p>
            <p className="text-xs text-green-400/60 mt-1">A CMP helps manage cookie consent. Quality depends on implementation.</p>
          </div>
        </div>
      )}

      {/* Filter */}
      <div className="flex items-center gap-2 flex-wrap">
        {['all', 'critical', 'high', 'medium', 'low'].map(f => {
          const count = f === 'all' ? allTrackers.length : allTrackers.filter(t => t.risk === f).length;
          return (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1 rounded-full text-xs font-mono border transition-all ${
                filter === f ? 'border-white/50 text-white' : 'border-border text-white/35 hover:border-white/20'
              }`}
              style={filter === f && f !== 'all' ? { borderColor: RISK_COLORS[f], color: RISK_COLORS[f] } : {}}
            >
              {f} ({count})
            </button>
          );
        })}
      </div>

      {/* Tracker list */}
      {filtered.length > 0 ? (
        <div className="bg-panel border border-border rounded-xl overflow-hidden">
          <div className="divide-y divide-border">
            {filtered.map((t, i) => (
              <div key={i} className="p-4 hover:bg-surface/50 transition-colors">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm">{SOURCE_ICONS[t.source_type] || '📍'}</span>
                      <span className="font-sans text-sm font-semibold text-white/85">{t.name}</span>
                      {t.fingerprinting && (
                        <span className="px-1.5 py-0.5 rounded text-xs font-mono bg-red-900/30 text-red-400 border border-red-800/40">Fingerprinting</span>
                      )}
                      {t.session_recording && (
                        <span className="px-1.5 py-0.5 rounded text-xs font-mono bg-orange-900/30 text-orange-400 border border-orange-800/40">Session Recording</span>
                      )}
                    </div>
                    <div className="flex items-center gap-3 mt-1">
                      <span className="text-xs font-mono text-white/30">{t.domain}</span>
                      <span className="text-xs font-mono text-white/25">· {t.category}</span>
                      <span className="text-xs font-mono text-white/20">· {t.source_type}</span>
                    </div>
                    <p className="text-xs font-sans text-white/35 mt-1.5 leading-relaxed">{t.description}</p>
                  </div>

                  <div className="flex flex-col items-end gap-2 flex-shrink-0">
                    <span
                      className="px-2 py-0.5 rounded text-xs font-mono font-bold uppercase"
                      style={{ color: RISK_COLORS[t.risk], background: `${RISK_COLORS[t.risk]}15`, border: `1px solid ${RISK_COLORS[t.risk]}30` }}
                    >
                      {t.risk}
                    </span>
                    {t.opt_out && (
                      <a href={t.opt_out} target="_blank" rel="noopener noreferrer"
                        className="text-xs font-mono text-accent-green/60 hover:text-accent-green transition-colors">
                        Opt-Out →
                      </a>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="text-center py-8 text-white/30 font-mono text-sm">
          {allTrackers.length === 0 ? '✓ No trackers detected on homepage.' : 'No trackers match this filter.'}
        </div>
      )}

      {/* Third-party domains */}
      {(trackers.unique_third_party_domains || []).length > 0 && (
        <div className="bg-panel border border-border rounded-xl p-5">
          <h3 className="font-mono text-xs text-white/40 uppercase tracking-wider mb-3">
            All Third-Party Domains ({trackers.unique_third_party_domains.length})
          </h3>
          <div className="flex flex-wrap gap-2">
            {trackers.unique_third_party_domains.map(d => (
              <span key={d} className="px-2 py-1 rounded text-xs font-mono border border-border text-white/35 bg-surface">
                {d}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
