// Privacy Nutrition Label – Background Service Worker
'use strict';

// Track requests per tab
const tabTrackers = new Map(); // tabId -> Set of tracker domains

// Tracker domain patterns (subset for real-time detection)
const KNOWN_TRACKERS = new Set([
  'google-analytics.com', 'googletagmanager.com', 'analytics.google.com',
  'doubleclick.net', 'googlesyndication.com', 'googleadservices.com',
  'connect.facebook.net', 'facebook.net', 'hotjar.com', 'static.hotjar.com',
  'mixpanel.com', 'segment.com', 'segment.io', 'amplitude.com',
  'fullstory.com', 'logrocket.com', 'clarity.ms', 'heap.io',
  'criteo.com', 'adroll.com', 'ads.twitter.com', 'platform.twitter.com',
  'snap.licdn.com', 'sc-static.net', 'static.klaviyo.com',
  'js.hs-scripts.com', 'munchkin.marketo.net', 'bat.bing.com',
  'quantserve.com', 'scorecardresearch.com', 'adnxs.com',
  'pubmatic.com', 'rubiconproject.com', 'openx.net', 'taboola.com',
  'outbrain.com', 'fingerprintjs.com', 'fpjs.io',
  'tiktok.com', 'analytics.tiktok.com', 'ads.pinterest.com',
]);

const HIGH_RISK = new Set([
  'doubleclick.net', 'connect.facebook.net', 'facebook.net',
  'fingerprintjs.com', 'fpjs.io', 'hotjar.com', 'fullstory.com',
  'criteo.com', 'quantserve.com', 'adnxs.com',
]);

function extractDomain(url) {
  try {
    const parsed = new URL(url);
    return parsed.hostname.replace(/^www\./, '');
  } catch { return ''; }
}

function matchesTracker(domain) {
  if (KNOWN_TRACKERS.has(domain)) return domain;
  // Check parent domains
  const parts = domain.split('.');
  for (let i = 1; i < parts.length - 1; i++) {
    const parent = parts.slice(i).join('.');
    if (KNOWN_TRACKERS.has(parent)) return parent;
  }
  return null;
}

function updateBadge(tabId) {
  const trackers = tabTrackers.get(tabId);
  if (!trackers) return;
  const count = trackers.size;
  const text = count > 0 ? String(count) : '';
  const color = count > 15 ? '#ff1744' : count > 5 ? '#ff9100' : '#ffd740';

  chrome.action.setBadgeText({ text, tabId }).catch(() => {});
  chrome.action.setBadgeBackgroundColor({ color, tabId }).catch(() => {});
}

// Listen to all web requests
chrome.webRequest.onBeforeRequest.addListener(
  (details) => {
    if (details.tabId < 0) return;
    const domain = extractDomain(details.url);
    const matched = matchesTracker(domain);

    if (matched) {
      if (!tabTrackers.has(details.tabId)) {
        tabTrackers.set(details.tabId, new Set());
      }
      tabTrackers.get(details.tabId).add(matched);
      updateBadge(details.tabId);

      // Store for popup
      chrome.storage.local.get(`trackers_${details.tabId}`, (data) => {
        const existing = data[`trackers_${details.tabId}`] || { count: 0, items: [] };
        const items = existing.items;
        if (!items.some(t => t.domain === matched)) {
          items.push({
            domain: matched,
            risk: HIGH_RISK.has(matched) ? 'high' : 'medium',
          });
        }
        chrome.storage.local.set({
          [`trackers_${details.tabId}`]: {
            count: tabTrackers.get(details.tabId)?.size || 0,
            items,
          }
        });
      });
    }
  },
  { urls: ['<all_urls>'] },
);

// Clear tracker data when tab navigates
chrome.webNavigation.onBeforeNavigate.addListener((details) => {
  if (details.frameId === 0) {
    tabTrackers.delete(details.tabId);
    chrome.storage.local.remove(`trackers_${details.tabId}`);
    chrome.action.setBadgeText({ text: '', tabId: details.tabId }).catch(() => {});
  }
});

// Clear when tab closes
chrome.tabs.onRemoved.addListener((tabId) => {
  tabTrackers.delete(tabId);
  chrome.storage.local.remove(`trackers_${tabId}`);
});

console.log('Privacy Nutrition Label – background worker started');
