import React, { useEffect, useMemo, useState } from 'react';
import { getPolicyText } from '../../api';
import type { AnalysisResult, PolicyTextResponse } from '../../types';

interface Props {
  result: AnalysisResult;
}

type PolicyBlock =
  | { kind: 'main'; text: string; url?: string }
  | { kind: 'sub'; text: string; url?: string }
  | { kind: 'heading'; level: number; text: string }
  | { kind: 'bullet'; text: string }
  | { kind: 'numbered'; text: string }
  | { kind: 'paragraph'; text: string };

function cleanInline(text: string): string {
  return text
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '$1')
    .replace(/\s+/g, ' ')
    .trim();
}

function parsePolicyText(text: string): PolicyBlock[] {
  const blocks: PolicyBlock[] = [];

  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line) continue;

    const main = line.match(/^===\s*MAIN PRIVACY POLICY\s*(?:\((.+)\))?\s*===$/i);
    if (main) {
      blocks.push({ kind: 'main', text: 'Main Privacy Policy', url: main[1] });
      continue;
    }

    const sub = line.match(/^===\s*SUB-POLICY:\s*(.+?)(?:\s*\((https?:\/\/.+)\))?\s*===$/i);
    if (sub) {
      blocks.push({ kind: 'sub', text: cleanInline(sub[1]), url: sub[2] });
      continue;
    }

    const heading = line.match(/^(#{1,4})\s+(.+)$/);
    if (heading) {
      blocks.push({
        kind: 'heading',
        level: heading[1].length,
        text: cleanInline(heading[2]),
      });
      continue;
    }

    const bullet = line.match(/^[-*\u2022]\s+(.+)$/);
    if (bullet) {
      blocks.push({ kind: 'bullet', text: cleanInline(bullet[1]) });
      continue;
    }

    const numbered = line.match(/^\d+[.)]\s+(.+)$/);
    if (numbered) {
      blocks.push({ kind: 'numbered', text: cleanInline(numbered[1]) });
      continue;
    }

    blocks.push({ kind: 'paragraph', text: cleanInline(line) });
  }

  return blocks;
}

function PolicyBlockView({ block }: { block: PolicyBlock }) {
  if (block.kind === 'main' || block.kind === 'sub') {
    return (
      <div className="border-t border-white/10 pt-4 first:border-t-0 first:pt-0">
        <div className="font-display text-lg font-bold text-white">
          {block.text}
        </div>
        {block.url && (
          <div className="mt-1 truncate font-mono text-[11px] text-accent-green/60">
            {block.url}
          </div>
        )}
      </div>
    );
  }

  if (block.kind === 'heading') {
    const size = block.level <= 1
      ? 'text-base text-white'
      : block.level === 2
        ? 'text-sm text-white/90'
        : 'text-xs text-white/75';
    return (
      <h4 className={`mt-4 font-display font-bold leading-snug ${size}`}>
        {block.text}
      </h4>
    );
  }

  if (block.kind === 'bullet') {
    return (
      <div className="flex gap-2 text-sm leading-6 text-white/68">
        <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-accent-green/70" />
        <span>{block.text}</span>
      </div>
    );
  }

  if (block.kind === 'numbered') {
    return (
      <div className="border-l border-white/10 pl-3 text-sm leading-6 text-white/68">
        {block.text}
      </div>
    );
  }

  return (
    <p className="text-sm leading-6 text-white/62">
      {block.text}
    </p>
  );
}

export default function PolicyTextPanel({ result }: Props) {
  const [policy, setPolicy] = useState<PolicyTextResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;

    if (!result.policy_found || !result.domain) {
      setPolicy(null);
      return;
    }

    setLoading(true);
    setError('');

    getPolicyText(result.domain)
      .then(data => {
        if (!cancelled) setPolicy(data);
      })
      .catch(() => {
        if (!cancelled) setError('Policy text unavailable');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [result.domain, result.policy_found]);

  const blocks = useMemo(() => parsePolicyText(policy?.text || ''), [policy?.text]);
  const wordCount = policy?.word_count || result.policy_word_count || 0;

  return (
    <section className="bg-panel border border-border rounded-xl overflow-hidden min-h-[430px]">
      <div className="flex items-center justify-between gap-4 border-b border-border px-5 py-4">
        <div>
          <h3 className="font-mono text-xs text-white/45 uppercase tracking-wider">
            Found Policy Text
          </h3>
          <p className="mt-1 font-mono text-[11px] text-white/35">
            {wordCount ? `${wordCount.toLocaleString()} words` : 'Raw policy'}
          </p>
        </div>
        {result.policy_url && (
          <a
            href={result.policy_url}
            target="_blank"
            rel="noreferrer"
            className="max-w-[45%] truncate font-mono text-[11px] text-accent-green/70 hover:text-accent-green"
          >
            {result.policy_url}
          </a>
        )}
      </div>

      <div className="max-h-[560px] overflow-y-auto px-5 py-4">
        {loading && (
          <div className="font-mono text-sm text-white/40">Loading policy text...</div>
        )}

        {!loading && error && (
          <div className="font-mono text-sm text-red-300/70">{error}</div>
        )}

        {!loading && !error && blocks.length === 0 && (
          <div className="font-mono text-sm text-white/40">No readable policy text stored.</div>
        )}

        {!loading && !error && blocks.length > 0 && (
          <div className="space-y-3">
            {blocks.map((block, index) => (
              <PolicyBlockView key={`${block.kind}-${index}`} block={block} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
