# SDK Mapper Quick Reference

## Quick Start

```bash
# Run the mapper
export GITHUB_TOKEN="your-token-here"
python scripts/comprehensive_branch_aware_mapper.py
```

## Key Functions Overview

### Main Entry Points

| Function | Purpose | When Called |
|----------|---------|-------------|
| `run_complete_analysis()` | Main orchestrator | Script entry point |
| `build_sdk_tag_database()` | Collect SDK tags & versions | Phase 1 |
| `analyze_release_branches()` | Find PRs on branches | Phase 2 |
| `map_runtime_releases()` | Match runtime to SDK | Phase 3 |
| `calculate_pr_counts()` | Assign PRs to releases | Phase 4 |
| `save_results()` | Generate output files | Phase 5 |

### Core Algorithms

```python
# 1. Find SDK version for a runtime release
def _find_best_sdk_match(runtime_packages, runtime_tag):
    # Returns: SDK tag name (e.g., "stable2503-4")
    
# 2. Build PR to releases mapping (critical!)
def _build_pr_to_releases_mapping():
    # Returns: {pr_number: [releases]}
    # Ensures each PR only in first release
    
# 3. Extract backport information
def _extract_backport_info(title, body):
    # Returns: Original PR number or None
    
# 4. Get exact branch point (NEW!)
def _get_branch_point(branch):
    # Returns: Exact commit SHA where branch forked from master
    # Uses GitHub compare API for precision
```

## Data Flow Diagram

```
GitHub API → SDK Tags → Package Versions → Runtime Matching
     ↓           ↓                              ↓
   PR Data → Branch PRs → PR Assignment → Output Files
     ↓           ↓              ↓
Backports → Relationships → Website Display
```

## Key Data Structures

### Input Processing
```python
# Raw SDK tag data
sdk_tags = {
    "stable2503": {
        "commit": "...",
        "date": "2025-03-01T...",
        "branch": "stable2503",
        "package_versions": {...}
    }
}

# Branch PR collections
branch_info = {
    "stable2503": {
        "prs": {6144, 6145, ...},  # Set of PR numbers
        "created_date": "...",
        "tags": [...]
    }
}
```

### Output Format
```python
# Website-ready data
{
    "runtime_sdk_versions": {
        "v1.6.0": {
            "sdk_version": "stable2503-6",
            "release_date": "...",
            "total_prs": 325
        }
    },
    "pr_to_releases": {
        "6144": [{
            "runtime_version": "1.6.0",
            "sdk_version": "stable2503-6",
            "sdk_branch": "stable2503"
        }]
    }
}
```

## Common Modifications

### Add a New Package to Track

```python
# In __init__:
self.tracked_packages = [
    'polkadot-primitives',
    'sp-runtime', 
    'frame-support',
    'your-new-package'  # Add here
]

# In _get_package_versions, add path:
package_paths = {
    'your-new-package': 'path/to/Cargo.toml'
}
```

### Change Backport Detection Patterns

```python
# In _extract_backport_info:
patterns = [
    r'\[stable\d+\]\s*(?:backport\s*)?#(\d+)',
    r'your-new-pattern-here',  # Add new pattern
]
```

### Adjust PR Assignment Logic

```python
# In _build_pr_to_releases_mapping:
# Current: First appearance only
# To change: Modify the assigned_prs logic
```

## Debugging Guide

### Common Issues

1. **Missing PRs**
   - Check: Branch date ranges in `_get_master_prs_for_branch`
   - Verify: PR search queries in `_find_branch_prs`

2. **Wrong SDK Version**
   - Check: Package versions in runtime's Cargo.lock
   - Verify: SDK tag has those versions
   - Debug: `_find_best_sdk_match` scoring

3. **Backports Not Linked**
   - Check: PR title/body patterns
   - Verify: `_extract_backport_info` regex
   - Test: Backport PR format matches patterns

### Debug Output

```python
# Enable debug logging
print(f"Debug: Found {len(prs)} PRs for {branch}")
print(f"Debug: Matched {runtime_tag} to {sdk_tag}")
```

### Verification Commands

```bash
# Check a specific PR
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/paritytech/polkadot-sdk/pulls/9405

# List tags on a branch
git ls-remote --tags origin | grep stable2503

# Check package versions
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/polkadot-fellows/runtimes/contents/Cargo.lock?ref=v1.6.0
```

## Performance Tips

1. **API Rate Limits**
   - Use GitHub token (5000 requests/hour vs 60)
   - Check `X-RateLimit-Remaining` header
   - Implement caching for repeated runs

2. **Optimization Opportunities**
   - Parallelize API calls (careful with rate limits)
   - Cache package version lookups
   - Skip unchanged branches in incremental mode

3. **Memory Usage**
   - PR cache grows with history
   - Consider pruning old branches
   - Use generators for large datasets

## Testing

### Unit Test Structure
```python
def test_backport_extraction():
    assert _extract_backport_info("[stable2503] #9195", "") == 9195
    assert _extract_backport_info("Normal PR", "") == None

def test_pr_assignment():
    # Ensure PR only assigned once
    mapping = _build_pr_to_releases_mapping()
    all_prs = []
    for releases in mapping.values():
        all_prs.extend(releases)
    assert len(all_prs) == len(set(all_prs))
```

### Integration Test
```bash
# Run on small date range
python scripts/comprehensive_branch_aware_mapper.py --limit 2
# Verify output files exist and are valid JSON
```

## Maintenance Checklist

- [ ] Monitor GitHub API changes
- [ ] Update package paths for repository restructures  
- [ ] Verify backport patterns still match
- [ ] Check performance on growing dataset
- [ ] Validate output against manual checks
- [ ] Update documentation for changes

## Quick Command Reference

```bash
# Full run
python scripts/comprehensive_branch_aware_mapper.py

# Check output
jq '.statistics' docs/data/sdk-mappings/sdk_pr_mappings.json

# Verify specific runtime
jq '.runtime_sdk_versions["v1.6.0"]' docs/data/sdk-mappings/sdk_pr_mappings.json

# Count total PRs tracked
jq '.pr_details | length' docs/data/sdk-mappings/sdk_pr_mappings.json

# Find backports
jq '.backport_mapping | length' docs/data/sdk-mappings/sdk_pr_mappings.json
```