import React, { useState, useRef, useEffect } from 'react';
import type { ChatMessage } from '../../types';
import { streamChatResponse } from '../../api';

interface Props {
  domain: string;
}

const SUGGESTED_QUESTIONS = [
  'What data does this site collect about me?',
  'Is my data sold to third parties?',
  'Do I have the right to delete my data?',
  'What trackers are active on this site?',
  'How does this site score compared to GDPR requirements?',
  'What are the biggest privacy risks here?',
];

function MessageBubble({ msg }: { msg: ChatMessage & { streaming?: boolean } }) {
  const isUser = msg.role === 'user';
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} gap-3`}>
      {!isUser && (
        <div className="w-7 h-7 rounded-full bg-accent-green/20 border border-accent-green/30 flex items-center justify-center text-xs shrink-0 mt-0.5">
          🔒
        </div>
      )}
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
          isUser
            ? 'bg-accent-green/15 border border-accent-green/25 text-white/90 rounded-tr-sm'
            : 'bg-surface/60 border border-border text-white/75 rounded-tl-sm'
        }`}
      >
        {msg.content}
        {(msg as any).streaming && (
          <span className="inline-flex ml-1 gap-0.5">
            <span className="w-1 h-1 rounded-full bg-white/40 animate-bounce" style={{ animationDelay: '0ms' }} />
            <span className="w-1 h-1 rounded-full bg-white/40 animate-bounce" style={{ animationDelay: '150ms' }} />
            <span className="w-1 h-1 rounded-full bg-white/40 animate-bounce" style={{ animationDelay: '300ms' }} />
          </span>
        )}
      </div>
      {isUser && (
        <div className="w-7 h-7 rounded-full bg-white/10 border border-border flex items-center justify-center text-xs shrink-0 mt-0.5">
          👤
        </div>
      )}
    </div>
  );
}

export default function PrivacyAssistant({ domain }: Props) {
  const [messages, setMessages] = useState<(ChatMessage & { streaming?: boolean })[]>([
    {
      role: 'assistant',
      content: `Hi! I'm your privacy assistant for **${domain}**. I have access to the full privacy analysis including policy text, trackers, dark patterns, and compliance data. Ask me anything about this site's privacy practices.`,
    },
  ]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function sendMessage(text: string) {
    if (!text.trim() || isStreaming) return;
    const userMsg: ChatMessage = { role: 'user', content: text.trim() };

    // Build conversation history (exclude streaming placeholder)
    const history = messages
      .filter(m => !m.streaming)
      .map(m => ({ role: m.role, content: m.content }));
    history.push(userMsg);

    setMessages(prev => [
      ...prev,
      userMsg,
      { role: 'assistant', content: '', streaming: true },
    ]);
    setInput('');
    setIsStreaming(true);

    try {
      let accumulated = '';
      await streamChatResponse(domain, history, (chunk) => {
        accumulated += chunk;
        setMessages(prev => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last.streaming) {
            updated[updated.length - 1] = { ...last, content: accumulated };
          }
          return updated;
        });
      });
      // Finalize — remove streaming flag
      setMessages(prev => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (last.streaming) {
          updated[updated.length - 1] = { role: 'assistant', content: accumulated || last.content };
        }
        return updated;
      });
    } catch (err: any) {
      setMessages(prev => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (last.streaming) {
          updated[updated.length - 1] = {
            role: 'assistant',
            content: 'Sorry, I encountered an error. Make sure ANTHROPIC_API_KEY is set in backend/.env.',
          };
        }
        return updated;
      });
    } finally {
      setIsStreaming(false);
    }
  }

  function handleKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  }

  function clearChat() {
    setMessages([{
      role: 'assistant',
      content: `Hi! I'm your privacy assistant for **${domain}**. Ask me anything about this site's privacy practices.`,
    }]);
  }

  return (
    <div className="flex flex-col" style={{ height: '600px' }}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-surface/40 rounded-t-xl shrink-0">
        <div className="flex items-center gap-2.5">
          <div className="w-2 h-2 rounded-full bg-accent-green animate-pulse" />
          <span className="text-sm font-semibold text-white/80">Privacy Assistant</span>
          <span className="text-xs text-white/30 font-mono">· {domain}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono text-white/25 bg-white/5 px-2 py-0.5 rounded">
            claude-haiku-4-5
          </span>
          <button
            onClick={clearChat}
            className="text-xs text-white/30 hover:text-white/60 font-mono transition-colors px-2 py-1 rounded hover:bg-white/5"
          >
            Clear
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4 scrollbar-thin scrollbar-track-transparent scrollbar-thumb-white/10">
        {messages.map((msg, i) => (
          <MessageBubble key={i} msg={msg} />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Suggested Questions — show only when just the welcome message exists */}
      {messages.length === 1 && (
        <div className="px-4 pb-3 shrink-0">
          <div className="text-xs font-mono text-white/25 mb-2">Suggested questions</div>
          <div className="flex flex-wrap gap-2">
            {SUGGESTED_QUESTIONS.map((q, i) => (
              <button
                key={i}
                onClick={() => sendMessage(q)}
                disabled={isStreaming}
                className="text-xs text-white/50 bg-white/5 border border-border hover:bg-white/10 hover:text-white/80
                           hover:border-white/20 rounded-lg px-3 py-1.5 transition-all disabled:opacity-40 text-left"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <div className="px-4 pb-4 pt-2 border-t border-border shrink-0 bg-surface/20 rounded-b-xl">
        <div className="flex items-end gap-2 rounded-xl border border-border bg-surface/60 focus-within:border-accent-green/40 transition-colors p-1">
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder={`Ask about ${domain}'s privacy…`}
            rows={1}
            disabled={isStreaming}
            className="flex-1 bg-transparent text-sm text-white/80 placeholder:text-white/25 resize-none px-3 py-2
                       outline-none scrollbar-hide disabled:opacity-50 min-h-[36px] max-h-[120px]"
            style={{ fieldSizing: 'content' } as React.CSSProperties}
          />
          <button
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || isStreaming}
            className="w-8 h-8 rounded-lg bg-accent-green/20 border border-accent-green/30 text-accent-green
                       hover:bg-accent-green/30 transition-all disabled:opacity-30 disabled:cursor-not-allowed
                       flex items-center justify-center text-sm mb-1 mr-1 shrink-0"
          >
            {isStreaming ? (
              <span className="w-3 h-3 rounded-full border-2 border-accent-green/60 border-t-accent-green animate-spin" />
            ) : (
              '↑'
            )}
          </button>
        </div>
        <p className="text-[10px] text-white/20 font-mono mt-1.5 text-center">
          Enter to send · Shift+Enter for new line · Powered by Claude
        </p>
      </div>
    </div>
  );
}
