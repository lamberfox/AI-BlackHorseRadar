# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GitHub daily "black horse" radar: scrapes GitHub for fast-growing repos (past 3 days), analyzes each with DeepSeek, and pushes a Markdown daily report to a WeCom (企业微信) webhook. Runs fully via GitHub Actions — no servers.

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Local dev: copy .env.example → .env and fill in secrets, then:
python src/main.py

# Run tests (once they exist)
python -m pytest tests/

# Run a single test file
python -m pytest tests/test_scraper.py -v
```

Local `.env` (never commit):
```
DEEPSEEK_API_KEY=...
WECOM_WEBHOOK_URL=...
```

## Architecture

Four-layer pipeline, each in its own module under `src/`:

| Layer | File | Responsibility |
|-------|------|----------------|
| Orchestration | `main.py` | Wires scrape → analyze → notify; catches top-level failures |
| Scraping | `scraper.py` | GitHub Search API + README fetch; returns list of `Project` objects |
| Analysis | `analyzer.py` | Sends project metadata + README to DeepSeek; returns structured JSON |
| Notification | `notifier.py` | Assembles Markdown daily report; POSTs to WeCom webhook |
| Data models | `models.py` | `dataclass` or Pydantic models for `Project` and `AnalysisResult` |
| Utilities | `utils.py` | Retry decorator, logger, time formatting |

CI/CD: `.github/workflows/radar.yml` — cron `0 1 * * *` (UTC) = Beijing 09:00.

## Key Design Rules

**Resilience** — single project failure must not abort the batch. Each project's scrape and analysis runs inside `try/except`; failures produce a degraded result, not an exception.

**Rate limiting** — `time.sleep(2)` after every per-project GitHub API request. GitHub token comes from `GITHUB_TOKEN` env var (Actions provides this automatically).

**Token budget** — README truncated to `README_MAX_LEN` characters (default 2000) before sending to DeepSeek. Never feed unbounded text to the model.

**Zero hard-coded secrets** — `DEEPSEEK_API_KEY` and `WECOM_WEBHOOK_URL` come only from environment variables. Logs must never print Authorization headers or full webhook URLs.

**Fallback notification** — even if all analysis fails, `notifier.py` must send at least a summary ("N projects fetched, 0 analyzed — see logs").

## Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `DEEPSEEK_API_KEY` | Yes | — | DeepSeek API auth |
| `WECOM_WEBHOOK_URL` | Yes | — | WeCom bot endpoint |
| `GITHUB_TOKEN` | No | Actions-provided | GitHub API auth |
| `TOP_N` | No | 10 | Projects to fetch |
| `ANALYZE_N` | No | 5 | Projects to analyze |
| `README_MAX_LEN` | No | 2000 | README character cap |

## DeepSeek Analyzer Output Schema

The prompt must enforce JSON-only output with exactly these fields:

```json
{
  "pain_point": "...",
  "implementation_guess": "...",
  "competitors": "...",
  "killer_feature": "...",
  "dark_horse_score": 1,
  "follow_up": "yes/no + one sentence"
}
```

Prompt framing: "技术 VC 视角，禁止营销词" (technical VC perspective, no marketing language). When data is insufficient, output "推测依据不足" rather than fabricating.

## GitHub Actions Workflow Requirements

- Trigger: `schedule` (cron) + `workflow_dispatch`
- Permissions: `contents: read` only
- Mask secrets before running: `echo "::add-mask::$DEEPSEEK_API_KEY"`
- Steps: checkout → setup-python → pip install → mask secrets → `python src/main.py`

## Definition of Done

- Manual `workflow_dispatch` run pushes a report to WeCom
- Cron fires at 09:00 Beijing time automatically
- At least 5 projects fetched and analysis attempted
- Single project failure does not abort the pipeline
- No plaintext secrets in repo or logs
