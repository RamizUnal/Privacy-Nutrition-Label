# Project Memory

Simple working context for this branch.

## Branch

- Active branch: `berin-dev-2`.
- Accidental `main` work was preserved earlier; current implementation work is on this branch.

## Privacy Policy Discovery

- Default discovery order in `/analyze`:
  1. Return cached analysis unless `force_refresh=true`.
  2. Try `KNOWN_POLICY_URLS`, unless `SKIP_KNOWN_POLICY_URLS=true`.
  3. Use Brave Search for `<domain> privacy policy`, then stricter site query fallback.
  4. Scan homepage links.
  5. Try canonical policy paths.
  6. Check sitemap/robots sitemap entries.
- Force re-analyze skips the database cache, but still starts discovery fresh from this order.
- Force re-analyze does not reuse the previous saved policy URL.

## Search And Ranking

- Brave Search finds candidate URLs; it does not decide the answer alone.
- Local Python heuristics rank and reject candidates before fetching.
- Claude/Anthropic search reranking is optional via `ENABLE_AI_SEARCH_RERANK=true`, but the project must work without a valid Claude key.
- `SKIP_KNOWN_POLICY_URLS=true` is useful for testing Brave discovery without the hardcoded map.

## Policy Reading

- Candidate pages must be fetched and validated before analysis.
- The crawler handles:
  - normal static HTML extraction,
  - embedded JSON/JS text extraction,
  - Reddit's simple JS verification form,
  - optional Playwright rendering,
  - Jina Reader fallback for JS/app-shell policy pages.
- Jina is a reader fallback, not the primary policy finder.

## Known Tricky Sites

- `amazon.com`: map points to the consumer Amazon Privacy Notice; Brave mode must avoid AWS/Amazon Ads policies.
- `reddit.com`: uses Reddit JS challenge solver, not Jina.
- `rockstar.com`: alias to `rockstargames.com`; official policy is JS-rendered, so reader fallback helps.
- `facebook.com` / `instagram.com`: use `mbasic.facebook.com` policy for fuller extractable text.
- `google.com` / `youtube.com`: use `policies.google.com/privacy?hl=en`.

## Dynamic Scan

- Dynamic scan means Playwright S0/S1/S2 browser crawling:
  - `S0`: baseline, no consent click.
  - `S1`: reject/decline cookies.
  - `S2`: accept cookies.
- It populates the Dynamic Scan tab and feeds technical/mismatch scoring.
- Requires Playwright plus Chromium installed in `backend/venv`.
- `ENABLE_DYNAMIC_CRAWL=false` in the example env because it adds noticeable latency; local `.env` can turn it on.
