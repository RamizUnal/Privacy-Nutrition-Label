import React, { useEffect, useState } from 'react';
import { getRecentDomains } from '../api';

interface Props {
  onSelect: (url: string) => void;
}

const GRADE_COLORS: Record<string, string> = {
  A: 'text-green-400', B: 'text-blue-400', C: 'text-yellow-400',
  D: 'text-orange-400', F: 'text-red-400',
};

export default function RecentDomains({ onSelect }: Props) {
  const [domains, setDomains] = useState<Array<{ domain: string; score: number; grade: string; analyzed_at: string }>>([]);

  useEffect(() => {
    getRecentDomains()
      .then(d => setDomains(d.domains.slice(0, 8)))
      .catch(() => {});
  }, []);

  if (!domains.length) return null;

  return (
    <div className="mt-10 w-full max-w-4xl">
      <p className="mb-3 text-center font-mono text-[10px] uppercase tracking-[0.14em] text-white/35">Recently analyzed</p>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {domains.map(d => (
          <button
            key={d.domain}
            onClick={() => onSelect(d.domain)}
            className="glass-panel group rounded-2xl p-3 text-left transition-all hover:-translate-y-0.5 hover:border-accent-green/40"
          >
            <div className="flex items-center justify-between mb-1">
              <span className="font-mono text-xs text-white/60 truncate group-hover:text-white/90 transition-colors">
                {d.domain}
              </span>
              <span className={`font-mono text-xs font-bold ${GRADE_COLORS[d.grade] || 'text-white/40'}`}>
                {d.grade}
              </span>
            </div>
            <div className="h-1 overflow-hidden rounded-full bg-white/30">
              <div
                className="h-full rounded-full"
                style={{
                  width: `${d.score}%`,
                  background: d.score >= 70 ? '#6B8453' : d.score >= 50 ? '#B98F2A' : '#A04535',
                }}
              />
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
