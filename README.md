# Privacy Nutrition Label Generator

A comprehensive privacy analysis tool that generates FDA nutrition label–style privacy reports for any website.

## Features

- **Privacy Policy Crawler** – Auto-discovers `/privacy`, `/privacy-policy`, `/legal` paths
- **Data Category Detection** – 20+ categories including all GDPR Art. 9 special categories
- **Third-Party Analysis** – Identifies and rates 50+ known third parties
- **Tracker Detection** – Real-time detection of 80+ known trackers, pixels, iframes
- **Cookie Security Analysis** – HttpOnly, Secure, SameSite flags; cookie categorization
- **Dark Pattern Detection** – 9 pattern types based on EDPB Guidelines 03/2022
- **GDPR/CCPA Rights Coverage** – Checks for all 9 GDPR rights + 6 CCPA rights
- **Sentiment/Transparency Analysis** – Vagueness scoring, passive voice ratio, named entities
- **Retention Period Extraction** – Regex-based extraction and rating per GDPR Art. 5(1)(e)
- **Historical Tracking** – Stores versions, detects policy changes, generates diffs
- **Privacy Score** – Weighted 0-100 score with letter grade (A-F)
- **Browser Extension** – Real-time tracker counting with badge display

## Quick Start

```bash
chmod +x start.sh
./start.sh
```

Then open http://localhost:5173

## Manual Setup

### Backend
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
uvicorn main:app --reload --port 8000
```

## Stateful Batch Crawl (S0/S1/S2 + Human-in-the-loop)

Run automated crawl for a list of domains with consent-state comparison:

- **S0**: baseline (no consent click)
- **S1**: attempt reject flow
- **S2**: attempt accept flow

The batch runner flags difficult cases (`recaptcha`, bot/access blocks, login-required) and writes a human review queue.

```bash
cd backend
source venv/bin/activate
python run_batch_stateful.py --sites ../Project-Demo/sites.txt --outdir ../batch_out
```

Outputs:

- `results.jsonl`: per-site full state metrics and derived consent deltas
- `human_queue.jsonl`: only sites that require manual intervention
- `artifacts/<site>/S0.png|S1.png|S2.png`: screenshots for review

## Phase 0 Validation (stability before DB schema)

Use this before implementing session persistence/resume tables.

1) Prepare a small representative corpus in `backend/validation/phase0_corpus.txt`.

2) Run repeated headless validation:

```bash
cd backend
source venv/bin/activate
python phase0_validate.py \
	--sites validation/phase0_corpus.txt \
	--outdir ../phase0_out \
	--repeats 3 \
	--with-policy
```

3) Optional headful rerun for flagged/unstable sites:

```bash
python phase0_validate.py \
	--sites validation/phase0_corpus.txt \
	--outdir ../phase0_out \
	--repeats 3 \
	--with-policy \
	--headful-rerun-flagged
```

Main outputs:

- `results_repeat_<n>.jsonl`: per-repeat raw results
- `phase0_summary.json`: machine-readable stability report
- `phase0_summary.md`: quick human-readable summary
- `artifacts/repeat_<n>/<site>/`: screenshots for manual review

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Extension (Chrome)
1. Open `chrome://extensions`
2. Enable "Developer mode"
3. Click "Load unpacked"
4. Select the `extension/` folder

## Architecture

```
privacy-two/
├── backend/
│   ├── main.py                    # FastAPI app + endpoints
│   ├── crawler.py                 # Privacy policy crawler
│   ├── analyzer/
│   │   ├── data_categories.py     # 20+ data type taxonomy
│   │   ├── retention_parser.py    # Retention period extraction
│   │   ├── sentiment_analyzer.py  # Vagueness/transparency scoring
│   │   ├── dark_pattern_detector.py # EDPB 03/2022 patterns
│   │   ├── rights_checker.py      # GDPR/CCPA rights coverage
│   │   └── third_party_analyzer.py # Third-party identification
│   ├── tracker/
│   │   ├── detector.py            # HTML-based tracker detection
│   │   └── databases/
│   │       ├── trackers.json      # 80+ known trackers
│   │       └── third_parties.json # 40+ trust ratings
│   ├── database/                  # SQLAlchemy + SQLite
│   └── scoring/
│       └── privacy_scorer.py      # Weighted scoring (7 dimensions)
├── frontend/                      # React + TypeScript + Tailwind
│   └── src/components/
│       └── PrivacyLabel/          # 9 analysis panels
└── extension/                     # Chrome MV3 extension
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `POST /analyze` | POST | Full privacy analysis |
| `GET /history/{domain}` | GET | Analysis history |
| `GET /compare/{domain}` | GET | Compare two versions |
| `GET /recent` | GET | Recently analyzed |
| `GET /docs` | GET | Swagger UI |

## Privacy Score Methodology

| Dimension | Weight | Description |
|-----------|--------|-------------|
| Data Collection | 20% | Sensitivity of data types, sharing |
| Third-Party Sharing | 20% | Count, trust, data sale |
| Transparency | 15% | Vagueness, named parties, DPO |
| Rights Coverage | 15% | GDPR/CCPA rights mentioned |
| Retention | 12% | Specificity of retention periods |
| Dark Patterns | 10% | EDPB 03/2022 patterns |
| Technical | 8% | Tracker count, cookie security, fingerprinting |

## Legal References

- GDPR (EU) 2016/679 – especially Arts. 5, 6, 7, 9, 13, 15-22, 77
- CCPA/CPRA – Cal. Civ. Code §1798.100–1798.199
- EDPB Guidelines 03/2022 on Dark Patterns
- PECR (UK) / ePrivacy Directive 2002/58/EC
- COPPA (US) – 15 U.S.C. § 6501
- LGPD (Brazil) – Lei nº 13.709/2018
- ICO Guidance on Data Retention
- EDPB Guidelines on Consent (WP259 rev.01)
