---
title: "GitHub Actions Setup"
weight: 2
---

# GitHub Actions Setup Guide

## Overview

This guide covers the workflow that builds this documentation with Hugo and publishes it to GitHub Pages. The application's own checks are in a separate workflow, described in [CI/CD Pipeline]({{% relref "/devops/cicd-pipeline" %}}).

## Workflow Architecture

```
Push to main (docs/ changed)  or  manual run
              ↓
      ┌──────────────┐
      │  build       │  Hugo 0.141.0 extended
      │  hugo        │  → docs/public
      │  --minify    │  → upload Pages artifact
      └──────┬───────┘
             ↓
      ┌──────────────┐
      │  deploy      │  actions/deploy-pages
      │  GitHub Pages│  → https://<user>.github.io/<repo>/
      └──────────────┘
```

## Workflow File

**Location**: `.github/workflows/docs.yml`

**Triggers**:
- A push to `main` that changes anything under `docs/` or the workflow file itself
- A manual run (`workflow_dispatch`)

## Two Pipeline Jobs

### Job 1: Build Hugo Documentation

```yaml
build:
  name: Build Hugo documentation
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4

    - uses: peaceiris/actions-hugo@v3
      with:
        hugo-version: "0.141.0"
        extended: true

    - name: Build site
      working-directory: docs
      run: hugo --minify

    - uses: actions/upload-pages-artifact@v3
      with:
        path: ./docs/public
```

**What it does**:
1. Checks out the repository (the theme is vendored in `docs/themes/`, so no submodules are needed)
2. Installs Hugo, pinned to 0.141.0 extended (the Relearn theme needs the extended build)
3. Builds the site into `docs/public/`
4. Uploads it as a Pages artifact

### Job 2: Deploy to GitHub Pages

```yaml
deploy:
  name: Deploy to GitHub Pages
  runs-on: ubuntu-latest
  needs: build
  environment:
    name: github-pages
    url: ${{ steps.deployment.outputs.page_url }}
  steps:
    - id: deployment
      uses: actions/deploy-pages@v4
```

It only runs when the build succeeds and publishes the artifact. The live URL appears on the workflow run and the `github-pages` environment.

## Enabling GitHub Pages

{{% notice warning "Required Configuration" %}}
GitHub Pages must be set to deploy from **GitHub Actions**. Without this, the deploy job fails with a permissions or "Pages not enabled" error.
{{% /notice %}}

### Step-by-Step Setup

1. Open your repository on GitHub
2. Go to **Settings → Pages**
3. Under **Build and deployment → Source**, choose **GitHub Actions**
4. Push a change under `docs/` to `main` (or run the workflow manually from the **Actions** tab)
5. Wait for both jobs to turn green

### Your Documentation URL

```
https://<username>.github.io/<repository>/
```

For this project: `https://karmen87.github.io/Crypto_Alarm/`. The `baseURL` in `docs/hugo.toml` must match it, or CSS and links will break.

## Workflow Permissions

```yaml
permissions:
  contents: read
  pages: write
  id-token: write
```

- `contents: read`: check out the code
- `pages: write`: publish to Pages
- `id-token: write`: lets `deploy-pages` verify the deployment source

## Concurrency Control

```yaml
concurrency:
  group: pages
  cancel-in-progress: false
```

Only one Pages deployment runs at a time. A second push waits instead of cancelling a deployment that is already in flight.

## Manual Triggering

1. Open the **Actions** tab
2. Select the **Docs** workflow
3. Click **Run workflow** and choose `main`

Useful after changing the Pages settings, or to rebuild without a docs change.

## Monitoring Workflow Runs

### Viewing Logs

1. **Actions** tab → select the run
2. Open the `build` or `deploy` job
3. Expand a step to read its output

### Common Log Sections

- **Setup Hugo**: shows the Hugo version that was installed
- **Build site**: Hugo's page and build statistics; warnings about missing shortcodes or references appear here
- **Upload artifact**: size of the generated site

## Troubleshooting

### Workflow Does Not Start

**Cause**: the push did not touch `docs/` or the workflow file.

**Solution**: change a file under `docs/`, or run the workflow manually.

### Workflow Fails on Build Job

{{% notice info "Hugo build errors" %}}
Reproduce locally with the same version:

```bash
cd docs
hugo --minify
```

Typical causes:
- A shortcode that is not closed (a `notice` block without its closing tag)
- A `relref` pointing at a page that does not exist
- Front matter YAML errors (bad indentation or quoting)
{{% /notice %}}

### Site Loads Without Styling

**Cause**: `baseURL` in `docs/hugo.toml` does not match the Pages URL.

**Solution**: set it to `https://<username>.github.io/<repository>/` (with the trailing slash).

### Workflow Fails on Deploy Job

**Cause**: Pages source is not set to **GitHub Actions**, or the workflow lacks `pages: write` / `id-token: write`.

**Solution**: fix the setting under *Enabling GitHub Pages* and re-run the workflow.

## Workflow Performance

### Typical Run Times

| Job | Typical time |
|-----|--------------|
| build | about 30-60 seconds (a tiny site, most time goes to downloading Hugo) |
| deploy | about 10-30 seconds |

### Optimization Tips

The workflow already skips runs that don't touch the documentation, through its `paths` filter.

## Cost & Usage

GitHub Actions and Pages are free for public repositories. The docs workflow is short and only runs when documentation changes.

## Adding Status Badge

```markdown
![Docs](https://github.com/karmen87/Crypto_Alarm/actions/workflows/docs.yml/badge.svg)
```

## Security Considerations

### Secrets Management

The workflow needs **no secrets**: it uses the built-in short-lived `GITHUB_TOKEN` and OIDC token only.

### Dependency Security

- Actions are pinned to major versions (`@v4`, `@v3`)
- Hugo is pinned to an exact version
- The theme is vendored and changes only through reviewed commits

## Custom Domain (Optional)

1. In **Settings → Pages**, enter your domain under **Custom domain**
2. Create a `CNAME` DNS record pointing to `<username>.github.io`
3. Update `baseURL` in `docs/hugo.toml` to your domain
4. Enable **Enforce HTTPS** once the certificate is issued

## Next Steps

- See **CI/CD Pipeline** for the application's own CI workflow and Docker setup
