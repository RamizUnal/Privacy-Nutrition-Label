import React from 'react';
import type { AnalysisResult } from '../../types';
import PolicyTextPanel from './PolicyTextPanel';

interface Props {
  result: AnalysisResult;
  onTabChange: (tab: string) => void;
}

const GRADE_COLORS: Record<string, string> = {
  A: '#6B8453', B: '#6F8791', C: '#B98F2A', D: '#A96F3C', F: '#A04535',
};

const SENSITIVITY_LABELS: Record<string, { color: string; short: string }> = {
  critical: { color: '#A04535', short: 'CRITICAL' },
  high: { color: '#A96F3C', short: 'HIGH' },
  medium: { color: '#B98F2A', short: 'MED' },
  low: { color: '#6B8453', short: 'LOW' },
};

export default function NutritionFacts({ result, onTabChange }: Props) {
  const gradeColor = GRADE_COLORS[result.grade] || '#888';

  const dt = result.data_types || [];
  const criticalCount = dt.filter(d => d.sensitivity === 'critical').length;
  const highCount = dt.filter(d => d.sensitivity === 'high').length;
  const specialGdprCount = dt.filter(d => d.gdpr_special_category).length;
  const sharedCount = dt.filter(d => d.shared).length;

  const tp = result.third_parties;
  const trackers = result.trackers;
  const dp = result.dark_patterns;
  const rights = result.rights;
  const retention = result.retention;
  const sentiment = result.sentiment;

  const Row = ({ label, value, sub, highlight, danger, tab }: {
    label: string; value: string | number; sub?: string;
    highlight?: boolean; danger?: boolean; tab?: string;
  }) => (
    <div
      className={`flex items-center justify-between py-2.5 border-b border-white/8 fda-thin-separator ${tab ? 'cursor-pointer hover:bg-black/[0.025]' : ''}`}
      onClick={() => tab && onTabChange(tab)}
    >
      <div>
        <span className="font-mono text-sm text-white/70">{label}</span>
        {sub && <span className="ml-2 font-mono text-xs text-white/30">{sub}</span>}
      </div>
      <span
        className="font-mono text-sm font-bold"
        style={{
          color: danger ? '#A04535' : highlight ? '#6B8453' : 'rgba(14,14,13,0.82)',
        }}
      >
        {value}
      </span>
    </div>
  );

  const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
    <div className="mb-1">
      <div className="py-1 border-t-4 border-white/80 mt-3 mb-0.5">
        <span className="font-mono text-xs text-white/40 uppercase tracking-wider">{title}</span>
      </div>
      {children}
    </div>
  );

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      {/* The FDA-style Nutrition Label */}
      <div className="fda-label overflow-hidden rounded-[22px] shadow-[var(--shadow-sm)]">
        {/* Header */}
        <div className="bg-white px-5 pt-4 pb-3 border-b-[10px] border-black">
          <h2 className="text-black font-display text-4xl font-light leading-none tracking-[-0.012em]">Privacy Facts</h2>
          <div className="flex items-baseline gap-3 mt-1">
            <span className="text-black font-mono text-sm">Overall Grade</span>
            <span
              className="font-display text-4xl font-black leading-none"
              style={{ color: gradeColor }}
            >
              {result.grade}
            </span>
            <span className="font-mono text-xs text-black/50">
              {result.overall_score}/100 Privacy Score
            </span>
          </div>
        </div>

        <div className="px-5 py-1">
          {/* Data collection */}
          <Section title="Data Collection">
            <Row label="Types collected" value={dt.length} tab="data" />
            <Row label="Special categories (GDPR Art.9)" value={specialGdprCount}
              danger={specialGdprCount > 0} tab="data" />
            <Row label="Critical sensitivity" value={criticalCount}
              danger={criticalCount > 0} tab="data" />
            <Row label="Shared with 3rd parties" value={sharedCount}
              danger={sharedCount > 3} tab="data" />
          </Section>

          <Section title="Third-Party Sharing">
            <Row label="Total recipients" value={tp?.count ?? '?'}
              danger={(tp?.count ?? 0) > 10} tab="sharing" />
            <Row label="Advertising partners" value={tp?.advertising_partners ?? 0}
              danger={(tp?.advertising_partners ?? 0) > 3} tab="sharing" />
            <Row label="Data sold" value={tp?.data_sold ? 'YES' : 'No'}
              danger={tp?.data_sold} tab="sharing" />
            <Row label="Cross-border transfers" value={tp?.cross_border_transfers ? 'Yes' : 'No'}
              tab="sharing" />
          </Section>

          <Section title="Trackers & Cookies">
            <Row label="Trackers detected" value={trackers?.total_tracker_count ?? 0}
              danger={(trackers?.total_tracker_count ?? 0) > 10} tab="trackers" />
            <Row label="Fingerprinting" value={trackers?.fingerprinting_detected ? 'DETECTED' : 'None'}
              danger={trackers?.fingerprinting_detected} tab="trackers" />
            <Row label="Session recording" value={trackers?.session_recording_detected ? 'DETECTED' : 'None'}
              danger={trackers?.session_recording_detected} tab="trackers" />
            <Row label="Consent manager" value={trackers?.cmp_detected ?? 'None'}
              highlight={!!trackers?.cmp_detected} tab="cookies" />
          </Section>

          <Section title="Consent & Rights">
            <Row label="Dark patterns" value={dp?.count ?? 0}
              danger={(dp?.count ?? 0) > 0} tab="dark_patterns" />
            <Row label="GDPR rights covered" value={`${rights?.gdpr_score ?? 0}%`}
              highlight={(rights?.gdpr_score ?? 0) >= 70} tab="rights" />
            <Row label="CCPA rights covered" value={`${rights?.ccpa_score ?? 0}%`}
              highlight={(rights?.ccpa_score ?? 0) >= 70} tab="rights" />
            <Row label="DNT honored" value={rights?.dnt_honored ? 'Yes' : 'No'}
              highlight={rights?.dnt_honored} tab="rights" />
          </Section>

          <Section title="Retention & Transparency">
            <Row label="Retention policy" value={retention?.overall_rating?.replace('_', ' ') ?? '?'}
              danger={retention?.overall_rating === 'very_poor'} tab="retention" />
            <Row label="Deletion on request" value={retention?.deletion_on_request ? 'Yes' : 'No'}
              highlight={retention?.deletion_on_request} tab="retention" />
            <Row label="Policy transparency" value={sentiment?.overall_transparency?.replace('_', ' ') ?? '?'}
              highlight={sentiment?.overall_transparency === 'high'} tab="transparency" />
            <Row label="Named 3rd parties" value={sentiment?.named_third_party_count ?? 0}
              highlight={(sentiment?.named_third_party_count ?? 0) > 3} tab="transparency" />
          </Section>

          {/* Footer */}
          <div className="border-t-4 border-white/50 mt-3 pt-2 pb-3">
            <p className="font-mono text-xs text-white/25 leading-relaxed">
              * Analyzed under GDPR (EU) 2016/679, CCPA/CPRA, and privacy best practices.
              Score methodology: Data(20%) + Sharing(20%) + Transparency(15%) + Rights(15%) + Retention(12%) + Dark Patterns(10%) + Technical(8%).
            </p>
          </div>
        </div>
      </div>

      {/* Quick stats grid */}
      <div className="space-y-4">
        {/* Sensitivity breakdown */}
        <div className="glass-panel rounded-[22px] p-5">
          <h3 className="font-mono text-xs text-white/40 uppercase tracking-wider mb-4">Data Sensitivity Distribution</h3>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {(['critical', 'high', 'medium', 'low'] as const).map(level => {
              const count = dt.filter(d => d.sensitivity === level).length;
              const info = SENSITIVITY_LABELS[level];
              return (
                <div
                  key={level}
                  className="rounded-xl border p-3 text-center"
                  style={{ borderColor: `${info.color}40`, background: `${info.color}08` }}
                >
                  <div className="text-2xl font-mono font-bold" style={{ color: info.color }}>{count}</div>
                  <div className="text-xs font-mono mt-1" style={{ color: `${info.color}80` }}>{info.short}</div>
                </div>
              );
            })}
          </div>

          {dt.length > 0 && (
            <div className="mt-3 h-2 rounded-full overflow-hidden flex">
              {(['critical', 'high', 'medium', 'low'] as const).map(level => {
                const count = dt.filter(d => d.sensitivity === level).length;
                const pct = (count / dt.length) * 100;
                const info = SENSITIVITY_LABELS[level];
                return pct > 0 ? (
                  <div key={level} style={{ width: `${pct}%`, background: info.color }} />
                ) : null;
              })}
            </div>
          )}
        </div>

        {/* Tracker categories */}
        {trackers?.by_category && Object.keys(trackers.by_category).length > 0 && (
          <div className="glass-panel rounded-[22px] p-5">
            <h3 className="font-mono text-xs text-white/40 uppercase tracking-wider mb-3">Tracker Categories</h3>
            <div className="space-y-2">
              {Object.entries(trackers.by_category)
                .sort(([, a], [, b]) => b - a)
                .slice(0, 6)
                .map(([cat, count]) => (
                  <div key={cat} className="flex items-center gap-3">
                    <span className="font-mono text-xs text-white/50 w-36 truncate">{cat}</span>
                    <div className="flex-1 h-1.5 rounded-full bg-white/5">
                      <div
                        className="h-full rounded-full bg-orange-500/70"
                        style={{ width: `${Math.min(100, (count / (trackers.total_tracker_count || 1)) * 100)}%` }}
                      />
                    </div>
                    <span className="font-mono text-xs text-white/40 w-4 text-right">{count}</span>
                  </div>
                ))}
            </div>
          </div>
        )}

        {/* Alert banners */}
        {dp?.high_severity_count > 0 && (
          <div className="rounded-[22px] border border-red-500/20 bg-white/60 p-4 flex items-start gap-3">
            <span className="text-red-400 text-lg flex-shrink-0">⚠</span>
            <div>
              <p className="font-mono text-sm text-red-400 font-semibold">Dark Patterns Detected</p>
              <p className="text-xs text-red-400/60 mt-1">
                {dp.high_severity_count} high-severity consent manipulation patterns found.
                These may violate GDPR Art. 7 and EDPB Guidelines 03/2022.
              </p>
            </div>
          </div>
        )}

        {trackers?.fingerprinting_detected && (
          <div className="rounded-[22px] border border-orange-500/20 bg-white/60 p-4 flex items-start gap-3">
            <span className="text-orange-400 text-lg flex-shrink-0">🔮</span>
            <div>
              <p className="font-mono text-sm text-orange-400 font-semibold">Fingerprinting Detected</p>
              <p className="text-xs text-orange-400/60 mt-1">
                Browser fingerprinting bypasses cookie consent and tracks users without their knowledge.
                EDPB classifies this as a high-risk processing activity.
              </p>
            </div>
          </div>
        )}

        {tp?.data_sold && (
          <div className="rounded-[22px] border border-red-500/20 bg-white/60 p-4 flex items-start gap-3">
            <span className="text-red-400 text-lg flex-shrink-0">💰</span>
            <div>
              <p className="font-mono text-sm text-red-400 font-semibold">Data is Sold</p>
              <p className="text-xs text-red-400/60 mt-1">
                This website sells your personal data. Under CCPA §1798.120, you have the right
                to opt-out via a "Do Not Sell My Personal Information" link.
              </p>
            </div>
          </div>
        )}

        {!result.policy_found && (
          <div className="rounded-[22px] border border-red-500/20 bg-white/60 p-4 flex items-start gap-3">
            <span className="text-red-400 text-lg flex-shrink-0">✗</span>
            <div>
              <p className="font-mono text-sm text-red-400 font-semibold">No Privacy Policy Found</p>
              <p className="text-xs text-red-400/60 mt-1">
                A public privacy policy is legally required under GDPR (Art. 13/14), CCPA,
                and virtually all modern privacy regulations.
              </p>
            </div>
          </div>
        )}

        <PolicyTextPanel result={result} />
      </div>
    </div>
  );
}
