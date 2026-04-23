import React, { useEffect, useState } from 'react';
import type { DomainHistory, PolicyChange } from '../../types';
import { getDomainHistory } from '../../api';

interface Props {
  domain: string;
}

function DiffSnippet({ change }: { change: PolicyChange }) {
  const [open, setOpen] = useState(false);
  const similarity = Math.round((change.similarity_ratio ?? 0) * 100);
  const hasChanged = change.added_lines > 0 || change.removed_lines > 0;
  const changeColor = similarity > 90 ? '#ffd740' : similarity > 70 ? '#ff9100' : '#ff1744';

  return (
    <div className="border border-border rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full text-left p-4 flex items-center gap-4 hover:bg-white/2 transition-colors"
      >
        {/* Timeline dot */}
        <div className="flex flex-col items-center gap-1 flex-shrink-0">
          <div
            className="w-3 h-3 rounded-full border-2"
            style={{ borderColor: changeColor, background: `${changeColor}30` }}
          />
        </div>

        <div className="flex-1 min-w-0">
          <div className="text-xs font-mono text-white/60">
            {new Date(change.detected_at).toLocaleDateString('en-GB', {
              day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit'
            })}
          </div>
          <div className="text-xs font-mono text-white/40 mt-0.5">{change.summary}</div>
        </div>

        <div className="flex items-center gap-3 flex-shrink-0">
          {change.added_lines > 0 && (
            <span className="text-xs font-mono text-accent-green">+{change.added_lines}</span>
          )}
          {change.removed_lines > 0 && (
            <span className="text-xs font-mono text-red-400">-{change.removed_lines}</span>
          )}
          <span
            className="text-[10px] font-mono px-2 py-0.5 rounded-full"
            style={{ color: changeColor, background: `${changeColor}20`, border: `1px solid ${changeColor}40` }}
          >
            {similarity}% similar
          </span>
          {(change.diff_snippets?.length ?? 0) > 0 && (
            <span className="text-white/30 text-xs">{open ? '▲' : '▼'}</span>
          )}
        </div>
      </button>

      {/* Diff snippets */}
      {open && (change.diff_snippets?.length ?? 0) > 0 && (
        <div className="border-t border-border p-4 space-y-3 bg-bg/40">
          <div className="text-[10px] font-mono text-white/30 uppercase tracking-wider mb-2">Changed Sections</div>
          {change.diff_snippets.slice(0, 5).map((snip, i) => (
            <div
              key={i}
              className="rounded-lg p-3 font-mono text-xs leading-relaxed"
              style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}
            >
              {snip.type === 'changed' && (
                <>
                  <div className="text-red-400/80 mb-1">- {snip.old}</div>
                  <div className="text-accent-green/80">+ {snip.new}</div>
                </>
              )}
              {snip.type === 'added' && (
                <div className="text-accent-green/80">+ {snip.text}</div>
              )}
              {snip.type === 'removed' && (
                <div className="text-red-400/80">- {snip.text}</div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function PolicyHistory({ domain }: Props) {
  const [history, setHistory] = useState<DomainHistory | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getDomainHistory(domain)
      .then(setHistory)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [domain]);

  if (loading) {
    return (
      <div className="flex flex-col items-center py-16 gap-3">
        <div className="w-6 h-6 border-2 border-accent-green border-t-transparent rounded-full animate-spin" />
        <span className="font-mono text-xs text-white/40">Loading policy history…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-6 text-center">
        <p className="font-mono text-xs text-red-400">Failed to load history: {error}</p>
      </div>
    );
  }

  const analyses = history?.analyses ?? [];
  const changes  = history?.policy_changes ?? [];

  return (
    <div className="space-y-6">

      {/* Score timeline */}
      <div className="bg-panel border border-border rounded-xl p-5">
        <div className="text-[10px] font-mono text-white/30 uppercase tracking-wider mb-4">Analysis History</div>

        {analyses.length === 0 ? (
          <p className="text-xs font-mono text-white/30">No previous analyses recorded.</p>
        ) : (
          <div className="space-y-3">
            {analyses.map((a, i) => {
              const isLatest = i === 0;
              const gradeColors: Record<string, string> = {
                A: '#00e676', B: '#40c4ff', C: '#ffd740', D: '#ff9100', F: '#ff1744',
              };
              const color = gradeColors[a.grade] ?? '#888';
              return (
                <div key={a.id} className="flex items-center gap-4">
                  {/* Timeline */}
                  <div className="flex flex-col items-center gap-1 flex-shrink-0 w-3">
                    <div
                      className="w-3 h-3 rounded-full border-2"
                      style={{ borderColor: color, background: isLatest ? color : `${color}30` }}
                    />
                    {i < analyses.length - 1 && (
                      <div className="w-px h-6 bg-border" />
                    )}
                  </div>

                  <div className="flex-1 min-w-0 py-1">
                    <div className="flex items-center gap-3 flex-wrap">
                      <span className="font-mono text-xs text-white/50">
                        {new Date(a.analyzed_at).toLocaleDateString('en-GB', {
                          day: 'numeric', month: 'short', year: 'numeric'
                        })}
                      </span>
                      <span
                        className="font-mono text-sm font-bold"
                        style={{ color }}
                      >
                        {a.grade} · {a.overall_score}/100
                      </span>
                      <span className="text-[10px] font-mono text-white/30 uppercase">{a.risk_level} risk</span>
                      {isLatest && (
                        <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-accent-green/10 text-accent-green border border-accent-green/30">
                          LATEST
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Policy version changes */}
      <div className="bg-panel border border-border rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="text-[10px] font-mono text-white/30 uppercase tracking-wider">Policy Version History</div>
            <p className="text-xs font-mono text-white/20 mt-0.5">
              Automatically detects when the privacy policy changes
            </p>
          </div>
          <span className="text-xs font-mono text-white/30">
            {changes.length} version{changes.length !== 1 ? 's' : ''} tracked
          </span>
        </div>

        {changes.length === 0 ? (
          <div className="flex flex-col items-center py-8 gap-2 text-white/30">
            <div className="text-2xl">📋</div>
            <p className="font-mono text-xs">No policy changes recorded yet.</p>
            <p className="font-mono text-[10px]">Re-analyze the site regularly to detect changes.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {changes.map(c => (
              <DiffSnippet key={c.id} change={c} />
            ))}
          </div>
        )}
      </div>

      {/* Versioning note */}
      <div
        className="rounded-xl p-4 flex items-start gap-3"
        style={{ background: 'rgba(64,196,255,0.05)', border: '1px solid rgba(64,196,255,0.15)' }}
      >
        <span className="text-blue-400 text-sm flex-shrink-0">ℹ</span>
        <p className="text-xs font-sans text-white/40 leading-relaxed">
          Each time you analyze this domain, its privacy policy is hashed and stored. If it differs from the
          previous version, a policy change record is created automatically with a line-level diff.
          This enables long-term policy versioning as promised under <span className="text-violet-300 font-mono">GDPR transparency obligations</span>.
        </p>
      </div>
    </div>
  );
}
