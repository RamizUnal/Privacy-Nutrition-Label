// Privacy Nutrition Label – Content Script
// Runs on every page to detect inline trackers and signals
'use strict';

(function () {
  if (window.__privacyLabelInjected) return;
  window.__privacyLabelInjected = true;

  // Collect signals from the page
  const signals = {
    hasConsentBanner: false,
    cmpName: null,
    hasDntHeader: false,
    cookieCount: 0,
    inlineScriptSignals: [],
    darkPatternSignals: [],
  };

  // Detect CMP / consent banners
  const CMP_SELECTORS = [
    '#cookiebanner', '#cookie-banner', '#cookie-consent', '#gdpr-banner',
    '.cookie-consent', '.gdpr-banner', '.consent-banner',
    '[id*="onetrust"]', '[id*="cookielaw"]', '[id*="cookiebot"]',
    '[class*="cookieconsent"]', '[class*="cookie-notice"]',
    '[aria-label*="cookie"]', '[aria-label*="consent"]',
  ];

  for (const sel of CMP_SELECTORS) {
    if (document.querySelector(sel)) {
      signals.hasConsentBanner = true;
      break;
    }
  }

  // Detect CMP script patterns
  const scriptTags = document.querySelectorAll('script[src]');
  for (const s of scriptTags) {
    const src = (s.getAttribute('src') || '').toLowerCase();
    if (src.includes('onetrust')) { signals.cmpName = 'OneTrust'; break; }
    if (src.includes('cookiebot')) { signals.cmpName = 'Cookiebot'; break; }
    if (src.includes('trustarc')) { signals.cmpName = 'TrustArc'; break; }
    if (src.includes('osano')) { signals.cmpName = 'Osano'; break; }
    if (src.includes('usercentrics')) { signals.cmpName = 'Usercentrics'; break; }
    if (src.includes('didomi')) { signals.cmpName = 'Didomi'; break; }
    if (src.includes('iubenda')) { signals.cmpName = 'Iubenda'; break; }
  }

  // Count cookies
  signals.cookieCount = document.cookie.split(';').filter(c => c.trim()).length;

  // Check inline scripts for fingerprinting
  const FINGERPRINT_PATTERNS = [
    /canvas\.toDataURL/,
    /AudioContext\(\)/,
    /WebGLRenderingContext/,
    /navigator\.plugins\b/,
    /navigator\.hardwareConcurrency/,
    /screen\.colorDepth/,
    /FingerprintJS/,
    /Fingerprint2/,
  ];

  const inlineScripts = document.querySelectorAll('script:not([src])');
  for (const s of inlineScripts) {
    const content = s.textContent || '';
    for (const pat of FINGERPRINT_PATTERNS) {
      if (pat.test(content)) {
        signals.inlineScriptSignals.push(`Fingerprinting: ${pat.source.substring(0, 40)}`);
        break;
      }
    }
  }

  // Look for dark pattern text in DOM (accept buttons, reject buttons)
  const buttons = document.querySelectorAll('button, [role="button"], a');
  const ACCEPT_PATTERNS = /accept\s*all|i\s*agree|allow\s*all|ok|got\s*it/i;
  const REJECT_PATTERNS = /reject|decline|no\s*thanks|only\s*necessary|manage\s*preferences/i;

  let hasProminentAccept = false;
  let hasHiddenReject = false;

  for (const btn of buttons) {
    const text = btn.textContent?.trim() || '';
    if (ACCEPT_PATTERNS.test(text)) {
      hasProminentAccept = true;
    }
  }

  // Check if reject/manage is less prominent (simple heuristic)
  const rejectBtns = Array.from(buttons).filter(b => REJECT_PATTERNS.test(b.textContent || ''));
  if (hasProminentAccept && rejectBtns.length === 0) {
    signals.darkPatternSignals.push('No visible reject/decline option found');
    hasHiddenReject = true;
  }

  // Check for pre-checked checkboxes
  const checkboxes = document.querySelectorAll('input[type="checkbox"]');
  for (const cb of checkboxes) {
    if (cb.checked && (cb.name?.toLowerCase().includes('consent') || cb.id?.toLowerCase().includes('consent'))) {
      signals.darkPatternSignals.push('Pre-ticked consent checkbox detected');
    }
  }

  // Send signals to background
  chrome.runtime.sendMessage({
    type: 'PAGE_SIGNALS',
    signals,
    url: window.location.href,
  }).catch(() => {});

  // Store locally
  chrome.storage.local.set({
    [`page_signals_${window.location.hostname.replace('www.', '')}`]: signals,
  });

})();
