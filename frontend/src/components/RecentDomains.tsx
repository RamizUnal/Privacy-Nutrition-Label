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
    <div className="max-w-2xl w-full">
      <p className="text-white/25 text-xs font-mono mb-3 text-center">Recently Analyzed</p>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {domains.map(d => (
          <button
            key={d.domain}
            onClick={() => onSelect(d.domain)}
            className="p-3 rounded border border-border bg-panel hover:border-accent-green/40 hover:bg-panel/80 transition-all text-left group"
          >
            <div className="flex items-center justify-between mb-1">
              <span className="font-mono text-xs text-white/60 truncate group-hover:text-white/90 transition-colors">
                {d.domain}
              </span>
              <span className={`font-mono text-xs font-bold ${GRADE_COLORS[d.grade] || 'text-white/40'}`}>
                {d.grade}
              </span>
            </div>
            <div className="h-1 rounded-full bg-white/5 overflow-hidden">
              <div
                className="h-full rounded-full"
                style={{
                  width: `${d.score}%`,
                  background: d.score >= 70 ? '#00e676' : d.score >= 50 ? '#ffd740' : '#ff3b3b',
                }}
              />
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
