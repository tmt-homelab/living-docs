# TMT Homelab Documentation

Automated documentation site powered by MkDocs and Corvus operational data.

## Overview

This repository contains the living documentation for the TMT Homelab infrastructure. The site is automatically synchronized with operational data from Corvus and deployed to GitHub Pages.

## Pipeline

The automated build and deploy pipeline works as follows:

### Triggers
- **Scheduled**: Every 6 hours (heartbeat sync)
- **Event-driven**: Repository dispatch events for `change.completed` and `incident.resolved`
- **Manual**: Can be triggered via GitHub Actions UI

### Process
1. **Sync**: Fetches latest data from Corvus (services, incidents, change windows)
2. **Generate**: Updates documentation pages with fresh operational data
3. **Build**: Compiles MkDocs site with material theme
4. **Deploy**: Publishes to GitHub Pages

### Deployment
- **Target**: GitHub Pages (gh-pages branch)
- **Runner**: Self-hosted (dockp04)
- **URL**: `https://tmt-homelab.github.io/living-docs/`

## Setup Instructions

### First-Time Setup

1. **Enable GitHub Pages**:
   - Go to repository Settings → Pages
   - Source: Deploy from a branch
   - Branch: gh-pages
   - Folder: / (root)

2. **Configure Secrets**:
   - `CORVUS_API_KEY`: API key for Corvus authentication
   - (Optional) `CORVUS_URL`: Corvus instance URL (defaults to `http://localhost:9420`)

3. **Verify Workflow Permissions**:
   - Settings → Actions → General
   - Workflow permissions: "Read and write permissions"
   - Enable "Allow GitHub Actions to create and approve pull requests"

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Serve locally
mkdocs serve

# Build for production
mkdocs build --site-dir site
```

## Repository Structure

```
├── .github/workflows/
│   └── sync-docs.yml       # Automated sync and deploy pipeline
├── docs/                   # Documentation source files
│   ├── getting-started/
│   ├── governance/
│   ├── infrastructure/
│   ├── services/
│   ├── operations/
│   └── ...
├── scripts/
│   ├── fetch_and_sync.py   # Corvus data fetcher
│   └── sync_corvus.py      # Documentation generator
├── mkdocs.yml              # MkDocs configuration
└── requirements.txt        # Python dependencies
```

## Manual Sync

To manually trigger a sync:
1. Go to Actions → "Sync Documentation"
2. Click "Run workflow"
3. Select branch and click "Run workflow"

## Monitoring

Check the [Actions tab](../../actions) to monitor:
- Sync job status
- Build logs
- Deployment status

## Troubleshooting

### Build Fails
- Check MkDocs configuration syntax
- Verify all nav paths in `mkdocs.yml` exist
- Run `mkdocs build --strict` locally to catch errors

### Sync Fails
- Verify `CORVUS_API_KEY` secret is set
- Check Corvus API endpoint accessibility from dockp04
- Review workflow logs for API errors

### Deployment Fails
- Ensure GitHub Pages is enabled in repository settings
- Verify workflow permissions allow writes
- Check that gh-pages branch exists

## Contributing

To add new documentation:
1. Create markdown files in the appropriate `docs/` subdirectory
2. Update `mkdocs.yml` navigation
3. Open a PR for review

**Note**: Operational data (services, incidents, etc.) is automatically managed by the sync pipeline and should not be edited manually.
