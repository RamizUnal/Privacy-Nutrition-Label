import React, { useEffect, useMemo, useRef, useState } from 'react';
import type { AnalysisResult, ChatMessage } from '../../types';
import { streamChatResponse } from '../../api';

interface Props {
  domain: string;
  result: AnalysisResult;
}

type LocalMessage = ChatMessage & { streaming?: boolean; error?: boolean };

function gradeColor(score: number) {
  if (score >= 85) return '#00e676';
  if (score >= 70) return '#40c4ff';
  if (score >= 55) return '#ffd740';
  if (score >= 40) return '#ff9100';
  return '#ff1744';
}

function buildSuggestions(result: AnalysisResult): string[] {
  const suggestions = [
    'What are the biggest privacy risks for me?',
    'Which data types does this policy say are collected?',
    'Which third parties receive my data?',
    'What can I do right now to reduce tracking?',
  ];
  if (result.third_parties?.data_sold) suggestions.unshift('How do I opt out of data sale or sharing?');
  if (result.trackers?.fingerprinting_detected) suggestions.unshift('Explain the fingerprinting risk in plain English.');
  if ((result.rights?.gdpr_score ?? 0) < 70) suggestions.push('Which GDPR rights are missing or weak?');
  if ((result.retention?.has_vague_retention ?? false) || result.retention?.overall_rating === 'very_poor') {
    suggestions.push('What is wrong with the retention policy?');
  }
  if ((result.dark_patterns?.count ?? 0) > 0) suggestions.push('Are there dark patterns in this policy?');
  return Array.from(new Set(suggestions)).slice(0, 8);
}

function InlineText({ text }: { text: string }) {
  const parts: React.ReactNode[] = [];
  const pattern = /(\*\*[^*]+\*\*|https?:\/\/\S+)/g;
  let last = 0;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(text))) {
    if (match.index > last) parts.push(text.slice(last, match.index));
    const value = match[0];
    if (value.startsWith('**')) {
      parts.push(<strong key={`${match.index}-b`} className="font-semibold text-white/90">{value.slice(2, -2)}</strong>);
    } else {
      parts.push(
        <a key={`${match.index}-a`} href={value} target="_blank" rel="noopener noreferrer" className="text-green-300 underline underline-offset-2">
          {value.replace(/^https?:\/\//, '')}
        </a>
      );
    }
    last = match.index + value.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return <>{parts}</>;
}

function MessageContent({ content }: { content: string }) {
  const blocks = content.split(/\n{2,}/).map(block => block.trim()).filter(Boolean);
  if (!blocks.length) return null;
  return (
    <div className="space-y-2">
      {blocks.map((block, i) => {
        const lines = block.split('\n').map(line => line.trim()).filter(Boolean);
        const isList = lines.length > 1 && lines.every(line => /^[-*•]\s+/.test(line) || /^\d+[.)]\s+/.test(line));
        if (isList) {
          return (
            <ul key={i} className="space-y-1 pl-1">
              {lines.map((line, j) => (
                <li key={j} className="flex gap-2">
                  <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-green-300/70" />
                  <span><InlineText text={line.replace(/^[-*•]\s+|^\d+[.)]\s+/, '')} /></span>
                </li>
              ))}
            </ul>
          );
        }
        return <p key={i}><InlineText text={block} /></p>;
      })}
    </div>
  );
}

function MessageBubble({ msg }: { msg: LocalMessage }) {
  const isUser = msg.role === 'user';
  return (
    <div className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}>
      {!isUser && (
        <div className={`mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border font-mono text-xs ${
          msg.error ? 'border-red-500/30 bg-red-500/10 text-red-300' : 'border-green-500/25 bg-green-500/10 text-green-300'
        }`}>
          AI
        </div>
      )}
      <div className={`max-w-[88%] rounded-lg border px-4 py-3 text-sm leading-relaxed ${
        isUser
          ? 'border-green-500/25 bg-green-500/10 text-white/90'
          : msg.error
            ? 'border-red-500/25 bg-red-500/10 text-red-100/75'
            : 'border-border bg-panel text-white/70'
      }`}>
        <MessageContent content={msg.content} />
        {msg.streaming && (
          <span className="mt-2 inline-flex gap-1">
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-white/35" />
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-white/35" style={{ animationDelay: '120ms' }} />
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-white/35" style={{ animationDelay: '240ms' }} />
          </span>
        )}
      </div>
      {isUser && (
        <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-white/10 bg-white/5 font-mono text-xs text-white/50">
          You
        </div>
      )}
    </div>
  );
}

function ContextMetric({ label, value, tone }: { label: string; value: React.ReactNode; tone?: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface/35 p-3">
      <div className={`font-mono text-lg font-bold ${tone || 'text-white/102'}`}>{value}</div>
      <div className="mt-1 font-mono text-[10px] uppercase tracking-wider text-white/30">{label}</div>
    </div>
  );
}

export default function PrivacyAssistant({ domain, result }: Props) {
  const welcome = `I have the stored analysis for **${domain}**: policy text, extracted data categories, third parties, trackers, rights coverage, retention, transparency, and scoring. Ask me for a plain-English answer or a specific policy quote.`;
  const [messages, setMessages] = useState<LocalMessage[]>([
    { role: 'assistant', content: welcome },
  ]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [lastError, setLastError] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const suggestions = useMemo(() => buildSuggestions(result), [result]);
  const trackerCount = result.trackers?.total_tracker_count ?? result.trackers?.trackers?.length ?? 0;
  const rightsScore = Math.round(((result.rights?.gdpr_score || 0) + (result.rights?.ccpa_score || 0)) / 2);
  const topParties = (result.third_parties?.parties || []).slice(0, 5).map(p => p.name);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function sendMessage(text: string) {
    const clean = text.trim();
    if (!clean || isStreaming) return;
    const userMsg: ChatMessage = { role: 'user', content: clean };
    const history = messages
      .filter(m => !m.streaming && !m.error)
      .map(m => ({ role: m.role, content: m.content }));
    history.push(userMsg);

    setMessages(prev => [...prev, userMsg, { role: 'assistant', content: '', streaming: true }]);
    setInput('');
    setIsStreaming(true);
    setLastError('');

    try {
      let accumulated = '';
      await streamChatResponse(domain, history, chunk => {
        accumulated += chunk;
        setMessages(prev => {
          const next = [...prev];
          const last = next[next.length - 1];
          if (last?.streaming) {
            next[next.length - 1] = { ...last, content: accumulated };
          }
          return next;
        });
      });

      setMessages(prev => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last?.streaming) {
          next[next.length - 1] = {
            role: 'assistant',
            content: accumulated || 'I did not receive a response. Try again.',
          };
        }
        return next;
      });
    } catch (err: any) {
      const message = err?.message || 'Assistant request failed';
      setLastError(message);
      setMessages(prev => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last?.streaming) {
          next[next.length - 1] = {
            role: 'assistant',
            content: `I could not answer that request: ${message}`,
            error: true,
          };
        }
        return next;
      });
    } finally {
      setIsStreaming(false);
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }

  function handleKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  }

  function clearChat() {
    setMessages([{ role: 'assistant', content: welcome }]);
    setLastError('');
  }

  return (
    <div className="grid min-h-[680px] grid-cols-1 gap-5 xl:grid-cols-[300px_minmax(0,1fr)]">
      <aside className="space-y-4">
        <section className="rounded-lg border border-border bg-panel p-4">
          <div className="font-mono text-xs uppercase tracking-wider text-white/35">Current Context</div>
          <div className="mt-3 flex items-end gap-3">
            <div className="font-display text-5xl font-bold" style={{ color: gradeColor(result.overall_score) }}>{result.grade}</div>
            <div className="pb-1">
              <div className="font-mono text-sm text-white/100">{result.overall_score}/100</div>
              <div className="font-mono text-xs text-white/35">{result.risk_level} risk</div>
            </div>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-2">
            <ContextMetric label="data" value={result.data_types?.length ?? 0} />
            <ContextMetric label="parties" value={result.third_parties?.count ?? 0} tone={(result.third_parties?.count ?? 0) > 10 ? 'text-orange-300' : undefined} />
            <ContextMetric label="trackers" value={trackerCount} tone={trackerCount > 5 ? 'text-red-300' : undefined} />
            <ContextMetric label="rights" value={`${rightsScore}%`} tone={rightsScore >= 70 ? 'text-green-300' : 'text-orange-300'} />
          </div>
        </section>

        <section className="rounded-lg border border-border bg-panel p-4">
          <div className="font-mono text-xs uppercase tracking-wider text-white/35">Signals</div>
          <div className="mt-3 space-y-2">
            {[
              ['Data sold', result.third_parties?.data_sold],
              ['Fingerprinting', result.trackers?.fingerprinting_detected],
              ['Dark patterns', (result.dark_patterns?.count ?? 0) > 0],
              ['AI extraction', result.ai_extraction?.complete],
            ].map(([label, value]) => (
              <div key={label as string} className="flex items-center justify-between gap-3 rounded border border-white/10 bg-white/5 px-3 py-2">
                <span className="font-mono text-xs text-white/50">{label}</span>
                <span className={`font-mono text-xs ${value ? 'text-red-300' : 'text-green-300'}`}>
                  {value ? 'yes' : 'no'}
                </span>
              </div>
            ))}
          </div>
        </section>

        {topParties.length > 0 && (
          <section className="rounded-lg border border-border bg-panel p-4">
            <div className="font-mono text-xs uppercase tracking-wider text-white/35">Named Parties</div>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {topParties.map(name => (
                <span key={name} className="rounded border border-white/10 bg-white/5 px-2 py-1 font-mono text-[11px] text-white/50">{name}</span>
              ))}
            </div>
          </section>
        )}
      </aside>

      <section className="flex min-h-[680px] flex-col overflow-hidden rounded-lg border border-border bg-surface/25">
        <div className="flex shrink-0 items-center justify-between gap-3 border-b border-border bg-panel px-4 py-3">
          <div>
            <h2 className="font-mono text-sm font-semibold text-white/100">Privacy Assistant</h2>
            <p className="mt-0.5 font-mono text-xs text-white/30">{domain} · privacy AI assistant</p>
          </div>
          <div className="flex items-center gap-2">
            {lastError && <span className="hidden font-mono text-[11px] text-red-300/100 md:inline">{lastError}</span>}
            <button
              onClick={clearChat}
              disabled={isStreaming}
              className="rounded border border-border px-3 py-1.5 font-mono text-xs text-white/50 transition-colors hover:text-white/75 disabled:opacity-40"
            >
              Clear
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-4">
          <div className="space-y-4">
            {messages.map((msg, i) => <MessageBubble key={i} msg={msg} />)}
            <div ref={bottomRef} />
          </div>
        </div>

        {messages.length === 1 && (
          <div className="shrink-0 border-t border-border px-4 py-3">
            <div className="mb-2 font-mono text-[11px] uppercase tracking-wider text-white/30">Suggested questions</div>
            <div className="flex flex-wrap gap-2">
              {suggestions.map(question => (
                <button
                  key={question}
                  onClick={() => sendMessage(question)}
                  disabled={isStreaming}
                  className="rounded-lg border border-border bg-panel px-3 py-1.5 text-left text-xs text-white/50 transition-colors hover:border-green-400/25 hover:text-white/75 disabled:opacity-40"
                >
                  {question}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="shrink-0 border-t border-border bg-panel px-4 py-3">
          <div className="flex items-end gap-2 rounded-lg border border-border bg-surface/50 p-1 transition-colors focus-within:border-green-400/35">
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder={`Ask about ${domain}'s policy, trackers, rights, or risks...`}
              rows={1}
              disabled={isStreaming}
              className="max-h-[140px] min-h-[38px] flex-1 resize-none bg-transparent px-3 py-2 text-sm text-white/100 outline-none placeholder:text-white/25 disabled:opacity-50"
              style={{ fieldSizing: 'content' } as React.CSSProperties}
            />
            <button
              onClick={() => sendMessage(input)}
              disabled={!input.trim() || isStreaming}
              className="mb-1 mr-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-green-400/30 bg-green-500/20 font-mono text-sm text-green-300 transition-colors hover:bg-green-500/25 disabled:cursor-not-allowed disabled:opacity-35"
            >
              {isStreaming ? <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-green-300/30 border-t-green-300" /> : '↑'}
            </button>
          </div>
          <p className="mt-2 text-center font-mono text-[10px] text-white/20">Enter sends · Shift+Enter adds a line</p>
        </div>
      </section>
    </div>
  );
}
