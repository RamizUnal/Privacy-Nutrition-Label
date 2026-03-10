// Privacy Nutrition Label – Popup Script
'use strict';

const API_BASE = 'http://localhost:8000';

const GRADE_COLORS = { A: '#00e676', B: '#40c4ff', C: '#ffd740', D: '#ff9100', F: '#ff1744' };
const RISK_COLORS = { low: '#00e676', medium: '#ffd740', high: '#ff9100', critical: '#ff1744' };
const BAR_DIMS = [
  { key: 'data_collection', label: 'Data Coll.' },
  { key: 'sharing', label: 'Sharing' },
  { key: 'transparency', label: 'Clarity' },
  { key: 'rights', label: 'Rights' },
  { key: 'retention', label: 'Retention' },
  { key: 'dark_patterns', label: 'No DarkPat.' },
  { key: 'technical', label: 'Technical' },
];

function getColor(score) {
  if (score >= 75) return '#00e676';
  if (score >= 50) return '#ffd740';
  if (score >= 30) return '#ff9100';
  return '#ff1744';
}

function show(id) { document.getElementById(id).style.display = ''; }
function hide(id) { document.getElementById(id).style.display = 'none'; }
function setText(id, text) { const el = document.getElementById(id); if (el) el.textContent = text; }

async function getCurrentTab() {
  return new Promise(resolve => {
    chrome.tabs.query({ active: true, currentWindow: true }, tabs => resolve(tabs[0]));
  });
}

async function getLiveTrackers(tabId) {
  return new Promise(resolve => {
    chrome.storage.local.get(`trackers_${tabId}`, data => {
      resolve(data[`trackers_${tabId}`] || { count: 0, items: [] });
    });
  });
}

function renderScoreBars(breakdown) {
  const container = document.getElementById('score-bars');
  if (!container || !breakdown) return;
  container.innerHTML = '';
  BAR_DIMS.forEach(dim => {
    const score = breakdown[dim.key] ?? 0;
    const color = getColor(score);
    const row = document.createElement('div');
    row.className = 'bar-row';
    row.innerHTML = `
      <span class="bar-label">${dim.label}</span>
      <div class="bar-track">
        <div class="bar-fill" style="width:${score}%;background:${color}"></div>
      </div>
      <span class="bar-val" style="color:${color}">${score}</span>
    `;
    container.appendChild(row);
  });
}

function renderAlerts(data) {
  const container = document.getElementById('alerts-section');
  if (!container) return;
  const alerts = [];

  if (data.dark_patterns?.count > 0) {
    alerts.push({
      icon: '🎭',
      text: `${data.dark_patterns.count} dark pattern(s) detected in privacy policy`,
      color: '#ff1744',
      bg: 'rgba(255,23,68,0.08)',
    });
  }
  if (data.trackers?.fingerprinting_detected) {
    alerts.push({
      icon: '🔮',
      text: 'Browser fingerprinting detected – tracks you without cookies',
      color: '#ff6b00',
      bg: 'rgba(255,107,0,0.08)',
    });
  }
  if (data.trackers?.session_recording_detected) {
    alerts.push({
      icon: '🎥',
      text: 'Session recording active – captures all mouse/keyboard activity',
      color: '#ff9100',
      bg: 'rgba(255,145,0,0.08)',
    });
  }
  if (data.third_parties?.data_sold) {
    alerts.push({
      icon: '💰',
      text: 'Personal data is sold to third parties (CCPA opt-out available)',
      color: '#ff1744',
      bg: 'rgba(255,23,68,0.08)',
    });
  }
  if (!data.policy_found) {
    alerts.push({
      icon: '⚠',
      text: 'No privacy policy found – legally required under GDPR & CCPA',
      color: '#ff1744',
      bg: 'rgba(255,23,68,0.08)',
    });
  }
  if (data.rights?.gdpr_score < 50) {
    alerts.push({
      icon: '⚖️',
      text: `Only ${data.rights.gdpr_score}% of GDPR rights covered in policy`,
      color: '#ffd740',
      bg: 'rgba(255,215,64,0.08)',
    });
  }

  if (alerts.length === 0) {
    container.innerHTML = `
      <div class="alert" style="border-color:rgba(0,230,118,0.3);background:rgba(0,230,118,0.05)">
        <span class="alert-icon">✓</span>
        <span class="alert-text" style="color:#00e676">No critical issues detected in this policy.</span>
      </div>
    `;
    return;
  }

  container.innerHTML = alerts.map(a => `
    <div class="alert" style="border-color:${a.color}30;background:${a.bg}">
      <span class="alert-icon">${a.icon}</span>
      <span class="alert-text">${a.text}</span>
    </div>
  `).join('');
}

function renderTrackerList(trackers) {
  if (!trackers || !trackers.trackers || trackers.trackers.length === 0) return;
  const section = document.getElementById('trackers-section');
  const list = document.getElementById('tracker-list');
  if (!section || !list) return;
  section.style.display = '';

  const RISK_DOT_COLORS = { low: '#22c55e', medium: '#f59e0b', high: '#ff6b00', critical: '#ff2d2d' };
  const items = trackers.trackers.slice(0, 8);
  list.innerHTML = items.map(t => `
    <div class="tracker-item">
      <span class="tracker-name">${t.name}</span>
      <div style="display:flex;align-items:center;gap:6px">
        <span style="font-size:10px;color:rgba(255,255,255,0.3);font-family:monospace">${t.category.split('/')[0].trim()}</span>
        <div class="risk-dot" style="background:${RISK_DOT_COLORS[t.risk] || '#888'}"></div>
      </div>
    </div>
  `).join('');
  if (trackers.trackers.length > 8) {
    list.innerHTML += `<div style="font-size:10px;color:rgba(255,255,255,0.2);font-family:monospace;padding:4px 0">+${trackers.trackers.length - 8} more…</div>`;
  }
}

async function analyze(tab, forceRefresh = false) {
  show('loading');
  hide('content');
  hide('no-policy');

  try {
    const url = tab.url.replace(/\/$/, '');
    const response = await fetch(`${API_BASE}/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, force_refresh: forceRefresh }),
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();

    // Update full analysis link
    const openBtn = document.getElementById('open-full');
    if (openBtn) openBtn.href = `http://localhost:5173?url=${encodeURIComponent(url)}`;

    // Render grade
    const grade = data.grade || 'F';
    const score = data.overall_score ?? 0;
    const gradeColor = GRADE_COLORS[grade] || '#888';
    const circle = document.getElementById('grade-circle');
    if (circle) {
      circle.style.borderColor = gradeColor;
      circle.style.boxShadow = `0 0 20px ${gradeColor}30`;
    }
    const gradeLetter = document.getElementById('grade-letter');
    if (gradeLetter) { gradeLetter.textContent = grade; gradeLetter.style.color = gradeColor; }
    setText('grade-score', `${score}/100`);
    setText('domain-name', data.domain || '');

    const riskBadge = document.getElementById('risk-badge');
    if (riskBadge && data.risk_level) {
      const riskColor = RISK_COLORS[data.risk_level] || '#888';
      riskBadge.textContent = data.risk_level.toUpperCase() + ' RISK';
      riskBadge.style.color = riskColor;
      riskBadge.style.background = `${riskColor}15`;
      riskBadge.style.borderColor = `${riskColor}40`;
    }

    const summaryEl = document.getElementById('summary-text');
    if (summaryEl && data.summary) {
      summaryEl.textContent = data.summary.substring(0, 100) + (data.summary.length > 100 ? '…' : '');
    }

    // Stats
    setText('stat-trackers', data.trackers?.total_tracker_count ?? 0);
    setText('stat-cookies', data.trackers?.cookies?.length ?? 0);
    setText('stat-parties', data.third_parties?.count ?? 0);
    setText('stat-dark', data.dark_patterns?.count ?? 0);

    // Score bars
    renderScoreBars(data.score_breakdown);

    // Alerts
    renderAlerts(data);

    // Tracker list
    renderTrackerList(data.trackers);

    // Hide loading, show content
    hide('loading');
    show('content');

    // Store analysis for background
    chrome.storage.local.set({ [`analysis_${data.domain}`]: data });

  } catch (err) {
    hide('loading');
    show('no-policy');
    console.error('Privacy Label error:', err);
  }
}

// Get live tracker count from content script data
async function updateLiveCount(tabId) {
  const data = await getLiveTrackers(tabId);
  const el = document.getElementById('live-tracker-count');
  if (el) {
    el.textContent = data.count;
    el.style.color = data.count > 10 ? '#ff3b3b' : data.count > 5 ? '#ff9100' : '#ffd740';
  }
}

// Init
document.addEventListener('DOMContentLoaded', async () => {
  const tab = await getCurrentTab();
  if (!tab || !tab.url || !tab.url.startsWith('http')) {
    hide('loading');
    show('no-policy');
    return;
  }

  // Update live count
  updateLiveCount(tab.id);

  // Check cache first
  const domain = new URL(tab.url).hostname.replace('www.', '');
  const cached = await new Promise(resolve => {
    chrome.storage.local.get(`analysis_${domain}`, data => resolve(data[`analysis_${domain}`]));
  });

  if (cached) {
    // Show cached data immediately
    const data = cached;
    const grade = data.grade || 'F';
    const gradeColor = GRADE_COLORS[grade] || '#888';
    const circle = document.getElementById('grade-circle');
    if (circle) { circle.style.borderColor = gradeColor; }
    const gradeLetter = document.getElementById('grade-letter');
    if (gradeLetter) { gradeLetter.textContent = grade; gradeLetter.style.color = gradeColor; }
    setText('grade-score', `${data.overall_score ?? 0}/100`);
    setText('domain-name', data.domain || '');
    setText('stat-trackers', data.trackers?.total_tracker_count ?? 0);
    setText('stat-cookies', data.trackers?.cookies?.length ?? 0);
    setText('stat-parties', data.third_parties?.count ?? 0);
    setText('stat-dark', data.dark_patterns?.count ?? 0);
    renderScoreBars(data.score_breakdown);
    renderAlerts(data);
    renderTrackerList(data.trackers);

    const riskBadge = document.getElementById('risk-badge');
    if (riskBadge && data.risk_level) {
      const riskColor = RISK_COLORS[data.risk_level] || '#888';
      riskBadge.textContent = data.risk_level.toUpperCase() + ' RISK';
      riskBadge.style.color = riskColor;
      riskBadge.style.background = `${riskColor}15`;
      riskBadge.style.borderColor = `${riskColor}40`;
    }

    hide('loading');
    show('content');
  } else {
    await analyze(tab);
  }

  // Open full analysis
  document.getElementById('open-full')?.addEventListener('click', () => {
    chrome.tabs.create({ url: `http://localhost:5173` });
  });

  // Re-analyze button
  document.getElementById('reanalyze-btn')?.addEventListener('click', () => analyze(tab, true));
});
