# State Validation Tooling

## Purpose
- Deterministically validate S0/S1/S2 consent-state behavior.
- Validate click verification.
- Validate runtime known tracker matching.
- Validate mismatch_detected logic.
- Establish a stable baseline before testing real websites.

## Hosts setup
Add the following lines to `/etc/hosts`:

```bash
127.0.0.1 truthsite.test
127.0.0.1 tracker.test
```

## Run local truth-site server

```bash
./backend/venv/bin/python tools/state_validation/local_truth_site/server.py
```

## Run deterministic browser tests

```bash
PNL_TEST_MODE=true ./backend/venv/bin/python tools/state_validation/local_truth_site/run_state_tests.py
```

Expected:

```text
PASSED 7/7
```

## Run backend unit tests

```bash
./backend/venv/bin/python -m unittest discover -s backend/tests -p "test_*.py" -v
```

## Interpretation rules
- Known tracker count is based on tracker DB matching.
- Third-party request is not automatically a tracker.
- Consent cookies should not count as tracking cookies.
- Blocked/login/recaptcha means inconclusive/human review.
- Live websites are not deterministic.

## Secrets warning
- Do not commit `.env`.
- Redact API keys before sharing dumps.

## Validation after move

```bash
PNL_TEST_MODE=true ./backend/venv/bin/python tools/state_validation/local_truth_site/run_state_tests.py
./backend/venv/bin/python -m unittest discover -s backend/tests -p "test_*.py" -v
cd frontend && npm run -s build
```
