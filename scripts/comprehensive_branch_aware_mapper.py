#!/usr/bin/env python3
"""
Comprehensive Branch-Aware SDK Mapper

This script provides the correct, comprehensive approach to tracking SDK versions
in runtime releases by understanding:

1. SDK release branches (stable2503, stable2412, etc.)
2. How releases are cut from branches with backports and cherry-picks
3. Package version mapping from crates.io
4. Complete PR tracking on branches
"""

import re
import json
import requests
import base64
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, timezone
import os
from collections import defaultdict
import time

class BranchAwareSDKMapper:
    """Maps SDK releases to runtime versions with full branch awareness"""
    
    def __init__(self, github_token: str = None):
        self.github_token = github_token
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Branch-Aware-SDK-Mapper"
        }
        if github_token:
            self.headers["Authorization"] = f"token {github_token}"
        
        # Core data structures
        self.sdk_tags = {}  # tag -> {commit, date, branch, package_versions}
        self.package_to_tags = defaultdict(list)  # "pkg:version" -> [tags]
        self.branch_info = {}  # branch -> {created_date, base_commit, tags, prs}
        self.pr_cache = {}  # pr_number -> pr_details
        self.runtime_mappings = {}  # runtime_tag -> sdk_info
        self.backport_mapping = {}  # backport_pr -> original_pr
        self.original_to_backports = defaultdict(list)  # original_pr -> [backport_prs]
        
        # Track key packages
        self.tracked_packages = ['polkadot-primitives', 'sp-runtime', 'frame-support']
    
    def _parse_date(self, date_str: str) -> datetime:
        """Parse ISO date string to datetime object"""
        if date_str.endswith('Z'):
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return datetime.fromisoformat(date_str)
        
    def _make_request(self, url: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make GitHub API request with rate limit handling"""
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=15)
            
            # Handle rate limits
            if 'X-RateLimit-Remaining' in response.headers:
                remaining = int(response.headers['X-RateLimit-Remaining'])
                if remaining < 100:
                    print(f"   Low rate limit: {remaining} requests remaining")
            
            if response.status_code == 403 and 'rate limit' in response.text.lower():
                reset = int(response.headers.get('X-RateLimit-Reset', 0))
                wait = max(0, reset - int(time.time()))
                print(f"  Rate limited. Waiting {wait}s...")
                time.sleep(wait + 1)
                return self._make_request(url, params)
            
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"  API Error: {e}")
            return None
    
    def build_sdk_tag_database(self):
        """Build comprehensive database of SDK tags and their properties"""
        print("=" * 80)
        print("BUILDING SDK TAG DATABASE")
        print("=" * 80)
        
        # Get all stable SDK tags
        print("\nFetching SDK tags...")
        tags = []
        page = 1
        
        while page <= 15:
            url = "https://api.github.com/repos/paritytech/polkadot-sdk/tags"
            data = self._make_request(url, params={"per_page": 100, "page": page})
            
            if not data:
                break
                
            stable_tags = [t for t in data if re.match(r'^polkadot-stable\d{4}', t['name'])]
            tags.extend(stable_tags)
            
            # Debug: Show stable2506 tags specifically
            stable2506_tags = [t['name'] for t in stable_tags if 'stable2506' in t['name']]
            if stable2506_tags:
                print(f"  Page {page}: found stable2506 tags: {stable2506_tags}")
            
            print(f"  Page {page}: found {len(stable_tags)} stable tags")
            
            if len(data) < 100:
                break
            page += 1
        
        print(f"\nTotal stable tags found: {len(tags)}")
        
        # Analyze each tag
        print("\nAnalyzing tags...")
        for i, tag_data in enumerate(tags):
            tag_name = tag_data['name']
            normalized = tag_name.replace('polkadot-', '')
            
            if i % 10 == 0:
                print(f"  Progress: {i}/{len(tags)} tags")
            
            # Get commit info
            commit_url = f"https://api.github.com/repos/paritytech/polkadot-sdk/commits/{tag_name}"
            commit_data = self._make_request(commit_url)
            
            if not commit_data:
                continue
            
            # Get package versions
            pkg_versions = self._get_package_versions(tag_name)
            
            # Debug stable2506 tags
            if 'stable2506' in tag_name:
                print(f"    Tag {tag_name}: package versions = {pkg_versions}")
            
            # Determine branch
            branch = self._determine_branch(normalized)
            
            # Store tag info
            self.sdk_tags[normalized] = {
                'commit': commit_data['sha'],
                'date': commit_data['commit']['committer']['date'],
                'branch': branch,
                'package_versions': pkg_versions
            }
            
            # Map packages to tags
            for pkg, ver in pkg_versions.items():
                key = f"{pkg}:{ver}"
                self.package_to_tags[key].append(normalized)
            
            # Track branch info
            if branch not in self.branch_info:
                self.branch_info[branch] = {
                    'tags': [],
                    'created_date': None,
                    'base_commit': None,
                    'prs': set()
                }
            self.branch_info[branch]['tags'].append(normalized)
        
        print(f"\nBuilt database with {len(self.sdk_tags)} SDK tags")
        print(f"Found {len(self.branch_info)} release branches")
        
        # Debug: Show what branches we found
        print("\nRelease branches found:")
        for branch in sorted(self.branch_info.keys()):
            if branch != "unknown":
                print(f"  {branch}: {len(self.branch_info[branch]['tags'])} tags")
    
    def _get_package_versions(self, tag: str) -> Dict[str, str]:
        """Get package versions from an SDK tag"""
        versions = {}
        
        # Map packages to their paths in the SDK repo
        package_paths = {
            'polkadot-primitives': 'polkadot/primitives/Cargo.toml',
            'sp-runtime': 'substrate/primitives/runtime/Cargo.toml',
            'frame-support': 'substrate/frame/support/Cargo.toml'
        }
        
        for pkg, path in package_paths.items():
            url = f"https://api.github.com/repos/paritytech/polkadot-sdk/contents/{path}?ref={tag}"
            response = self._make_request(url)
            
            if response:
                try:
                    content = base64.b64decode(response['content']).decode('utf-8')
                    match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
                    if match:
                        versions[pkg] = match.group(1)
                except:
                    pass
        
        return versions
    
    def _determine_branch(self, tag: str) -> str:
        """Determine which branch a tag belongs to"""
        # Extract stable branch pattern
        match = re.match(r'stable(\d{4})', tag)
        if match:
            return f"stable{match.group(1)}"
        return "unknown"
    
    def _get_actual_branch_name(self, branch: str) -> Optional[str]:
        """Get the actual GitHub branch name for a stable branch"""
        # Cache results to avoid repeated API calls
        if hasattr(self, '_branch_name_cache'):
            if branch in self._branch_name_cache:
                return self._branch_name_cache[branch]
        else:
            self._branch_name_cache = {}
        
        # The actual branch names in the SDK are just the stable names
        # e.g., stable2412, stable2409, etc.
        branch_url = f"https://api.github.com/repos/paritytech/polkadot-sdk/branches/{branch}"
        branch_response = self._make_request(branch_url)
        
        if branch_response:
            self._branch_name_cache[branch] = branch
            return branch
        
        self._branch_name_cache[branch] = None
        return None
    
    def _get_branch_point(self, branch: str) -> Optional[Dict[str, str]]:
        """Get the exact commit where branch diverged from master using GitHub API"""
        print(f"  Finding branch point for {branch}...")
        
        # Get the actual branch name
        actual_branch = self._get_actual_branch_name(branch)
        
        if not actual_branch:
            print(f"    No branch found for {branch} pattern")
            return None
        
        print(f"    Found actual branch name: {actual_branch}")
        
        # Compare master...branch to find merge base
        compare_url = f"https://api.github.com/repos/paritytech/polkadot-sdk/compare/master...{actual_branch}"
        response = self._make_request(compare_url)
        
        if not response:
            print(f"    Could not compare master...{actual_branch}")
            return None
        
        merge_base_commit = response.get('merge_base_commit')
        if not merge_base_commit:
            print(f"    No merge base found for {branch}")
            return None
        
        # Get the commit details for the exact date
        commit_sha = merge_base_commit['sha']
        commit_date = merge_base_commit['commit']['committer']['date']
        
        return {
            'sha': commit_sha,
            'date': commit_date
        }
    
    def analyze_release_branches(self):
        """Analyze release branches to understand their history"""
        print("\n" + "=" * 80)
        print("ANALYZING RELEASE BRANCHES")
        print("=" * 80)
        
        # Sort branches chronologically for proper date range calculation
        sorted_branches = sorted(
            [(b, i) for b, i in self.branch_info.items() if b != "unknown"],
            key=lambda x: x[0]  # Sort by branch name (stable2409, stable2412, etc.)
        )
        
        # First pass: Get all branch points and dates
        print("\nPhase 1: Getting branch points...")
        for branch, info in sorted_branches:
            print(f"\nAnalyzing branch: {branch}")
            
            # Get the exact branch point from master
            branch_point = self._get_branch_point(branch)
            if branch_point:
                info['branch_point'] = branch_point['sha']
                info['branch_date'] = branch_point['date']
                info['created_date'] = branch_point['date']  # Use exact branch date
                print(f"  Branch point: {branch_point['sha'][:8]} ({branch_point['date'][:10]})")
            else:
                # Fallback to earliest tag method if branch point detection fails
                branch_tags = [(t, self.sdk_tags[t]['date']) for t in info['tags']]
                branch_tags.sort(key=lambda x: x[1])
                
                if branch_tags:
                    earliest_tag, earliest_date = branch_tags[0]
                    info['created_date'] = earliest_date
                    print(f"  Fallback to earliest tag: {earliest_tag} ({earliest_date[:10]})")
            
            if info['tags']:
                print(f"  Total tags: {len(info['tags'])}")
        
        # Second pass: Find PRs for each branch (now that all dates are set)
        print("\n\nPhase 2: Finding PRs for each branch...")
        for branch, info in sorted_branches:
            print(f"\nFinding PRs for branch: {branch}")
            self._find_branch_prs(branch, info)
    
    def _find_branch_prs(self, branch: str, branch_info: Dict):
        """Find all PRs included in a release branch (direct + from master)"""
        pr_count = 0
        branch_prs = set()
        
        # Get the actual branch name
        actual_branch = self._get_actual_branch_name(branch)
        
        # First, get PRs directly on the branch
        queries = []
        if actual_branch:
            queries.append(f'repo:paritytech/polkadot-sdk type:pr is:merged base:{actual_branch}')
        
        # Also search for PRs with the branch name in title (for backports)
        queries.extend([
            f'repo:paritytech/polkadot-sdk type:pr is:merged "[{branch}]" in:title',
            f'repo:paritytech/polkadot-sdk type:pr is:merged "backport" "{branch}" in:title'
        ])
        
        for query in queries:
            page = 1
            while page <= 5:
                result = self._make_request(
                    "https://api.github.com/search/issues",
                    params={"q": query, "per_page": 100, "page": page}
                )
                
                if not result:
                    break
                
                items = result.get('items', [])
                for pr in items:
                    pr_num = pr['number']
                    if pr_num not in branch_prs:
                        branch_prs.add(pr_num)
                        pr_count += 1
                        
                        # Cache PR details
                        pr_details = {
                            'number': str(pr_num),
                            'title': pr['title'],
                            'author': pr['user']['login'] if pr.get('user') else 'unknown',
                            'merged_at': pr.get('pull_request', {}).get('merged_at'),
                            'labels': [label['name'] for label in pr.get('labels', [])],
                            'url': pr['html_url'],
                            'branch': branch,
                            'is_direct': True
                        }
                        
                        # Check if this is a backport and extract original PR
                        # Need to fetch PR body if not provided
                        pr_body = pr.get('body', '')
                        if not pr_body and '[' in pr['title'] and ']' in pr['title']:
                            # Might be a backport, fetch full PR details
                            pr_url = f"https://api.github.com/repos/paritytech/polkadot-sdk/pulls/{pr_num}"
                            pr_detail_response = self._make_request(pr_url)
                            if pr_detail_response:
                                pr_body = pr_detail_response.get('body', '')
                        
                        original_pr = self._extract_backport_info(pr['title'], pr_body)
                        if original_pr and original_pr > 0 and original_pr < 100000:  # Basic validation
                            pr_details['is_backport'] = True
                            pr_details['original_pr'] = original_pr
                            self.backport_mapping[pr_num] = original_pr
                            self.original_to_backports[original_pr].append(pr_num)
                            
                            # Ensure we have info for the original PR too
                            if original_pr not in self.pr_cache:
                                self._fetch_pr_details(original_pr)
                        
                        self.pr_cache[pr_num] = pr_details
                
                if len(items) < 100:
                    break
                page += 1
                time.sleep(0.1)
        
        print(f"  Found {pr_count} direct PRs on {branch}")
        
        # Now get PRs from master that are included in this branch
        if branch_info.get('branch_point'):
            # Use exact branch point to find master PRs
            master_pr_count = self._get_master_prs_at_branch_point(
                branch,
                branch_info['branch_point'],
                branch_info['branch_date'],
                branch_prs
            )
            pr_count += master_pr_count
            print(f"  Found {master_pr_count} master PRs included in {branch} (using exact branch point)")
        elif branch_info.get('created_date'):
            # Fallback to date range method
            prev_branch_date = self._find_previous_branch_date(branch)
            
            if prev_branch_date:
                # Only get PRs between previous branch and this branch
                master_pr_count = self._get_master_prs_for_branch(
                    branch, 
                    prev_branch_date, 
                    branch_info['created_date'],
                    branch_prs
                )
                pr_count += master_pr_count
                print(f"  Found {master_pr_count} master PRs included in {branch} (fallback method)")
            else:
                # This is the earliest branch - skip master PRs
                print(f"  Skipping master PRs for {branch} (earliest branch, would include entire history)")
        
        branch_info['prs'] = branch_prs
        print(f"  Total PRs for {branch}: {len(branch_prs)}")
    
    def _get_master_prs_at_branch_point(self, branch: str, branch_commit: str, branch_date: str, existing_prs: Set[int]) -> int:
        """Get all PRs that were on master at the exact branch point"""
        count = 0
        
        print(f"    Fetching master PRs up to branch point {branch_commit[:8]}")
        
        # Find the previous branch to get the date range
        prev_branch_date = self._find_previous_branch_date(branch)
        
        # We need to find all PRs merged to master between the previous branch and this branch
        # GitHub search doesn't support commit-based queries, so we use date
        if prev_branch_date:
            query = f'repo:paritytech/polkadot-sdk type:pr is:merged base:master merged:{prev_branch_date}..{branch_date}'
            print(f"    Date range: {prev_branch_date[:10]} to {branch_date[:10]}")
        else:
            # This is the earliest branch we're tracking - skip master PRs
            print(f"    This is the earliest branch - skipping master PRs (would include entire history)")
            return count
        
        page = 1
        while page <= 10:
            result = self._make_request(
                "https://api.github.com/search/issues",
                params={"q": query, "per_page": 100, "page": page, "sort": "created", "order": "desc"}
            )
            
            if not result:
                break
            
            items = result.get('items', [])
            if not items:
                break
            
            for pr in items:
                pr_num = pr['number']
                if pr_num not in existing_prs:
                    # Double-check this PR was actually included in the branch
                    # by verifying it was merged before our branch point
                    merged_at = pr.get('pull_request', {}).get('merged_at', '')
                    if merged_at:
                        merged_dt = self._parse_date(merged_at)
                        branch_dt = self._parse_date(branch_date)
                        if merged_dt < branch_dt:  # Use < instead of <= to avoid boundary issues
                            existing_prs.add(pr_num)
                            count += 1
                        
                        # Cache PR details
                        self.pr_cache[pr_num] = {
                            'number': str(pr_num),
                            'title': pr['title'],
                            'author': pr['user']['login'] if pr.get('user') else 'unknown',
                            'merged_at': merged_at,
                            'labels': [label['name'] for label in pr.get('labels', [])],
                            'url': pr['html_url'],
                            'branch': branch,
                            'is_direct': False,
                            'from_master': True
                        }
            
            if len(items) < 100:
                break
            page += 1
            time.sleep(0.1)
        
        return count
    
    def _find_previous_branch_date(self, current_branch: str) -> Optional[str]:
        """Find when the previous release branch was created"""
        # Extract year/month from current branch
        match = re.match(r'stable(\d{2})(\d{2})', current_branch)
        if not match:
            return None
        
        year = int(match.group(1))
        month = int(match.group(2))
        
        # Calculate previous branch (3 months earlier)
        prev_month = month - 3
        prev_year = year
        if prev_month <= 0:
            prev_month += 12
            prev_year -= 1
        
        prev_branch = f"stable{prev_year:02d}{prev_month:02d}"
        
        # Check if previous branch exists and get its creation date
        if prev_branch in self.branch_info and self.branch_info[prev_branch].get('created_date'):
            return self.branch_info[prev_branch]['created_date']
        
        # If no previous branch, return None
        return None
    
    def _find_next_branch_date(self, current_branch: str) -> Optional[str]:
        """Find when the next release branch was created"""
        # Extract year/month from current branch
        match = re.match(r'stable(\d{2})(\d{2})', current_branch)
        if not match:
            return None
        
        year = int(match.group(1))
        month = int(match.group(2))
        
        # Calculate next branch (3 months later)
        next_month = month + 3
        next_year = year
        if next_month > 12:
            next_month -= 12
            next_year += 1
        
        next_branch = f"stable{next_year:02d}{next_month:02d}"
        
        # Check if next branch exists and get its creation date
        if next_branch in self.branch_info and self.branch_info[next_branch].get('created_date'):
            return self.branch_info[next_branch]['created_date']
        
        # If no next branch, use current date as cutoff
        return datetime.utcnow().isoformat() + 'Z'
    
    def _get_master_prs_for_branch(self, branch: str, from_date: str, to_date: str, existing_prs: Set[int]) -> int:
        """Get PRs merged to master between two dates"""
        count = 0
        
        # Search for PRs merged to master in the date range
        query = f'repo:paritytech/polkadot-sdk type:pr is:merged base:master merged:{from_date}..{to_date}'
        
        page = 1
        while page <= 10:  # More pages for master PRs
            result = self._make_request(
                "https://api.github.com/search/issues",
                params={"q": query, "per_page": 100, "page": page}
            )
            
            if not result:
                break
            
            items = result.get('items', [])
            for pr in items:
                pr_num = pr['number']
                if pr_num not in existing_prs:
                    existing_prs.add(pr_num)
                    count += 1
                    
                    # Cache PR details
                    self.pr_cache[pr_num] = {
                        'number': str(pr_num),
                        'title': pr['title'],
                        'author': pr['user']['login'] if pr.get('user') else 'unknown',
                        'merged_at': pr.get('pull_request', {}).get('merged_at'),
                        'labels': [label['name'] for label in pr.get('labels', [])],
                        'url': pr['html_url'],
                        'branch': branch,
                        'is_direct': False,
                        'from_master': True
                    }
            
            if len(items) < 100:
                break
            page += 1
            time.sleep(0.1)
        
        return count
    
    def _extract_backport_info(self, title: str, body: str) -> Optional[int]:
        """Extract original PR number from backport PR title/body"""
        # Common patterns for backport PRs
        patterns = [
            r'\[stable\d+\]\s*(?:backport\s*)?#(\d+)',  # [stable2503] #1234 or [stable2503] backport #1234
            r'backport\s+#(\d+)',  # backport #1234
            r'backport\s+of\s+#(\d+)',  # backport of #1234
            r'backports?\s+paritytech/polkadot-sdk#(\d+)',  # backports paritytech/polkadot-sdk#1234
            r'#(\d+)\s*\(backport\)',  # #1234 (backport)
            r'cherry[- ]?pick\s+#(\d+)',  # cherry-pick #1234 or cherry pick #1234
            r'backport-(\d+)-to-',  # backport-1234-to-stable
        ]
        
        # Check title first
        for pattern in patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                return int(match.group(1))
        
        # Check body for references
        if body:
            # Look for PR references in body
            pr_refs = re.findall(r'#(\d+)', body)
            if pr_refs:
                # Usually the first PR reference is the original
                return int(pr_refs[0])
        
        return None
    
    def _fetch_pr_details(self, pr_num: int) -> None:
        """Fetch and cache details for a specific PR"""
        print(f"      Fetching details for PR #{pr_num}")
        
        pr_url = f"https://api.github.com/repos/paritytech/polkadot-sdk/pulls/{pr_num}"
        pr_data = self._make_request(pr_url)
        
        if pr_data:
            # Determine which branch this PR was merged to
            base_branch = pr_data.get('base', {}).get('ref', 'unknown')
            
            self.pr_cache[pr_num] = {
                'number': str(pr_num),
                'title': pr_data.get('title', ''),
                'author': pr_data.get('user', {}).get('login', 'unknown'),
                'merged_at': pr_data.get('merged_at'),
                'labels': [label['name'] for label in pr_data.get('labels', [])],
                'url': pr_data.get('html_url', ''),
                'branch': base_branch,
                'is_direct': False,
                'from_master': base_branch == 'master'
            }
        else:
            print(f"        WARNING: Could not fetch details for PR #{pr_num}")
    
    def map_runtime_releases(self):
        """Map runtime releases to SDK versions"""
        print("\n" + "=" * 80)
        print("MAPPING RUNTIME RELEASES")  
        print("=" * 80)
        
        # Dynamically fetch runtime releases from GitHub
        print("Fetching runtime releases from GitHub...")
        runtime_tags = []
        page = 1
        
        while page <= 5:  # Limit to 5 pages to avoid too many old releases
            url = "https://api.github.com/repos/polkadot-fellows/runtimes/releases"
            releases = self._make_request(url, params={"per_page": 30, "page": page})
            
            if not releases:
                break
                
            for release in releases:
                if not release.get('prerelease') and not release.get('draft'):
                    runtime_tags.append(release['tag_name'])
            
            if len(releases) < 30:
                break
            page += 1
        
        print(f"Found {len(runtime_tags)} runtime releases")
        print(f"Latest releases: {runtime_tags[:5]}")  # Show first 5 (most recent)
        
        # Process releases in reverse order (oldest first)
        for runtime_tag in reversed(runtime_tags):
            print(f"\nAnalyzing {runtime_tag}...")
            
            # Get runtime package versions from Cargo.lock
            runtime_pkgs = self._get_runtime_packages(runtime_tag)
            if not runtime_pkgs:
                print(f"  Could not get package versions")
                continue
            
            # Debug: Always show package versions for troubleshooting
            if runtime_tag in ["v1.7.0", "v1.7.1", "v1.7.2"]:  # Latest releases
                print(f"  Package versions found:")
                for pkg, ver in runtime_pkgs.items():
                    print(f"    {pkg}: {ver}")
            
            # Find best matching SDK tag
            best_match = self._find_best_sdk_match(runtime_pkgs, runtime_tag)
            
            if best_match:
                tag_info = self.sdk_tags[best_match]
                sdk_branch = tag_info['branch']
                branch_prs = len(self.branch_info[sdk_branch]['prs']) if sdk_branch in self.branch_info else 0
                
                self.runtime_mappings[runtime_tag] = {
                    'sdk_tag': best_match,
                    'sdk_branch': sdk_branch,
                    'sdk_date': tag_info['date'],
                    'package_versions': runtime_pkgs,
                    'branch_pr_count': branch_prs
                }
                
                print(f"  Matched to SDK: {best_match}")
                print(f"    Branch: {sdk_branch}")
                print(f"    Branch PRs: {branch_prs}")
                
                # Debug: Show package versions that led to this match
                print(f"    Package versions matched:")
                for pkg, ver in runtime_pkgs.items():
                    print(f"      {pkg}: {ver}")
            else:
                print(f"  No SDK match found")
    
    def _get_runtime_packages(self, runtime_tag: str) -> Dict[str, str]:
        """Get package versions from runtime Cargo.lock"""
        url = f"https://api.github.com/repos/polkadot-fellows/runtimes/contents/Cargo.lock?ref={runtime_tag}"
        response = self._make_request(url)
        
        if not response:
            return {}
        
        try:
            content = base64.b64decode(response['content']).decode('utf-8')
            versions = {}
            
            # Parse Cargo.lock
            current_pkg = None
            for line in content.split('\n'):
                if line.startswith('name = '):
                    current_pkg = line.split('"')[1]
                elif line.startswith('version = ') and current_pkg in self.tracked_packages:
                    versions[current_pkg] = line.split('"')[1]
            
            return versions
        except:
            return {}
    
    def _find_best_sdk_match(self, runtime_pkgs: Dict[str, str], runtime_tag: str) -> Optional[str]:
        """Find the best matching SDK tag for runtime package versions"""
        # Get runtime release date for chronological matching
        release_url = f"https://api.github.com/repos/polkadot-fellows/runtimes/releases/tags/{runtime_tag}"
        release_data = self._make_request(release_url)
        runtime_date = release_data['created_at'] if release_data else None
        
        # Find all possible matches
        candidates = []
        
        # Debug for v1.7.0
        if runtime_tag == "v1.7.0":
            print(f"    Looking for SDK tags with these package versions:")
            for pkg, version in runtime_pkgs.items():
                key = f"{pkg}:{version}"
                print(f"      {key} -> {self.package_to_tags.get(key, 'NOT FOUND')}")
        
        for pkg, version in runtime_pkgs.items():
            key = f"{pkg}:{version}"
            if key in self.package_to_tags:
                # Get tags that have this package version
                for tag in self.package_to_tags[key]:
                    candidates.append(tag)
        
        if not candidates:
            return None
        
        # Count occurrences - the tag that matches most packages wins
        tag_scores = defaultdict(int)
        for tag in candidates:
            tag_scores[tag] += 1
        
        # Get tags with highest score
        max_score = max(tag_scores.values())
        best_tags = [t for t, s in tag_scores.items() if s == max_score]
        
        if len(best_tags) == 1:
            return best_tags[0]
        
        # Multiple tags match - use chronological proximity
        if runtime_date:
            runtime_ts = datetime.fromisoformat(runtime_date.replace('Z', '+00:00'))
            
            best_tag = None
            best_diff = None
            
            for tag in best_tags:
                tag_date = self.sdk_tags[tag]['date']
                tag_ts = datetime.fromisoformat(tag_date.replace('Z', '+00:00'))
                
                # Only consider SDK tags before runtime release
                if tag_ts <= runtime_ts:
                    diff = (runtime_ts - tag_ts).total_seconds()
                    if best_diff is None or diff < best_diff:
                        best_diff = diff
                        best_tag = tag
            
            if best_tag:
                return best_tag
        
        # Fallback: return the latest tag
        return sorted(best_tags)[-1]
    
    def calculate_pr_counts(self):
        """Calculate actual PR counts for each runtime release"""
        print("\n" + "=" * 80)
        print("CALCULATING PR COUNTS")
        print("=" * 80)
        
        # Build PR to releases mapping first
        pr_mapping = self._build_pr_to_releases_mapping()
        
        # Count PRs for each runtime release
        for runtime_tag in self.runtime_mappings:
            pr_count = 0
            for pr_num, releases in pr_mapping.items():
                for release in releases:
                    if release['runtime_version'] == runtime_tag.lstrip('v'):
                        pr_count += 1
                        break
            
            self.runtime_mappings[runtime_tag]['actual_pr_count'] = pr_count
            print(f"\n{runtime_tag}:")
            print(f"  SDK: {self.runtime_mappings[runtime_tag]['sdk_tag']}")
            print(f"  PRs in this release: {pr_count}")
    
    def _count_prs_between_dates(self, from_date: str, to_date: str) -> int:
        """Count PRs merged between two dates"""
        query = f"repo:paritytech/polkadot-sdk type:pr is:merged merged:{from_date}..{to_date}"
        
        result = self._make_request(
            "https://api.github.com/search/issues",
            params={"q": query, "per_page": 1}
        )
        
        if result:
            return result.get('total_count', 0)
        return 0
    
    def generate_final_report(self):
        """Generate comprehensive final report"""
        print("\n" + "=" * 80)
        print("FINAL COMPREHENSIVE REPORT")
        print("=" * 80)
        
        print("\n= Summary Statistics:")
        print(f"  SDK tags analyzed: {len(self.sdk_tags)}")
        print(f"  Release branches: {len(self.branch_info)}")
        print(f"  Runtime releases mapped: {len(self.runtime_mappings)}")
        print(f"  Total PRs tracked: {len(self.pr_cache)}")
        
        print("\n=Runtime SDK Mappings:")
        for runtime in sorted(self.runtime_mappings.keys(), reverse=True):
            info = self.runtime_mappings[runtime]
            print(f"\n{runtime}:")
            print(f"  SDK tag: {info['sdk_tag']}")
            print(f"  SDK branch: {info['sdk_branch']}")
            print(f"  PRs included in this release: {info.get('actual_pr_count', 0)}")
            print(f"  Package versions:")
            for pkg, ver in sorted(info['package_versions'].items()):
                print(f"    {pkg}: {ver}")
        
        print("\n<? Release Branch Summary:")
        for branch in sorted(self.branch_info.keys()):
            if branch == "unknown":
                continue
            info = self.branch_info[branch]
            print(f"\n{branch}:")
            print(f"  Tags: {len(info['tags'])}")
            print(f"  PRs: {len(info['prs'])}")
            if info.get('created_date'):
                print(f"  Created: {info['created_date'][:10]}")
    
    def save_results(self, output_dir: str = "docs/data/sdk-mappings"):
        """Save all results to files"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Prepare output data
        output_data = {
            'generated_at': datetime.utcnow().isoformat() + 'Z',
            'methodology': 'branch-aware-comprehensive',
            'runtime_mappings': self.runtime_mappings,
            'sdk_tags': self.sdk_tags,
            'branch_info': {
                branch: {
                    'tags': info['tags'],
                    'created_date': info.get('created_date'),
                    'pr_count': len(info['prs'])
                }
                for branch, info in self.branch_info.items()
            },
            'statistics': {
                'total_sdk_tags': len(self.sdk_tags),
                'total_branches': len(self.branch_info),
                'total_prs_tracked': len(self.pr_cache),
                'runtime_releases_mapped': len(self.runtime_mappings)
            }
        }
        
        # Save main file
        with open(output_path / "branch_aware_mappings.json", 'w') as f:
            json.dump(output_data, f, indent=2)
        
        # Save simplified runtime mappings for the website
        runtime_sdk_versions = {}
        for runtime_tag, info in self.runtime_mappings.items():
            runtime_sdk_versions[runtime_tag] = {
                'sdk_version': info['sdk_tag'],
                'release_date': info['sdk_date'],
                'total_prs': info.get('actual_pr_count', 0),
                'new_prs': info.get('actual_pr_count', 0)
            }
        
        website_data = {
            'last_updated': datetime.utcnow().isoformat() + 'Z',
            'runtime_sdk_versions': runtime_sdk_versions,
            'pr_details': self.pr_cache,
            'pr_to_releases': self._build_pr_to_releases_mapping(),
            'backport_mapping': self.backport_mapping,
            'original_to_backports': dict(self.original_to_backports)
        }
        
        with open(output_path / "sdk_pr_mappings.json", 'w') as f:
            json.dump(website_data, f, indent=2)
        
        print(f"\n Saved comprehensive mappings to {output_path}")
        
        return output_data
    
    def _build_pr_to_releases_mapping(self) -> Dict[str, List[Dict]]:
        """Build mapping of PRs to runtime releases - each PR only in first release"""
        pr_to_releases = defaultdict(list)
        
        # Sort runtime releases by SDK date (oldest first)
        sorted_releases = sorted(
            self.runtime_mappings.items(),
            key=lambda x: x[1]['sdk_date']
        )
        
        # Track which PRs have been assigned
        assigned_prs = set()
        
        # For each runtime release (oldest to newest)
        for runtime_tag, info in sorted_releases:
            branch = info['sdk_branch']
            sdk_date = info['sdk_date']
            
            if branch in self.branch_info:
                # Get all PRs on this branch
                branch_prs = self.branch_info[branch]['prs']
                
                # Only include PRs that:
                # 1. Haven't been assigned to an earlier release
                # 2. Were merged before this SDK tag date
                for pr_num in branch_prs:
                    if pr_num not in assigned_prs:
                        # Check if PR was merged before this SDK tag
                        pr_details = self.pr_cache.get(pr_num, {})
                        merged_at = pr_details.get('merged_at')
                        
                        if merged_at:
                            merged_dt = self._parse_date(merged_at)
                            sdk_dt = self._parse_date(sdk_date)
                            if merged_dt < sdk_dt:  # Use < instead of <= to avoid boundary issues
                                # Include PR metadata in the release mapping
                                release_info = {
                                    'runtime_version': runtime_tag.lstrip('v'),
                                    'sdk_version': info['sdk_tag'],
                                    'sdk_branch': branch
                                }
                                
                                # Add PR type info from cache
                                if pr_details.get('is_backport'):
                                    release_info['is_backport'] = True
                                    release_info['original_pr'] = pr_details.get('original_pr')
                                if pr_details.get('from_master'):
                                    release_info['from_master'] = True
                                if pr_details.get('is_direct'):
                                    release_info['is_direct'] = True
                                    
                                pr_to_releases[str(pr_num)].append(release_info)
                                assigned_prs.add(pr_num)
        
        return dict(pr_to_releases)
    
    def run_complete_analysis(self):
        """Run the complete analysis pipeline"""
        print("=Starting Comprehensive Branch-Aware SDK Analysis")
        print("=" * 80)
        
        # Step 1: Build SDK tag database
        self.build_sdk_tag_database()
        
        # Step 2: Analyze release branches
        self.analyze_release_branches()
        
        # Step 3: Map runtime releases
        self.map_runtime_releases()
        
        # Step 4: Calculate PR counts
        self.calculate_pr_counts()
        
        # Step 5: Ensure we have all original PRs for backports
        self._fetch_missing_original_prs()
        
        # Step 6: Generate report
        self.generate_final_report()
        
        # Step 7: Save results
        return self.save_results()
    
    def _fetch_missing_original_prs(self):
        """Ensure we have details for all original PRs referenced by backports"""
        print("\n" + "=" * 80)
        print("FETCHING MISSING ORIGINAL PRS")
        print("=" * 80)
        
        missing_prs = []
        for backport_pr, original_pr in self.backport_mapping.items():
            if original_pr not in self.pr_cache:
                missing_prs.append(original_pr)
        
        if missing_prs:
            print(f"\nFound {len(missing_prs)} original PRs that need fetching")
            for pr_num in sorted(set(missing_prs)):
                self._fetch_pr_details(pr_num)
        else:
            print("\nAll original PRs already cached")


def main():
    """Run the comprehensive branch-aware SDK mapper"""
    github_token = os.environ.get("GITHUB_TOKEN")
    
    if not github_token:
        print("WARNING: No GITHUB_TOKEN found. You will hit rate limits.")
        print("Set: export GITHUB_TOKEN=your_token_here")
        print()
    
    mapper = BranchAwareSDKMapper(github_token)
    mapper.run_complete_analysis()


if __name__ == "__main__":
    main()
