import axios from 'axios';
import type { AnalysisResult, DomainHistory, PolicyAIAnalysis, EcosystemMap, ChatMessage } from './types';

const API = axios.create({ baseURL: '/api', timeout: 90000 });

export async function analyzeWebsite(url: string, forceRefresh = false): Promise<AnalysisResult> {
  const { data } = await API.post('/analyze', { url, force_refresh: forceRefresh });
  return data;
}

export async function getDomainHistory(domain: string): Promise<DomainHistory> {
  const { data } = await API.get(`/history/${domain}`);
  return data;
}

export async function getRecentDomains(): Promise<{ domains: Array<{ domain: string; score: number; grade: string; analyzed_at: string }> }> {
  const { data } = await API.get('/recent');
  return data;
}

// ─── AI API ─────────────────────────────────────────────────────────────────

export async function checkAIStatus(): Promise<{ available: boolean; model: string }> {
  const { data } = await API.get('/ai/status');
  return data;
}

export async function getAIInsights(domain: string): Promise<PolicyAIAnalysis> {
  const { data } = await API.post('/ai/analyze', { domain });
  return data;
}

export async function getEcosystemResearch(domain: string, maxParties = 12): Promise<EcosystemMap> {
  const { data } = await API.post('/ai/research-ecosystem', { domain, max_parties: maxParties });
  return data;
}

/**
 * Stream a chat response from the privacy assistant.
 * Calls onChunk for each text token. Resolves when stream ends.
 */
export async function streamChatResponse(
  domain: string,
  messages: ChatMessage[],
  onChunk: (text: string) => void,
): Promise<void> {
  const response = await fetch('/api/ai/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ domain, messages }),
  });

  if (!response.ok) {
    throw new Error(`Chat request failed: ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) return;

  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // Process complete SSE lines
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6).trim();
        if (data === '[DONE]') return;
        if (data && !data.startsWith('[ERROR')) {
          // Restore escaped newlines
          onChunk(data.replace(/\\n/g, '\n'));
        }
      }
    }
  }
}
