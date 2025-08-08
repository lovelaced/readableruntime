# Comprehensive SDK Mapper Documentation

## Overview

The `comprehensive_branch_aware_mapper.py` script is the core component that tracks how Polkadot SDK changes flow into runtime releases. It understands the complex branching model used by the SDK repository and ensures accurate tracking of pull requests across releases.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Core Data Structures](#core-data-structures)
3. [Key Algorithms](#key-algorithms)
4. [Output Files](#output-files)
5. [Website Integration](#website-integration)
6. [Workflow Visualization](#workflow-visualization)

## Architecture Overview

The mapper solves several complex problems:
- **Branch-based releases**: SDK uses stable branches (stable2503, stable2412, etc.)
- **PR attribution**: PRs can come from master or be directly targeted to branches
- **Backport tracking**: Changes can be backported to older branches
- **One-time counting**: Each PR should only be counted in its first runtime release

## Core Data Structures

### 1. SDK Tags Dictionary (`sdk_tags`)
```python
{
    "stable2503": {
        "commit": "abc123...",
        "date": "2025-03-01T10:00:00Z",
        "branch": "stable2503",
        "package_versions": {
            "polkadot-primitives": "18.0.0",
            "sp-runtime": "41.0.0",
            "frame-support": "40.0.0"
        }
    }
}
```
**Purpose**: Central repository of all SDK release tags with their metadata

### 2. Package to Tags Mapping (`package_to_tags`)
```python
{
    "polkadot-primitives:18.0.0": ["stable2503", "stable2503-1"],
    "sp-runtime:41.0.0": ["stable2503", "stable2503-1"]
}
```
**Purpose**: Reverse index for finding SDK tags by package version

### 3. Branch Information (`branch_info`)
```python
{
    "stable2503": {
        "created_date": "2025-03-01T00:00:00Z",
        "base_commit": "xyz789...",
        "tags": ["stable2503", "stable2503-1", ...],
        "prs": {6144, 6145, 6146, ...}  # Set of PR numbers
    }
}
```
**Purpose**: Comprehensive information about each release branch

### 4. PR Cache (`pr_cache`)
```python
{
    9405: {
        "number": "9405",
        "title": "[stable2506] Backport #9195",
        "author": "paritytech-release-backport-bot[bot]",
        "merged_at": "2025-07-31T13:31:40Z",
        "labels": ["A3-backport"],
        "url": "https://github.com/paritytech/polkadot-sdk/pull/9405",
        "branch": "stable2506",
        "is_direct": True,
        "is_backport": True,
        "original_pr": 9195
    }
}
```
**Purpose**: Cached PR details to minimize API calls

### 5. Backport Mappings
```python
# backport_mapping: backport PR -> original PR
{9405: 9195, 9370: 9355, ...}

# original_to_backports: original PR -> list of backports
{9195: [9405], 9355: [9370], ...}
```
**Purpose**: Bidirectional tracking of backport relationships

## Key Algorithms

### 1. Building SDK Tag Database

```python
def build_sdk_tag_database(self):
    # 1. Fetch all SDK tags from GitHub
    # 2. Filter for stable tags (polkadot-stable*)
    # 3. For each tag:
    #    - Get commit info
    #    - Extract package versions from Cargo.toml
    #    - Determine branch (stable2503, etc.)
    #    - Update reverse mappings
```

**Key Decisions**:
- Tracks only stable releases
- Monitors specific core packages
- Builds multiple indices for efficient lookups

### 2. Analyzing Release Branches

```python
def analyze_release_branches(self):
    # For each branch:
    # 1. Find exact branch point using GitHub compare API
    # 2. Find direct PRs (targeted to branch)
    # 3. Find master PRs (merged before branch point)
    # 4. Identify backports
```

**Branch Point Detection**:
```python
def _get_branch_point(self, branch: str):
    # Use GitHub's compare API to find merge-base
    compare_url = f"https://api.github.com/repos/paritytech/polkadot-sdk/compare/master...{branch}"
    # Returns exact commit SHA and date where branch diverged
```

**PR Discovery Strategy**:
- **Direct PRs**: `base:stable2503` or `[stable2503]` in title
- **Master PRs**: All PRs merged to master before exact branch point
- **Backport Detection**: Pattern matching in titles/bodies

### 3. Mapping Runtime to SDK Versions

```python
def _find_best_sdk_match(self, runtime_pkgs, runtime_tag):
    # 1. Find all SDK tags containing runtime's package versions
    # 2. Score candidates by number of matching packages
    # 3. For ties, use chronological proximity
    # 4. Ensure SDK predates runtime release
```

**Matching Priority**:
1. Package version matches (highest priority)
2. Chronological proximity (tie-breaker)
3. Lexicographical ordering (fallback)

### 4. PR Assignment Algorithm (Critical)

```python
def _build_pr_to_releases_mapping(self):
    # Sort runtime releases by SDK date (oldest first)
    sorted_releases = sorted(runtime_mappings.items(), 
                           key=lambda x: x[1]['sdk_date'])
    
    assigned_prs = set()
    
    for runtime_tag, info in sorted_releases:
        for pr_num in branch_prs:
            if pr_num not in assigned_prs:
                if pr_merged_before_sdk_tag:
                    assign_pr_to_release(pr_num, runtime_tag)
                    assigned_prs.add(pr_num)
```

**Key Innovation**: Each PR is assigned only to its first appearance in a runtime release

## Output Files

### 1. branch_aware_mappings.json
Complete data dump including:
- All SDK tags and metadata
- Branch information and PR counts
- Runtime to SDK mappings
- Comprehensive statistics

### 2. sdk_pr_mappings.json
Website-optimized file containing:
- Runtime SDK versions summary
- PR details with full metadata
- PR to releases mapping
- Backport relationships

## Website Integration

### Loading Data
```javascript
// On page load
async function loadSDKMappings() {
    const response = await fetch('data/sdk-mappings/sdk_pr_mappings.json');
    sdkMappings = await response.json();
}
```

### Displaying PRs for a Release
```javascript
// When viewing runtime v1.6.1
const sdkInfo = sdkMappings.runtime_sdk_versions['v1.6.1'];
// Shows: SDK stable2503-7-rc2, 27 PRs

// Find all PRs for this release
for (const [prNum, releases] of Object.entries(sdkMappings.pr_to_releases)) {
    if (releases.find(r => r.runtime_version === '1.6.1')) {
        // Display this PR
    }
}
```

### PR Search Features
```javascript
// Search by number
const prReleases = sdkMappings.pr_to_releases[prNumber];
const prDetails = sdkMappings.pr_details[prNumber];

// Handle backports
if (sdkMappings.backport_mapping[prNumber]) {
    // Show "Backport of: #XXXX"
}

// Search by title
const results = Object.entries(sdkMappings.pr_details)
    .filter(([_, details]) => details.title.includes(searchQuery));
```

## Workflow Visualization

```
┌─────────────────────────────────────────────────────────────┐
│                    GitHub API Data Collection                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  SDK Tags          PR Search          Runtime Releases      │
│     ↓                  ↓                     ↓              │
│  ┌─────┐          ┌─────────┐         ┌───────────┐        │
│  │Tags │          │Direct   │         │Cargo.lock │        │
│  │Info │          │Master   │         │Versions   │        │
│  │     │          │Backports│         │           │        │
│  └──┬──┘          └────┬────┘         └─────┬─────┘        │
│     └─────────┬────────┴──────────┬─────────┘              │
│               ↓                    ↓                        │
│        Data Processing      PR Assignment                   │
│               ↓                    ↓                        │
│     ┌─────────────────────────────────────┐                │
│     │  • Map packages to SDK versions     │                │
│     │  • Assign PRs to first release only │                │
│     │  • Track backport relationships     │                │
│     └─────────────────────────────────────┘                │
│                         ↓                                   │
│                  Output Generation                          │
│     ┌────────────────────┴────────────────────┐            │
│     ↓                                         ↓            │
│  branch_aware_mappings.json         sdk_pr_mappings.json   │
│  (Complete data archive)            (Website optimized)    │
└─────────────────────────────────────────────────────────────┘

                            ↓

┌─────────────────────────────────────────────────────────────┐
│                      Website Display                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Release View          PR Search           PR Details       │
│  ┌──────────┐       ┌──────────┐       ┌──────────┐       │
│  │v1.6.1    │       │Search:   │       │PR #9405  │       │
│  │SDK: 2503 │  -->  │"xcm"     │  -->  │Backport  │       │
│  │27 PRs    │       │5 results │       │of #9195  │       │
│  └──────────┘       └──────────┘       └──────────┘       │
└─────────────────────────────────────────────────────────────┘
```

## Key Features

1. **Comprehensive Branch Tracking**: Understands SDK's branch-based release model
2. **Accurate PR Attribution**: Tracks direct, master, and backport PRs
3. **One-Time Counting**: Ensures PRs appear in only their first runtime release
4. **Backport Awareness**: Maps backports to original PRs bidirectionally
5. **Efficient Search**: Supports PR lookup by number or title
6. **Historical Accuracy**: Preserves complete change history

## Performance Considerations

- **API Rate Limits**: Implements rate limit handling and retries
- **Caching**: Caches PR details to minimize API calls
- **Batch Processing**: Processes all data before generating output
- **Incremental Updates**: Can be run periodically to update mappings

## Error Handling

- Graceful handling of API failures
- Validation of package versions
- Chronological consistency checks
- Comprehensive logging for debugging

This mapper provides the foundation for understanding how SDK changes propagate through the release process into runtime releases, enabling accurate tracking and attribution of changes.