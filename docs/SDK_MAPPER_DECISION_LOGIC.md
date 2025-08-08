# SDK Mapper Decision Logic

This document explains the key decisions and logic behind the comprehensive SDK mapper, including why certain approaches were chosen and what edge cases are handled.

## Core Design Decisions

### 1. Why Track Specific Packages?

The mapper tracks three specific packages:
- `polkadot-primitives`
- `sp-runtime`
- `frame-support`

**Rationale:**
- These are core dependencies that change with SDK versions
- They provide reliable version indicators
- Tracking all packages would be computationally expensive and unnecessary
- These packages have consistent versioning patterns

### 2. Branch-Based PR Discovery

**Problem:** PRs can enter a release branch through multiple paths:
1. Direct PRs targeted to the branch
2. PRs from master included when branch was cut
3. Backports from newer branches

**Solution Architecture:**
```
Branch Timeline:
master: ──●──●──●──●──●──●──●──●──●──●──●──→
           │        │        │
stable2409:└────●───┼────●───┼────●
                    │        │
stable2412:         └────●───┼────●
                             │
stable2503:                  └────●────●
```

**Decision Logic:**
- For stable2412, include:
  - All PRs directly to stable2412
  - Master PRs between stable2412 and stable2503 creation
  - Identified backports

### 3. PR Assignment: "First Appearance Only" Rule

**Problem:** A PR merged to master appears in multiple branches.

**Example:**
```
PR #6144 merged to master on 2024-09-15
- Included in stable2409 (cut before but includes this PR)
- Also in stable2412 (inherits from master)
- Also in stable2503 (inherits from master)
```

**Solution:**
```python
# Pseudocode for PR assignment
assigned_prs = set()

for release in sorted_by_date(runtime_releases):
    for pr in get_branch_prs(release.sdk_branch):
        if pr not in assigned_prs:
            assign_to_release(pr, release)
            assigned_prs.add(pr)
```

**Result:** PR #6144 is only counted in v1.4.0 (first appearance)

### 4. Backport Detection Patterns

**Challenge:** Backports have various naming conventions

**Patterns Detected:**
1. `[stable2503] Backport #9195`
2. `[stable2503] #9195`
3. `backport #9195`
4. `backport of #9195`
5. `backports paritytech/polkadot-sdk#9195`
6. `#9195 (backport)`

**Edge Cases Handled:**
- Bot-created backports (different author patterns)
- Manual backports with custom titles
- Multiple backports of the same PR
- Backports of backports (rejected - only track original)

### 5. SDK Version Matching Algorithm

**Problem:** Multiple SDK tags might have the same package versions

**Decision Tree:**
```
1. Find all SDK tags with matching package versions
   ├─> Single match: Use it
   └─> Multiple matches:
       ├─> Count matching packages
       │   ├─> Clear winner: Use it
       │   └─> Tie:
       │       ├─> Use chronological proximity
       │       │   ├─> Find closest before runtime release
       │       │   └─> No valid match: Use latest
       │       └─> Still tied: Lexicographical order
```

**Example:**
Runtime v1.5.0 has `polkadot-primitives: 15.0.0`
- stable2409-4 has this version (released 2024-09-20)
- stable2409-5 has this version (released 2024-09-25)
- Runtime released 2024-09-22
- **Decision:** Use stable2409-4 (closest before runtime)

### 6. Master PR Discovery - Exact Branch Points

**Problem:** Determining which master PRs are included in a branch

**Solution Evolution:**
1. **Original Approach**: Used first tag date as approximation
2. **Current Approach**: Uses GitHub compare API to find exact merge-base

**Algorithm:**
```python
def _get_branch_point(branch):
    # Use GitHub compare API to find merge-base
    compare_url = f"https://api.github.com/repos/paritytech/polkadot-sdk/compare/master...{branch}"
    response = make_request(compare_url)
    
    merge_base_commit = response.get('merge_base_commit')
    return {
        'sha': merge_base_commit['sha'],
        'date': merge_base_commit['commit']['committer']['date']
    }

def _get_master_prs_at_branch_point(branch, branch_commit, branch_date):
    # Get all PRs merged to master before the exact branch point
    query = f'repo:paritytech/polkadot-sdk type:pr is:merged base:master merged:<={branch_date}'
    # Fetch and filter PRs...
```

**Advantages:**
- **Precision**: Uses exact commit where branch diverged
- **Reliability**: No guessing or approximation
- **Consistency**: Same results regardless of tag timing

**Fallback Strategy:**
If branch point detection fails (e.g., branch deleted):
- Falls back to date range method using earliest tag
- Still provides reasonable approximation
- Logs warning for investigation

### 7. Data Structure Decisions

**Why Multiple Indices?**

1. **Forward Mapping** (`pr_to_releases`):
   - Quick lookup: "Which releases include PR #6144?"
   - Used by search functionality

2. **Reverse Mapping** (`package_to_tags`):
   - Quick lookup: "Which SDK tags have polkadot-primitives 15.0.0?"
   - Used by runtime-to-SDK matching

3. **Bidirectional Backports**:
   - `backport_mapping`: Find original from backport
   - `original_to_backports`: Find all backports of original
   - Enables complete relationship visualization

### 8. Performance Optimizations

**API Call Minimization:**
- Cache all PR details in `pr_cache`
- Batch API requests where possible
- Reuse data across operations

**Memory Efficiency:**
- Use sets for PR collections (deduplication)
- Store normalized data (e.g., strip 'polkadot-' prefix)
- Generate derived data on demand

### 9. Error Handling Strategy

**Graceful Degradation:**
```python
# Example: Package version extraction
try:
    content = fetch_cargo_toml(tag)
    version = extract_version(content)
except:
    # Don't fail entire process
    version = None
    log_warning(f"Could not extract version for {tag}")
```

**Validation Layers:**
1. Verify chronological ordering
2. Ensure PR dates precede release dates
3. Validate backport relationships
4. Check for orphaned data

### 10. Output File Decisions

**Two-File Strategy:**

1. **Complete Data** (`branch_aware_mappings.json`):
   - Full audit trail
   - Debugging information
   - Statistical analysis

2. **Optimized Data** (`sdk_pr_mappings.json`):
   - Only fields needed by UI
   - Reduced file size
   - Faster loading

**Rationale:** Separates operational needs from debugging/analysis needs

## Edge Cases and Special Handling

### 1. Renamed/Moved Packages
- Solution: Check multiple possible paths
- Fallback to known locations
- Log warnings for investigation

### 2. Force Pushes and Rebases
- PRs tracked by number (stable)
- Merge dates from API (authoritative)
- Commit SHAs not relied upon

### 3. Irregular Release Schedules
- No hardcoded dates
- Everything derived from actual data
- Adapts to changing release cadences

### 4. API Rate Limits
- Exponential backoff
- Caching to reduce calls
- Progress indicators for long runs

### 5. Incomplete Data
- Missing package versions: Skip but continue
- API failures: Retry with backoff
- Partial results: Save what's available

## Future Considerations

### Potential Enhancements

1. **Incremental Updates**: Only process new PRs/tags
2. **Parallel Processing**: Concurrent API calls
3. **Change Detection**: Skip unchanged branches
4. **Extended Metadata**: PR size, review info
5. **Graph Analysis**: PR dependency tracking

### Maintenance Guidelines

1. **Monitor API Changes**: GitHub API evolution
2. **Update Patterns**: New backport conventions
3. **Validate Accuracy**: Spot-check results
4. **Performance Metrics**: Track run times
5. **Error Patterns**: Common failure modes

This design ensures robust, accurate tracking of SDK changes through the complex release process while handling edge cases gracefully.