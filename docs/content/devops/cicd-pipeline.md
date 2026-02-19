---
title: "CI/CD Pipeline"
weight: 1
---

# CI/CD Pipeline: The Skill Shot

## Overview

This document showcases a professional CI/CD pipeline for the Crypto Price Alarm project, implementing automated testing, deployment, and documentation publishing using GitHub Actions.

## Pipeline Architecture

### High-Level Flow

```
Developer Push
  ↓
GitHub Actions Triggered
  ↓
┌─────────────────────────┐
│  Parallel Jobs          │
├─────────────────────────┤
│  1. JavaScript Tests    │
│  2. Python Tests        │
│  3. Lint & Format Check │
│  4. Security Scan       │
└────────┬────────────────┘
         │ All pass?
         ↓
┌─────────────────────────┐
│  Build & Package        │
├─────────────────────────┤
│  1. JavaScript Bundle   │
│  2. Python Docker Image │
│  3. Hugo Docs Site      │
└────────┬────────────────┘
         │
         ↓
┌─────────────────────────┐
│  Deploy (on main)       │
├─────────────────────────┤
│  1. GitHub Pages (docs) │
│  2. Docker Hub (image)  │
│  3. Release Artifacts   │
└─────────────────────────┘
```

## GitHub Actions Workflows

### Workflow 1: Test & Lint

**File**: `.github/workflows/test.yml`

```yaml
name: Test & Lint

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test-javascript:
    name: Test JavaScript App
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
          cache: 'npm'
          cache-dependency-path: javascript-app/package-lock.json

      - name: Install dependencies
        working-directory: javascript-app
        run: npm ci

      - name: Run linter
        working-directory: javascript-app
        run: npm run lint

      - name: Run unit tests
        working-directory: javascript-app
        run: npm test -- --coverage

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: javascript-app/coverage/lcov.info
          flags: javascript

  test-python:
    name: Test Python App
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.9', '3.10', '3.11']

    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Setup Python ${{ matrix.python-version }}
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
          cache: 'pip'

      - name: Install dependencies
        working-directory: python-app
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov flake8 black mypy

      - name: Run linter (flake8)
        working-directory: python-app
        run: flake8 app.py --max-line-length=100

      - name: Check formatting (black)
        working-directory: python-app
        run: black --check app.py

      - name: Type checking (mypy)
        working-directory: python-app
        run: mypy app.py --ignore-missing-imports

      - name: Run tests
        working-directory: python-app
        run: pytest --cov=. --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: python-app/coverage.xml
          flags: python

  security-scan:
    name: Security Scan
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
          severity: 'CRITICAL,HIGH'
          exit-code: '1'

      - name: SAST with Semgrep
        uses: returntocorp/semgrep-action@v1
        with:
          config: auto
```

### Workflow 2: Build & Deploy

**File**: `.github/workflows/deploy.yml`

```yaml
name: Build & Deploy

on:
  push:
    branches: [ main ]
  release:
    types: [ published ]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}/python-app

jobs:
  build-docs:
    name: Build & Deploy Documentation
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v3
        with:
          submodules: recursive  # Fetch Hugo themes

      - name: Setup Hugo
        uses: peaceiris/actions-hugo@v2
        with:
          hugo-version: '0.141.0'
          extended: true

      - name: Build Hugo site
        run: cd docs && hugo --minify

      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v3
        if: github.ref == 'refs/heads/main'
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./docs/public
          cname: crypto-alarm-docs.yourdomain.com  # Optional custom domain

  build-docker:
    name: Build & Push Docker Image
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2

      - name: Log in to Container Registry
        uses: docker/login-action@v2
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v4
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=ref,event=branch
            type=ref,event=pr
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=sha

      - name: Build and push
        uses: docker/build-push-action@v4
        with:
          context: ./python-app
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  release-artifacts:
    name: Create Release Artifacts
    runs-on: ubuntu-latest
    if: github.event_name == 'release'

    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Create JavaScript bundle
        run: |
          cd javascript-app
          zip -r ../crypto-alarm-javascript-${{ github.ref_name }}.zip .

      - name: Create Python bundle
        run: |
          cd python-app
          zip -r ../crypto-alarm-python-${{ github.ref_name }}.zip .

      - name: Upload release assets
        uses: softprops/action-gh-release@v1
        with:
          files: |
            crypto-alarm-javascript-${{ github.ref_name }}.zip
            crypto-alarm-python-${{ github.ref_name }}.zip
```

### Workflow 3: Scheduled Checks

**File**: `.github/workflows/scheduled.yml`

```yaml
name: Scheduled Health Checks

on:
  schedule:
    # Run every day at 00:00 UTC
    - cron: '0 0 * * *'
  workflow_dispatch:  # Allow manual trigger

jobs:
  dependency-check:
    name: Check for Dependency Updates
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Check npm outdated
        working-directory: javascript-app
        run: npm outdated || true

      - name: Check pip outdated
        working-directory: python-app
        run: |
          pip install pip-check
          pip-check || true

  api-health-check:
    name: Verify CoinGecko API
    runs-on: ubuntu-latest

    steps:
      - name: Test CoinGecko API
        run: |
          response=$(curl -s https://api.coingecko.com/api/v3/ping)
          echo "$response"
          echo "$response" | grep -q "gecko_says" || exit 1

      - name: Test sample price fetch
        run: |
          curl -f https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd

  link-check:
    name: Check Documentation Links
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Setup Hugo
        uses: peaceiris/actions-hugo@v2
        with:
          hugo-version: '0.141.0'
          extended: true

      - name: Build docs
        run: cd docs && hugo

      - name: Check links
        uses: lycheeverse/lychee-action@v1
        with:
          args: --verbose --no-progress 'docs/public/**/*.html'
          fail: true
```

## Testing Strategy

### JavaScript Testing

**Test Framework**: Jest

**File**: `javascript-app/package.json`

```json
{
  "scripts": {
    "test": "jest",
    "test:watch": "jest --watch",
    "test:coverage": "jest --coverage",
    "lint": "eslint app.js",
    "format": "prettier --write app.js"
  },
  "devDependencies": {
    "@jest/globals": "^29.5.0",
    "eslint": "^8.40.0",
    "jest": "^29.5.0",
    "prettier": "^2.8.8"
  }
}
```

**File**: `javascript-app/app.test.js`

```javascript
import { describe, test, expect } from '@jest/globals';
import {
  checkTargetPriceAlarm,
  checkPercentChangeAlarm,
  checkTimeframeAlarm
} from './app.js';

describe('Target Price Alarms', () => {
  test('triggers when price crosses from below', () => {
    const alarm = {
      targetPrice: 50000,
      direction: 'fromBelow',
      triggered: false
    };

    const result = checkTargetPriceAlarm(alarm, 50100, 49900);
    expect(result).toBe(true);
  });

  test('does not trigger when coming from above', () => {
    const alarm = {
      targetPrice: 50000,
      direction: 'fromBelow',
      triggered: false
    };

    const result = checkTargetPriceAlarm(alarm, 49900, 50100);
    expect(result).toBe(false);
  });
});

describe('Percent Change Alarms', () => {
  test('triggers on 10% drop from max', () => {
    const alarm = {
      percentage: 10,
      changeType: 'downFromMax',
      triggered: false
    };

    const result = checkPercentChangeAlarm(alarm, 54000, 60000, 40000);
    expect(result).toBe(true);
  });
});

describe('Timeframe Alarms', () => {
  test('triggers on 5% move in 30 minutes', () => {
    const alarm = {
      percentage: 5,
      timeValue: 30,
      timeUnit: 'minutes',
      direction: 'any',
      triggered: false
    };

    const priceHistory = [
      { price: 50000, timestamp: Date.now() - 30 * 60 * 1000 },
      { price: 50500, timestamp: Date.now() - 20 * 60 * 1000 },
      { price: 52500, timestamp: Date.now() }
    ];

    const result = checkTimeframeAlarm(alarm, 52500, priceHistory);
    expect(result).toBe(true);
  });
});
```

### Python Testing

**Test Framework**: pytest

**File**: `python-app/test_app.py`

```python
import pytest
from app import (
    check_target_alarm,
    check_percent_change_alarm,
    check_timeframe_alarm
)

class TestTargetAlarms:
    def test_trigger_from_below(self):
        alarm = {
            'targetPrice': 50000,
            'direction': 'fromBelow',
            'triggered': False
        }

        result = check_target_alarm(alarm, current=50100, previous=49900)
        assert result is True

    def test_no_trigger_from_above(self):
        alarm = {
            'targetPrice': 50000,
            'direction': 'fromBelow',
            'triggered': False
        }

        result = check_target_alarm(alarm, current=49900, previous=50100)
        assert result is False

class TestPercentChangeAlarms:
    def test_trigger_down_from_max(self):
        alarm = {
            'percentage': 10,
            'changeType': 'downFromMax',
            'triggered': False
        }

        result = check_percent_change_alarm(
            alarm,
            current=54000,
            max_price=60000,
            min_price=40000
        )
        assert result is True

class TestTimeframeAlarms:
    def test_trigger_5_percent_in_30_minutes(self):
        alarm = {
            'percentage': 5,
            'timeValue': 30,
            'timeUnit': 'minutes',
            'direction': 'any',
            'triggered': False
        }

        price_history = [
            {'price': 50000, 'timestamp': '2024-01-01T10:00:00Z'},
            {'price': 52500, 'timestamp': '2024-01-01T10:30:00Z'}
        ]

        result = check_timeframe_alarm(alarm, 52500, price_history)
        assert result is True
```

**File**: `python-app/pytest.ini`

```ini
[pytest]
testpaths = .
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts =
    --verbose
    --strict-markers
    --cov=.
    --cov-report=term-missing
    --cov-report=xml
```

## Code Quality Tools

### ESLint Configuration

**File**: `javascript-app/.eslintrc.json`

```json
{
  "env": {
    "browser": true,
    "es2021": true
  },
  "extends": "eslint:recommended",
  "parserOptions": {
    "ecmaVersion": 12,
    "sourceType": "module"
  },
  "rules": {
    "no-unused-vars": "warn",
    "no-console": "off",
    "indent": ["error", 2],
    "quotes": ["error", "single"],
    "semi": ["error", "always"]
  }
}
```

### Python Code Quality

**File**: `python-app/.flake8`

```ini
[flake8]
max-line-length = 100
exclude =
    .git,
    __pycache__,
    venv,
    env
ignore = E203, W503
```

**File**: `python-app/pyproject.toml`

```toml
[tool.black]
line-length = 100
target-version = ['py39', 'py310', 'py311']
include = '\.pyi?$'

[tool.mypy]
python_version = "3.9"
warn_return_any = true
warn_unused_configs = true
ignore_missing_imports = true
```

## Docker Configuration

### Dockerfile

**File**: `python-app/Dockerfile`

```dockerfile
# Multi-stage build for minimal image size
FROM python:3.11-slim as builder

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Copy dependencies from builder
COPY --from=builder /root/.local /root/.local

# Copy application
COPY app.py .
COPY templates/ templates/
COPY static/ static/
COPY data/ data/

# Make sure scripts are in PATH
ENV PATH=/root/.local/bin:$PATH

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:5000/health')"

EXPOSE 5000

CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "app:app", "--bind", "0.0.0.0:5000"]
```

### Docker Compose

**File**: `python-app/docker-compose.yml`

```yaml
version: '3.8'

services:
  crypto-alarm:
    build: .
    ports:
      - "5000:5000"
    volumes:
      - ./data:/app/data
    environment:
      - FLASK_ENV=production
      - LOG_LEVEL=INFO
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 30s
      timeout: 3s
      retries: 3
      start_period: 10s

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certs:/etc/nginx/certs:ro
    depends_on:
      - crypto-alarm
    restart: unless-stopped
```

## Documentation Publishing

### Hugo Build Configuration

**File**: `docs/config.toml` (production settings)

```toml
baseURL = 'https://crypto-alarm-docs.yourdomain.com/'
languageCode = 'en-us'
title = 'Crypto Price Alarm | Technical Documentation'
theme = 'hugo-theme-relearn'

[params]
themeVariant = 'relearn-dark'
disableSearch = false
disableNextPrev = false

[outputs]
home = ['HTML', 'RSS', 'JSON']

[[menu.main]]
name = 'GitHub Repo'
url = 'https://github.com/karmen87/Crypto_Alarm'
weight = 10
```

### GitHub Pages Deployment

The `deploy.yml` workflow automatically builds and deploys the Hugo site to GitHub Pages on every push to `main`.

**Enable GitHub Pages**:
1. Go to repository Settings → Pages
2. Source: Deploy from a branch
3. Branch: `gh-pages` / `root`
4. Save

**Custom Domain** (optional):
1. Add CNAME file: `docs/static/CNAME` with your domain
2. Configure DNS: `CNAME` record pointing to `username.github.io`

## Release Management

### Semantic Versioning

Version format: `MAJOR.MINOR.PATCH`

- **MAJOR**: Breaking changes (e.g., API changes)
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes

### Creating a Release

```bash
# Update version
git tag -a v1.2.0 -m "Release v1.2.0: Add WebSocket support"

# Push tag
git push origin v1.2.0

# GitHub Actions automatically:
# 1. Builds release artifacts
# 2. Creates Docker images with version tags
# 3. Publishes to GitHub Releases
```

### Changelog Generation

**File**: `.github/workflows/changelog.yml`

```yaml
name: Generate Changelog

on:
  release:
    types: [ published ]

jobs:
  changelog:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v3
        with:
          fetch-depth: 0

      - name: Generate changelog
        uses: orhun/git-cliff-action@v2
        with:
          config: cliff.toml
          args: --verbose
        env:
          OUTPUT: CHANGELOG.md

      - name: Commit changelog
        run: |
          git config user.name github-actions
          git config user.email github-actions@github.com
          git add CHANGELOG.md
          git commit -m "docs: update changelog for ${{ github.ref_name }}"
          git push
```

## Monitoring & Alerts

### GitHub Actions Notifications

**Slack Integration**:

```yaml
# Add to deploy.yml
- name: Notify Slack on failure
  if: failure()
  uses: slackapi/slack-github-action@v1
  with:
    webhook-url: ${{ secrets.SLACK_WEBHOOK_URL }}
    payload: |
      {
        "text": "❌ Deployment failed for ${{ github.repository }}",
        "blocks": [
          {
            "type": "section",
            "text": {
              "type": "mrkdwn",
              "text": "*Build Failed*\nRepository: ${{ github.repository }}\nBranch: ${{ github.ref }}\nCommit: ${{ github.sha }}"
            }
          }
        ]
      }
```

### Deployment Status Badge

Add to README.md:

```markdown
![Build Status](https://github.com/karmen87/Crypto_Alarm/workflows/Test%20%26%20Lint/badge.svg)
![Deploy Status](https://github.com/karmen87/Crypto_Alarm/workflows/Build%20%26%20Deploy/badge.svg)
[![codecov](https://codecov.io/gh/karmen87/Crypto_Alarm/branch/main/graph/badge.svg)](https://codecov.io/gh/karmen87/Crypto_Alarm)
```

## Local Development Workflow

### Pre-Commit Hooks

**File**: `.pre-commit-config.yaml`

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files

  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
        files: python-app/.*\.py$

  - repo: https://github.com/pre-commit/mirrors-eslint
    rev: v8.40.0
    hooks:
      - id: eslint
        files: javascript-app/.*\.js$
        additional_dependencies:
          - eslint@8.40.0
```

**Setup**:
```bash
pip install pre-commit
pre-commit install
```

### Local Testing Commands

**JavaScript**:
```bash
cd javascript-app
npm install
npm run lint
npm test
npm run format
```

**Python**:
```bash
cd python-app
pip install -r requirements.txt
pip install pytest pytest-cov flake8 black mypy
flake8 app.py
black app.py
mypy app.py
pytest --cov
```

**Documentation**:
```bash
cd docs
hugo server --buildDrafts
# Visit http://localhost:1313
```

## Performance Optimization

### Build Caching

GitHub Actions caches:
- npm packages (`node_modules`)
- pip packages
- Docker layers
- Hugo resources

**Benefits**:
- Faster builds (30s → 10s for cached runs)
- Reduced bandwidth
- Lower GitHub Actions minutes usage

### Parallel Jobs

Jobs run in parallel when independent:
```yaml
jobs:
  test-javascript:
    # Runs concurrently with test-python
  test-python:
    # Runs concurrently with test-javascript
  security-scan:
    # Runs concurrently with both tests
```

**Total CI time**: ~3-5 minutes (vs 10+ if sequential)

## Security Best Practices

### Secrets Management

**Never commit**:
- API keys
- Passwords
- Private keys
- Tokens

**Use GitHub Secrets**:
```yaml
env:
  API_KEY: ${{ secrets.COINGECKO_API_KEY }}
```

### Dependency Scanning

**Dependabot configuration**:

**File**: `.github/dependabot.yml`

```yaml
version: 2
updates:
  - package-ecosystem: "npm"
    directory: "/javascript-app"
    schedule:
      interval: "weekly"

  - package-ecosystem: "pip"
    directory: "/python-app"
    schedule:
      interval: "weekly"

  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
```

## Cost Optimization

### GitHub Actions Minutes

**Free tier**: 2,000 minutes/month (public repos: unlimited)

**Optimization strategies**:
1. Use caching extensively
2. Run expensive jobs only on main branch
3. Skip redundant builds (e.g., docs-only changes)

```yaml
on:
  push:
    branches: [ main ]
    paths-ignore:
      - 'docs/**'
      - '**.md'
```

## Troubleshooting CI/CD

### Common Issues

**Build fails on dependency install**:
```bash
# Solution: Clear cache
# In workflow: Add cache-dependency-path or change cache key
```

**Docker image too large**:
```dockerfile
# Solution: Multi-stage builds + slim base images
FROM python:3.11-slim  # Not python:3.11 (full)
```

**Hugo build fails with theme error**:
```yaml
# Solution: Checkout with submodules
- uses: actions/checkout@v3
  with:
    submodules: recursive
```

## Next Steps

- Implement workflows in your repository
- Customize deployment targets
- Add monitoring and alerting
- Explore **Implementations** for application details
- See **API Integration** for external service documentation

---

**This CI/CD pipeline demonstrates professional DevOps practices including automated testing, security scanning, containerization, and documentation-as-code deployment.**
