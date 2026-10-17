---
title: "CI/CD Pipeline"
weight: 1
---

# CI/CD Pipeline

## Overview

This page documents the project's real automation: a CI workflow that runs the same checks you run locally, a Docker image for deployment, pinned dependencies, and a workflow that publishes this documentation.

## Pipeline Architecture

### High-Level Flow

```
Developer Push / Pull Request
  ↓
GitHub Actions Triggered
  ↓
┌──────────────────────────────┐
│  CI (matrix: Python 3.10,    │
│  3.12)                       │
├──────────────────────────────┤
│  1. pip install -e ".[dev]"  │
│  2. ruff check .             │
│  3. ruff format --check .    │
│  4. mypy (strict)            │
│  5. unittest discover        │
└──────────────────────────────┘

Push to main touching docs/
  ↓
┌──────────────────────────────┐
│  Docs                        │
├──────────────────────────────┤
│  1. hugo --minify            │
│  2. Deploy to GitHub Pages   │
└──────────────────────────────┘
```

## GitHub Actions Workflows

### Workflow 1: CI

**File**: `.github/workflows/ci.yml`

```yaml
name: CI

on:
  push:
  pull_request:

jobs:
  check:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip
      - run: pip install -e ".[dev]"
      - run: ruff check .
      - run: ruff format --check .
      - run: mypy
      - run: python -m unittest discover -s tests
```

**What each step guards**:

| Step | Guards |
|------|--------|
| `ruff check .` | lint rules (`E`, `F`, `W`, `I`, `B`, `UP`, `SIM`, `C4`, `RUF`), line length 100 |
| `ruff format --check .` | consistent formatting |
| `mypy` | `strict = true` over `crypto_alarm/` |
| `unittest` | alarm rules, monitor behavior, persistence |

The matrix runs the minimum supported Python (3.10, from `requires-python`) and the version used in Docker (3.12).

### Workflow 2: Docs

**File**: `.github/workflows/docs.yml`

Builds the Hugo site and deploys it to GitHub Pages whenever `docs/` changes on `main` (or when triggered manually). See [GitHub Actions Setup]({{% relref "/devops/github-actions-setup" %}}) for the details.

## Testing Strategy

### What the tests cover

- `tests/test_alarms.py`: the pure rules (`rules.py`): input validation, target crossing, extremes, timeframe windows
- `tests/test_monitor.py`: a real `Monitor` with a fake Binance client and an injected clock: adding pairs, trigger-once behavior, restart cooldown, stale prices, "since start" repeats, max/min reset, history sampling, persistence round trip, corrupt file handling

### Why this design is testable

- Trigger logic lives in pure functions (no clocks, locks or I/O)
- `Monitor` takes its Binance client, store and notifier as constructor arguments
- `check_alarms(now)` accepts the current time, so tests control the clock

### Running locally

```
pip install -e ".[dev]"
python -m unittest discover -s tests
```

## Code Quality Tools

All configuration is in `pyproject.toml`:

```toml
[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP", "SIM", "C4", "RUF"]

[tool.mypy]
python_version = "3.10"
strict = true
files = ["crypto_alarm"]
```

Fix formatting automatically with `ruff format .`.

## Docker Configuration

### Dockerfile

```dockerfile
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    CRYPTO_ALARM_HOST=0.0.0.0 \
    CRYPTO_ALARM_DATA=/data/crypto_data_binance.json \
    CRYPTO_ALARM_LOG_JSON=1

WORKDIR /app

# Dependencies first so this layer is cached until requirements.lock changes.
COPY requirements.lock .
RUN pip install -r requirements.lock

COPY pyproject.toml README.md ./
COPY crypto_alarm ./crypto_alarm
RUN pip install --no-deps . \
    && useradd --system --no-create-home app \
    && mkdir /data && chown app /data

USER app
VOLUME /data
EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/healthz', timeout=3)"

# One worker only: pairs, alarms and price history live in this process.
CMD ["gunicorn", "--worker-class", "gthread", "--workers", "1", "--threads", "100", \
     "--bind", "0.0.0.0:5000", "crypto_alarm.web:create_app()"]
```

**Design notes**:
- Layer caching: dependencies are installed before the source is copied
- `--no-deps` for the app itself, because `requirements.lock` already pinned everything
- Runs as an unprivileged `app` user, which owns only the `/data` volume
- The health check calls `/healthz`, which returns 503 when the Binance feed is down, so Docker marks the container unhealthy
- **One worker** is not optional: state lives in the process

### Docker Compose

```yaml
services:
  crypto-alarm:
    build: .
    ports:
      - "127.0.0.1:5000:5000"   # published on localhost only; there is no authentication
    volumes:
      - alarm-data:/data
    env_file:
      - path: .env
        required: false
    restart: unless-stopped

volumes:
  alarm-data:
```

Notification credentials and other settings go in a `.env` file next to `docker-compose.yml` (`.env.example` lists every variable). The file is optional.

### Dependency Pinning

Version ranges live in `pyproject.toml`. Exact versions for Docker are pinned in `requirements.lock`:

```
pip install -e ".[server]" && pip freeze --exclude-editable > requirements.lock
```

Keep the two comment lines at the top of that file.

## Documentation Publishing

### Hugo Build Configuration

```toml
# docs/hugo.toml
baseURL = 'https://karmen87.github.io/Crypto_Alarm/'
languageCode = 'en-us'
title = 'Crypto Price Alarm | Technical Documentation'
theme = 'hugo-theme-relearn'

[params]
themeVariant = 'relearn-dark'
```

### GitHub Pages Deployment

`.github/workflows/docs.yml` builds with Hugo 0.141.0 (extended) and publishes through `actions/deploy-pages`. The Relearn theme is vendored in `docs/themes/hugo-theme-relearn`, so no submodule checkout is needed.

## Local Development Workflow

### Run the checks CI runs

```
ruff check .
ruff format --check .      # `ruff format .` to fix
mypy
python -m unittest discover -s tests
```

### Run the app

```
python -m crypto_alarm              # http://localhost:5000
docker compose up -d --build        # or with Docker
```

### Preview the docs

```
cd docs
hugo server
# Visit http://localhost:1313/Crypto_Alarm/
```

## Security Best Practices

### Secrets Management

- Notification tokens (`TELEGRAM_BOT_TOKEN`, `ALARM_WEBHOOK_URL`) are read from the environment only, never committed
- `.env` is git-ignored; `.env.example` contains placeholders only
- Logs never include request URLs, because Telegram's URL embeds the bot token

### Container Hardening

- Non-root user, slim base image, no build tools in the final image
- Port published on `127.0.0.1` only, because the app has no authentication

## Not Automated (Yet)

For accuracy, these are things the project does **not** currently do in CI:

- Publishing Docker images to a registry
- Release tagging and changelog generation
- Dependency update bots and vulnerability scanning
- Scheduled workflow runs

They would be natural additions (for example Dependabot for `requirements.lock`).

## Troubleshooting CI/CD

### Common Issues

**`ruff format --check` fails**
```
# Solution: format locally and commit
ruff format .
```

**`mypy` reports errors only in CI**
```
# Solution: use the same Python as the matrix (3.10) and the same extras
pip install -e ".[dev]"
```

**The Docker build can't find a package**
```
# Solution: regenerate the lock file
pip install -e ".[server]" && pip freeze --exclude-editable > requirements.lock
```

## Next Steps

- See **GitHub Actions Setup** for the documentation workflow
- Check **Implementations** for architecture details
