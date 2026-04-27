import React, { useState } from 'react';
import type { TrackerResult, RuntimeObservations } from '../../types';

interface Props {
  trackers: TrackerResult;
  runtime?: RuntimeObservations;
}

const RISK_COLORS: Record<string, string> = {
  low: '#22c55e', medium: '#f59e0b', high: '#ff6b00', critical: '#ff2d2d',
};
const SOURCE_ICONS: Record<string, string> = {
  script: '📜', pixel: '🔲', iframe: '🖼️', inline: '⚙️',
};

export default function Trackers({ trackers, runtime }: Props) {
  const [filter, setFilter] = useState('all');

  if (!trackers && !runtime?.available) return (
    <div className="text-center py-16 text-white/30 font-mono text-sm">
      Tracker data unavailable. Homepage may not have been accessible.
    </div>
  );

  const allTrackers = trackers.trackers || [];
  const filtered = filter === 'all' ? allTrackers : allTrackers.filter(t => t.risk === filter);
  const runtimeAvailable = !!runtime?.available;
  const runtimeQuality = runtime?.quality || {};
  const runtimeInconclusive =
    !!runtime?.requires_human ||
    runtimeQuality.usable_for_scoring === false ||
    runtimeQuality.usable_for_mismatch === false;

  const runtimeStates = runtime?.states || {};
  const s0 = runtimeStates.S0;
  const s1 = runtimeStates.S1;
  const s2 = runtimeStates.S2;
  const knownMatching = runtime?.known_tracker_matching_available !== false;
  const runtimeKnownTrackerNames = Array.from(new Set([
    ...(s0?.known_tracker_names || []),
    ...(s1?.known_tracker_names || []),
    ...(s2?.known_tracker_names || []),
  ])).slice(0, 20);
  const runtimeThirdPartyTotal = (s0?.third_party_request_count || 0) + (s1?.third_party_request_count || 0) + (s2?.third_party_request_count || 0);

  return (
    <div className="space-y-6">
      {runtimeAvailable && (
        <div className={`border rounded-xl p-4 ${runtimeInconclusive ? 'border-yellow-800/50 bg-yellow-900/10' : 'border-green-800/40 bg-green-900/10'}`}>
          <p className={`font-mono text-xs ${runtimeInconclusive ? 'text-yellow-300/80' : 'text-green-300/80'}`}>
            {runtimeInconclusive
              ? 'Runtime crawl unavailable or inconclusive; falling back to static homepage detector.'
              : 'Runtime browser crawl is the primary evidence source for this view.'}
          </p>
          {runtimeInconclusive && (
            <p className="text-[11px] text-yellow-300/60 mt-2 font-mono">
              Runtime crawl inconclusive{(runtime?.human_reasons || runtimeQuality.reasons || []).length ? `: ${[...(runtime?.human_reasons || []), ...(runtimeQuality.reasons || [])].join(', ')}` : '.'}
            </p>
          )}
        </div>
      )}

      {runtimeAvailable && (
        <div className="bg-panel border border-border rounded-xl p-5">
          <h3 className="font-mono text-xs text-white/40 uppercase tracking-wider mb-3">Runtime Browser Evidence (S0/S1/S2)</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {[
              { key: 'S0', label: 'S0 Pre-Consent', state: s0 },
              { key: 'S1', label: 'S1 Reject', state: s1 },
              { key: 'S2', label: 'S2 Accept', state: s2 },
            ].map(({ key, label, state }) => (
              <div key={key} className="border border-border rounded-lg p-3 bg-surface/30">
                <div className="font-mono text-[11px] text-white/50 uppercase mb-2">{label}</div>
                <div className="text-xs text-white/60 flex justify-between"><span>Known trackers</span><span className="font-mono text-white/80">{knownMatching ? (state?.known_tracker_count ?? 0) : 'N/A'}</span></div>
                <div className="text-xs text-white/60 flex justify-between mt-1"><span>3rd-party requests</span><span className="font-mono text-white/80">{state?.third_party_request_count ?? 0}</span></div>
                <div className="text-xs text-white/60 flex justify-between mt-1"><span>3rd-party domains</span><span className="font-mono text-white/80">{(state?.third_party_domains || []).length}</span></div>
              </div>
            ))}
          </div>
          {!knownMatching && (
            <p className="text-xs text-yellow-300/70 font-mono mt-3">
              Known tracker matching is unavailable for runtime crawl; showing third-party request evidence instead. Third-party requests are not automatically trackers.
            </p>
          )}
          {knownMatching && runtimeKnownTrackerNames.length > 0 && (
            <div className="mt-3">
              <div className="text-[10px] font-mono text-white/35 uppercase tracking-wider mb-2">Runtime known tracker names</div>
              <div className="flex flex-wrap gap-2">
                {runtimeKnownTrackerNames.map((name) => (
                  <span key={name} className="px-2 py-1 rounded text-xs font-mono border border-border text-white/55 bg-surface">{name}</span>
                ))}
              </div>
            </div>
          )}
          {knownMatching && runtimeKnownTrackerNames.length === 0 && runtimeThirdPartyTotal > 0 && (
            <p className="text-xs text-white/50 font-mono mt-3">
              No known tracker database matches. Runtime third-party requests are shown separately.
            </p>
          )}
          {knownMatching && (s0?.known_tracker_count ?? 0) + (s1?.known_tracker_count ?? 0) + (s2?.known_tracker_count ?? 0) === 0 && (
            <p className="text-xs text-white/45 font-mono mt-3">
              No known tracker database matches. Runtime third-party requests are shown separately.
            </p>
          )}
        </div>
      )}

      <div className="font-mono text-[11px] text-white/40 uppercase tracking-wider">Static HTML detector results</div>

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
          {allTrackers.length === 0 ? 'No static trackers detected on homepage.' : 'No trackers match this filter.'}
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
