# How to Update SDK Mappings - Step-by-Step Guide

## Quick Update (Recommended)

```bash
# 1. Set your GitHub token
export GITHUB_TOKEN=your_github_token_here

# 2. Run the automated updater
python scripts/automated_sdk_updater.py

# That's it! The system will:
# - Detect new runtime releases
# - Update SDK mappings automatically  
# - Generate all output files
```

## What Gets Updated

When you run the updater, it:

1. **Fetches latest runtime releases** from `polkadot-fellows/runtimes`
2. **Analyzes Cargo.lock files** to extract exact SDK versions
3. **Maps SDK commits to branches** (e.g., stable2412, stable2503)
4. **Fetches all PRs** merged into those SDK versions
5. **Generates comprehensive mappings** with full PR details
6. **Updates the website data** for SDK PR search

## Verifying the Update

```bash
# Check statistics
python test_sdk_search.py

# Test specific PR search
python test_sdk_search.py 5546

# Test title search
python scripts/test_pr_search.py "approval slash"
```

## Current vs New System Comparison

### OLD System (Manual)
```bash
# Had to run multiple scripts
python extract_sdk_pr_mappings.py       # Basic changelog scraping
python enhanced_sdk_pr_mapper.py        # Version tracking
python scripts/populate_sdk_mappings.py # Merge results

# Problems:
# - Required multiple manual steps
# - Data could get out of sync
# - No automation
```

### NEW System (Automated)
```bash
# Single command does everything
python scripts/automated_sdk_updater.py

# Benefits:
# - One command updates everything
# - Fully automated via GitHub Actions
# - Robust branch-aware tracking
# - Complete PR coverage
```

## Files You'll See Updated

After running the updater, these files will be updated:

```
docs/data/sdk-mappings/
├── sdk_pr_mappings.json          # Main mappings file
├── sdk_branch_data.json          # Branch tracking data  
├── .update_state.json            # Update tracking
├── enhanced_sdk_mappings.json    # Detailed mappings
└── prs/                          # Individual PR files
    ├── 5546.json
    ├── 6827.json
    └── ...
```

## Example: What Changed

### Before (Old PR File Format)
```json
{
  "pr_details": {
    "number": "5546",
    "title": "Transfer Polkadot-native assets to Ethereum"
  },
  "runtime_releases": [...]
}
```

### After (New PR File Format) 
```json
{
  "pr_number": "5546",
  "pr_details": {
    "number": "5546", 
    "title": "Transfer Polkadot-native assets to Ethereum",
    "author": "yrong",
    "merged_at": "2024-09-13T13:01:29Z",
    "labels": ["T15-bridges"],
    "url": "https://github.com/paritytech/polkadot-sdk/pull/5546"
  },
  "runtime_releases": [{
    "runtime_version": "1.4.0",
    "sdk_version": "stable2409", 
    "sdk_commit": "abc123...",
    "included_via": "sdk_version_bump"
  }]
}
```

## Automation Setup

The system runs automatically via GitHub Actions:

```yaml
# .github/workflows/update-sdk-mappings.yml
# Runs daily at 2 AM UTC
# Manual trigger available in GitHub UI
```

## Manual Override Options

```bash
# Force complete regeneration
python scripts/automated_sdk_updater.py --force

# Update only specific components
python scripts/populate_sdk_mappings.py        # Just mappings
python scripts/sdk_branch_tracker.py           # Just branch data

# Query current state
python scripts/sdk_version_query.py runtime v1.6.0
```

## Transition from Old System

If you were using the old system:

1. **Old files are archived** in `archived/` directory
2. **New system is active** - uses only enhanced tracking
3. **All data preserved** - no PRs lost in transition
4. **Better coverage** - finds more PRs via version tracking

You don't need to do anything special for the transition - just run the new updater!