import React from 'react';
import type { DynamicCrawlingResult } from '../../types';

interface Props {
  dynamic: DynamicCrawlingResult | undefined;
}

export default function DynamicScan({ dynamic }: Props) {
  if (!dynamic) {
    return (
      <div className="text-center py-16 text-white/30 font-mono text-sm">
        Dynamic crawling data (S0/S1/S2) is unavailable. This may take longer to generate or was not enabled.
      </div>
    );
  }

  const { S0, S1, S2, mismatch_detected } = dynamic;
  const quality = dynamic.state_quality || {};
  const requiresHuman = !!dynamic.requires_human;
  const qualityReasons = [
    ...(dynamic.human_reasons || []),
    ...(quality.reasons || []),
  ];
  const runtimeInconclusive =
    requiresHuman ||
    quality.usable_for_scoring === false ||
    quality.usable_for_mismatch === false;

  const stateful = dynamic._stateful?.states || {};
  const s1ClickVerification = stateful.S1?.click_verification;
  const s2ClickVerification = stateful.S2?.click_verification;

  const renderClickSummary = (label: string, cv: Record<string, any> | undefined) => {
    if (!cv) return null;
    const fields = [
      `clicked=${String(cv.clicked)}`,
      `likely_click_worked=${String(cv.likely_click_worked)}`,
      `banner_before=${String(cv.banner_before)}`,
      `banner_after=${String(cv.banner_after)}`,
      `consent_storage_changed=${String(cv.consent_storage_changed)}`,
      `requests_after_click=${String(cv.requests_after_click)}`,
      `third_party_requests_after_click=${String(cv.third_party_requests_after_click)}`,
    ];
    const evidence = Array.isArray(cv.evidence) ? cv.evidence.join(', ') : 'none';
    const cookieNames = Array.isArray(cv.new_cookie_names_after_click) && cv.new_cookie_names_after_click.length > 0
      ? cv.new_cookie_names_after_click.join(', ')
      : 'none';

    return (
      <div key={label} className="text-xs text-white/45 font-mono space-y-1">
        <div>{label}: {fields.join(' · ')}</div>
        <div>new_cookie_names={cookieNames}</div>
        <div>evidence={evidence}</div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <div className="bg-panel border border-border rounded-xl p-5">
        <h3 className="font-mono text-sm text-white/60 mb-2 uppercase tracking-wider font-semibold">
          3-State Dynamic Crawling
        </h3>
        <p className="text-xs text-white/40 mb-5 leading-relaxed">
          The automated crawler visited the site in 3 distinct consent states to verify if tracking behavior matches the stated policy.
        </p>
        <p className="text-xs text-white/40 mb-5 leading-relaxed">
          These counts come from a live browser crawl. Trackers/Cookies tabs now use this runtime evidence first when available.
        </p>

        <div className={`border rounded-xl p-4 mb-6 ${runtimeInconclusive ? 'border-yellow-800/50 bg-yellow-900/10' : 'border-green-800/40 bg-green-900/10'}`}>
          <p className={`font-mono text-xs ${runtimeInconclusive ? 'text-yellow-300/80' : 'text-green-300/80'}`}>
            {runtimeInconclusive ? 'Runtime crawl inconclusive.' : 'Runtime crawl quality is usable for scoring.'}
          </p>
          <p className="text-xs text-white/45 mt-2 font-mono">
            usable_for_scoring={String(quality.usable_for_scoring)} · usable_for_mismatch={String(quality.usable_for_mismatch)} · requires_human={String(requiresHuman)}
          </p>
          {requiresHuman && (
            <p className="text-xs text-white/40 mt-2 font-mono">human_reasons: {(dynamic.human_reasons || []).join(', ') || 'none'}</p>
          )}
          {qualityReasons.length > 0 && (
            <p className="text-xs text-white/40 mt-2 font-mono">reasons: {qualityReasons.join(', ')}</p>
          )}
        </div>

        {mismatch_detected && (
          <div className="border border-red-800/50 bg-red-900/10 rounded-xl p-4 mb-6">
            <p className="font-mono text-sm text-red-400 font-semibold mb-1">⚠ Consent Mismatch Detected</p>
            <p className="text-xs text-red-400/60">
              The site continued to deploy the same or more trackers during the <b>Reject (S1)</b> state compared to the <b>Baseline (S0)</b>. 
              This indicates non-compliance strictly tracking users before or after consent is explicitly denied.
            </p>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          
          {/* S0 State */}
          <div className="border border-border rounded-lg p-4 bg-surface/30">
            <div className="flex justify-between items-center mb-3">
              <span className="font-mono text-xs text-white/50 uppercase">S0 - Baseline</span>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-white/5 text-white/40">Pre-Consent</span>
            </div>
            <div className="text-3xl font-mono font-bold mb-1">{S0.total_trackers}</div>
            <div className="text-[10px] font-mono text-white/30 uppercase tracking-widest">Trackers Loaded</div>
            
            <div className="mt-4 pt-4 border-t border-white/5 space-y-2">
              <div className="flex justify-between text-xs">
                <span className="text-white/30">Cookies</span>
                <span className="font-mono font-bold text-white/70">{S0.total_cookies}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-white/30">Network Requests</span>
                <span className="font-mono font-bold text-white/70">{S0.total_requests}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-white/30">3rd Parties</span>
                <span className="font-mono font-bold text-white/70">{S0.third_party_domains?.length || 0}</span>
              </div>
            </div>
          </div>

          {/* S1 State */}
          <div className="border border-border rounded-lg p-4 bg-surface/30 relative overflow-hidden">
            <div className="absolute top-0 right-0 w-1 bg-orange-500/50 h-full"></div>
            <div className="flex justify-between items-center mb-3">
              <span className="font-mono text-xs text-white/50 uppercase">S1 - Reject</span>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-orange-500/10 text-orange-400">Consent Denied</span>
            </div>
            <div className={`text-3xl font-mono font-bold mb-1 ${S1.total_trackers >= S0.total_trackers && S0.total_trackers > 0 ? 'text-red-400' : 'text-orange-300'}`}>
              {S1.total_trackers}
            </div>
            <div className="text-[10px] font-mono text-white/30 uppercase tracking-widest">Trackers Loaded</div>
            
            <div className="mt-4 pt-4 border-t border-white/5 space-y-2">
              <div className="flex justify-between text-xs">
                <span className="text-white/30">Cookies</span>
                <span className="font-mono font-bold text-white/70">{S1.total_cookies}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-white/30">Network Requests</span>
                <span className="font-mono font-bold text-white/70">{S1.total_requests}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-white/30">3rd Parties</span>
                <span className="font-mono font-bold text-white/70">{S1.third_party_domains?.length || 0}</span>
              </div>
            </div>
          </div>

          {/* S2 State */}
          <div className="border border-border rounded-lg p-4 bg-surface/30 relative overflow-hidden">
            <div className="absolute top-0 right-0 w-1 bg-green-500/50 h-full"></div>
            <div className="flex justify-between items-center mb-3">
              <span className="font-mono text-xs text-white/50 uppercase">S2 - Accept</span>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-green-500/10 text-green-400">Consent Granted</span>
            </div>
            <div className="text-3xl font-mono font-bold mb-1 text-green-300">{S2.total_trackers}</div>
            <div className="text-[10px] font-mono text-white/30 uppercase tracking-widest">Trackers Loaded</div>
            
            <div className="mt-4 pt-4 border-t border-white/5 space-y-2">
              <div className="flex justify-between text-xs">
                <span className="text-white/30">Cookies</span>
                <span className="font-mono font-bold text-white/70">{S2.total_cookies}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-white/30">Network Requests</span>
                <span className="font-mono font-bold text-white/70">{S2.total_requests}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-white/30">3rd Parties</span>
                <span className="font-mono font-bold text-white/70">{S2.third_party_domains?.length || 0}</span>
              </div>
            </div>
          </div>

        </div>

        {(s1ClickVerification || s2ClickVerification) && (
          <div className="mt-6 border border-border rounded-xl p-4 bg-surface/20">
            <h4 className="font-mono text-xs text-white/40 uppercase tracking-wider mb-3">Click verification</h4>
            <div className="space-y-2">
              {renderClickSummary('S1', s1ClickVerification)}
              {renderClickSummary('S2', s2ClickVerification)}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
