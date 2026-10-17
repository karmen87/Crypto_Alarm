---
title: "DevOps"
weight: 5
chapter: true
---

# DevOps & Automation

## Overview

This section documents the DevOps practices behind the Crypto Price Alarm project: continuous integration, containerization, pinned dependencies and documentation-as-code deployment with GitHub Actions.

## Why DevOps Matters

Even a small project benefits from automation in a few key areas:

1. **Continuous Integration**: the same checks run locally and on every push
2. **Quality Assurance**: linting, formatting and strict type checking
3. **Reproducible Builds**: pinned dependencies and a Docker image
4. **Documentation**: this site is built and published automatically
5. **Monitoring**: a health endpoint used by the container healthcheck

## This Project's DevOps Stack

### CI/CD Platform
- **GitHub Actions**: free for public repos

### Testing & Quality
- **unittest**: the test suite (`python -m unittest discover -s tests`)
- **ruff**: linting (`ruff check .`) and formatting (`ruff format --check .`)
- **mypy**: strict type checking of the `crypto_alarm` package
- **Python matrix**: CI runs on Python 3.10 and 3.12

### Containerization
- **Docker**: `python:3.12-slim` image, non-root user, health check
- **Docker Compose**: one command to run it, with a named volume for data
- **gunicorn**: one worker, 100 threads

### Dependencies
- **`pyproject.toml`**: version ranges
- **`requirements.lock`**: exact versions used by the Docker build

### Documentation
- **Hugo**: static site generator
- **Relearn Theme**: documentation theme (vendored in `docs/themes/`)
- **GitHub Pages**: free hosting, deployed by GitHub Actions

## Key Workflows

### 1. CI (on every push and pull request)
- Install the package with dev extras on Python 3.10 and 3.12
- `ruff check`, `ruff format --check`, `mypy`
- Run the unit tests

### 2. Docs (when `docs/` changes on `main`)
- Build the Hugo site with `hugo --minify`
- Publish it to GitHub Pages

## Pipeline Benefits

### For Developers
- Fast feedback on code changes
- The exact same commands run locally (see [CONTRIBUTING.md](https://github.com/karmen87/Crypto_Alarm/blob/main/CONTRIBUTING.md))
- Strict typing catches mistakes early

### For Users
- A reproducible Docker image with a health check
- Up-to-date documentation

### For Project Maintainers
- Reduced manual work
- Consistent builds
- An audit trail of every change

## Quick Start: Deploy Your Documentation

{{% notice tip "5-Minute Setup" %}}
Get your documentation auto-deployed to GitHub Pages:

1. **Push the workflow**: commit `.github/workflows/docs.yml` to your repository
2. **Enable Pages**: GitHub Settings → Pages → Source: "GitHub Actions"
3. **Push to main**: any change under `docs/` triggers the workflow
4. **Visit your site**: `https://<username>.github.io/<repository>/`

Full step-by-step guide in **GitHub Actions Setup** →
{{% /notice %}}

## Documentation Pages

Explore detailed implementation guides:

### [GitHub Actions Setup]({{% relref "/devops/github-actions-setup" %}})
**Quick deployment guide** for the documentation pipeline:
- Step-by-step GitHub Pages setup
- Workflow architecture and job details
- Troubleshooting common issues
- Custom domain configuration

### [CI/CD Pipeline]({{% relref "/devops/cicd-pipeline" %}})
**Complete reference** for the project's CI and packaging:
- The CI workflow, line by line
- Local checks that mirror CI
- Docker image and Compose configuration
- Dependency pinning
- Health checks and what is not automated yet

---

**This setup keeps a small project reproducible: one command to check it, one to run it, and documentation that deploys itself.**
