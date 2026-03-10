import React, { useEffect, useRef } from 'react';
import type { AnalysisResult } from '../../types';
import { RadialBarChart, RadialBar, ResponsiveContainer } from 'recharts';

interface Props {
  result: AnalysisResult;
  onReanalyze?: () => void;
}

const GRADE_COLORS: Record<string, string> = {
  A: '#00e676', B: '#40c4ff', C: '#ffd740', D: '#ff9100', F: '#ff1744',
};
const RISK_COLORS: Record<string, string> = {
  low: '#00e676', medium: '#ffd740', high: '#ff9100', critical: '#ff1744',
};

function CountUp({ target, duration = 1200 }: { target: number; duration?: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    let start = 0;
    const increment = target / (duration / 16);
    const timer = setInterval(() => {
      start = Math.min(start + increment, target);
      if (ref.current) ref.current.textContent = Math.floor(start).toString();
      if (start >= target) clearInterval(timer);
    }, 16);
    return () => clearInterval(timer);
  }, [target, duration]);
  return <span ref={ref}>0</span>;
}

export default function ScoreHeader({ result, onReanalyze }: Props) {
  const gradeColor = GRADE_COLORS[result.grade] || '#888';
  const riskColor = RISK_COLORS[result.risk_level] || '#888';

  const chartData = [
    { name: 'score', value: result.overall_score, fill: gradeColor },
  ];

  const breakdown = result.score_breakdown;
  const dims = [
    { key: 'data_collection', label: 'Data Collection', score: breakdown?.data_collection },
    { key: 'sharing', label: 'Sharing', score: breakdown?.sharing },
    { key: 'transparency', label: 'Transparency', score: breakdown?.transparency },
    { key: 'rights', label: 'Rights', score: breakdown?.rights },
    { key: 'retention', label: 'Retention', score: breakdown?.retention },
    { key: 'dark_patterns', label: 'Dark Patterns', score: breakdown?.dark_patterns },
    { key: 'technical', label: 'Technical', score: breakdown?.technical },
  ];

  const getBarColor = (score: number) => {
    if (score >= 75) return '#00e676';
    if (score >= 50) return '#ffd740';
    if (score >= 30) return '#ff9100';
    return '#ff1744';
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 pt-4">
      {/* Main score card */}
      <div className="lg:col-span-1 bg-panel border border-border rounded-xl overflow-hidden">
        <div className="p-6 flex flex-col items-center">
          {/* Domain */}
          <div className="flex items-center gap-2 mb-4">
            <div className="w-4 h-4 rounded-full bg-panel border border-border flex-shrink-0 overflow-hidden">
              <img
                src={`https://www.google.com/s2/favicons?domain=${result.domain}&sz=16`}
                alt=""
                className="w-full h-full"
                onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }}
              />
            </div>
            <span className="font-mono text-sm text-white/60 truncate max-w-[180px]">{result.domain}</span>
          </div>

          {/* Radial score */}
          <div className="relative w-44 h-44">
            <ResponsiveContainer width="100%" height="100%">
              <RadialBarChart
                cx="50%" cy="50%"
                innerRadius="70%" outerRadius="100%"
                startAngle={180} endAngle={-180}
                data={chartData}
              >
                <RadialBar
                  dataKey="value"
                  cornerRadius={8}
                  background={{ fill: 'rgba(255,255,255,0.04)' }}
                />
              </RadialBarChart>
            </ResponsiveContainer>
            {/* Center text */}
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <div className="text-5xl font-mono font-bold number-pop" style={{ color: gradeColor }}>
                <CountUp target={result.overall_score} />
              </div>
              <div className="text-xs font-mono text-white/40 mt-0.5">/100</div>
            </div>
          </div>

          {/* Grade badge */}
          <div
            className="mt-3 text-6xl font-display font-bold number-pop"
            style={{ color: gradeColor, textShadow: `0 0 30px ${gradeColor}40` }}
          >
            {result.grade}
          </div>

          {/* Risk level */}
          <div
            className="mt-2 px-3 py-1 rounded-full text-xs font-mono font-semibold uppercase tracking-wider"
            style={{
              color: riskColor,
              background: `${riskColor}15`,
              border: `1px solid ${riskColor}40`,
            }}
          >
            {result.risk_level} risk
          </div>

          {/* Summary */}
          <p className="mt-4 text-xs font-sans text-white/40 text-center leading-relaxed">
            {result.summary}
          </p>

          {/* Meta */}
          <div className="mt-4 w-full pt-4 border-t border-border flex flex-col gap-1.5">
            <div className="flex justify-between text-xs font-mono">
              <span className="text-white/30">Policy found</span>
              <span className={result.policy_found ? 'text-accent-green' : 'text-red-400'}>
                {result.policy_found ? '✓ Yes' : '✗ No'}
              </span>
            </div>
            {result.policy_word_count > 0 && (
              <div className="flex justify-between text-xs font-mono">
                <span className="text-white/30">Policy length</span>
                <span className="text-white/60">{result.policy_word_count.toLocaleString()} words</span>
              </div>
            )}
            {result.policy_discovery_method && (
              <div className="flex justify-between text-xs font-mono">
                <span className="text-white/30">Found via</span>
                <span className={
                  result.policy_discovery_method === 'ai_discovery'
                    ? 'text-violet-400'
                    : result.policy_discovery_method === 'sitemap'
                      ? 'text-blue-400'
                      : 'text-white/50'
                }>
                  {result.policy_discovery_method === 'canonical_path' && '📍 canonical path'}
                  {result.policy_discovery_method === 'link_scan'      && '🔗 link scan'}
                  {result.policy_discovery_method === 'sitemap'        && '🗺 sitemap'}
                  {result.policy_discovery_method === 'ai_discovery'   && '✦ AI discovery'}
                </span>
              </div>
            )}
            {result.cached && (
              <div className="flex justify-between text-xs font-mono">
                <span className="text-white/30">Source</span>
                <span className="text-white/40">cached result</span>
              </div>
            )}
          </div>

          {onReanalyze && (
            <button
              onClick={onReanalyze}
              className="mt-4 w-full py-2 rounded border border-border text-white/40 hover:border-white/30 hover:text-white/60 text-xs font-mono transition-colors"
            >
              ↺ Force Re-analyze
            </button>
          )}
        </div>
      </div>

      {/* Dimension breakdown */}
      <div className="lg:col-span-2 bg-panel border border-border rounded-xl p-6">
        <h3 className="font-mono text-xs text-white/40 uppercase tracking-wider mb-5">Score Breakdown</h3>

        <div className="space-y-3">
          {dims.map(dim => {
            const score = dim.score ?? 0;
            const color = getBarColor(score);
            const weight = breakdown?.weights?.[dim.key] ?? 0;
            return (
              <div key={dim.key}>
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-white/60">{dim.label}</span>
                    <span className="font-mono text-xs text-white/20">({(weight * 100).toFixed(0)}%)</span>
                  </div>
                  <span className="font-mono text-xs font-semibold" style={{ color }}>
                    {score}/100
                  </span>
                </div>
                <div className="score-bar">
                  <div
                    className="score-bar-fill"
                    style={{ width: `${score}%`, background: color }}
                  />
                </div>
              </div>
            );
          })}
        </div>

        {/* Penalties/bonuses */}
        <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Top penalties */}
          <div>
            <h4 className="font-mono text-xs text-red-400/70 uppercase tracking-wider mb-2">
              Top Findings
            </h4>
            <div className="space-y-1.5">
              {(result.penalties || []).slice(0, 4).map((p, i) => (
                <div key={i} className="flex items-start gap-2">
                  <span className="text-red-400 text-xs mt-0.5 flex-shrink-0">▼</span>
                  <span className="text-xs font-sans text-white/40 leading-snug">{p.reason}</span>
                </div>
              ))}
            </div>
          </div>
          {/* Bonuses */}
          <div>
            <h4 className="font-mono text-xs text-green-400/70 uppercase tracking-wider mb-2">
              Positive Signals
            </h4>
            <div className="space-y-1.5">
              {(result.bonuses || []).slice(0, 4).map((b, i) => (
                <div key={i} className="flex items-start gap-2">
                  <span className="text-accent-green text-xs mt-0.5 flex-shrink-0">▲</span>
                  <span className="text-xs font-sans text-white/40 leading-snug">{b.reason}</span>
                </div>
              ))}
              {!(result.bonuses || []).length && (
                <span className="text-xs font-mono text-white/20">No notable positives found.</span>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
