#!/usr/bin/env python3
"""
Analyzes PRs merged between releases in the polkadot-fellows/runtimes repository.
"""

import os
import json
import requests
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import anthropic
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import base64
import re


class GitHubAPI:
    """Handles GitHub API interactions"""
    
    def __init__(self, token: Optional[str] = None):
        self.base_url = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Polkadot-Release-Analyzer"
        }
        if token:
            self.headers["Authorization"] = f"token {token}"
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def _make_request(self, url: str, params: Optional[Dict] = None) -> Dict:
        """Make a request to GitHub API with rate limit handling"""
        response = self.session.get(url, params=params)
        
        # Check rate limit before processing
        if 'X-RateLimit-Remaining' in response.headers:
            remaining = int(response.headers['X-RateLimit-Remaining'])
            limit = int(response.headers.get('X-RateLimit-Limit', 60))
            reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
            
            if remaining < 10:
                current_time = int(time.time())
                reset_datetime = datetime.fromtimestamp(reset_time).strftime('%Y-%m-%d %H:%M:%S')
                print(f"\nRate limit status: {remaining}/{limit} requests remaining")
                print(f"Reset time: {reset_datetime}")
        
        # Handle rate limiting
        if response.status_code == 403:
            error_data = response.json()
            if 'rate limit' in error_data.get('message', '').lower():
                reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                wait_time = reset_time - int(time.time()) + 1
                if wait_time > 0:
                    print(f"\nRate limit exceeded. Waiting {wait_time} seconds...")
                    print("Tip: Use a GitHub personal access token to increase rate limits from 60 to 5000 requests/hour")
                    print("Set GITHUB_TOKEN environment variable or use --github-token flag")
                    time.sleep(wait_time)
                    response = self.session.get(url, params=params)
        
        response.raise_for_status()
        return response.json()
    
    def get_releases(self, owner: str, repo: str, limit: int = 10) -> List[Dict]:
        """Fetch the most recent releases"""
        url = f"{self.base_url}/repos/{owner}/{repo}/releases"
        releases = self._make_request(url, params={"per_page": limit})
        return releases[:limit]
    
    def get_release_by_tag(self, owner: str, repo: str, tag: str) -> Dict:
        """Fetch a specific release by tag name"""
        url = f"{self.base_url}/repos/{owner}/{repo}/releases/tags/{tag}"
        return self._make_request(url)
    
    def get_commits_between_dates(self, owner: str, repo: str, since: str, until: str) -> List[Dict]:
        """Get all commits between two dates"""
        url = f"{self.base_url}/repos/{owner}/{repo}/commits"
        commits = []
        page = 1
        
        while True:
            params = {
                "since": since,
                "until": until,
                "per_page": 100,
                "page": page
            }
            batch = self._make_request(url, params=params)
            if not batch:
                break
            commits.extend(batch)
            page += 1
            
        return commits
    
    def get_pr_for_commit(self, owner: str, repo: str, commit_sha: str) -> Optional[Dict]:
        """Get PR associated with a commit"""
        url = f"{self.base_url}/repos/{owner}/{repo}/commits/{commit_sha}/pulls"
        try:
            prs = self._make_request(url)
            return prs[0] if prs else None
        except:
            return None
    
    def get_pr_details(self, owner: str, repo: str, pr_number: int) -> Dict:
        """Get detailed PR information"""
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}"
        return self._make_request(url)
    
    def get_pr_diff(self, owner: str, repo: str, pr_number: int) -> str:
        """Get the diff for a PR"""
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}"
        response = self.session.get(url, headers={**self.headers, "Accept": "application/vnd.github.v3.diff"})
        response.raise_for_status()
        return response.text
    
    def get_pr_comments(self, owner: str, repo: str, pr_number: int) -> List[Dict]:
        """Get all comments on a PR"""
        # Get issue comments
        issue_url = f"{self.base_url}/repos/{owner}/{repo}/issues/{pr_number}/comments"
        issue_comments = self._make_request(issue_url)
        
        # Get review comments
        review_url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}/comments"
        review_comments = self._make_request(review_url)
        
        return issue_comments + review_comments
    
    def get_linked_issues(self, owner: str, repo: str, pr_body: str, pr_number: int) -> List[Dict]:
        """Extract and fetch linked issues from PR body"""
        linked_issues = []
        
        # Common patterns for issue references
        patterns = [
            r'(?:close|closes|closed|fix|fixes|fixed|resolve|resolves|resolved)\s+#(\d+)',
            r'#(\d+)',
            r'(?:close|closes|closed|fix|fixes|fixed|resolve|resolves|resolved)\s+' + 
            rf'{owner}/{repo}#(\d+)'
        ]
        
        issue_numbers = set()
        for pattern in patterns:
            matches = re.findall(pattern, pr_body.lower() if pr_body else '', re.IGNORECASE)
            issue_numbers.update(matches)
        
        # Fetch issue details
        for issue_num in issue_numbers:
            try:
                url = f"{self.base_url}/repos/{owner}/{repo}/issues/{issue_num}"
                issue = self._make_request(url)
                linked_issues.append(issue)
            except:
                continue
                
        return linked_issues
    
    def get_cargo_lock_at_tag(self, owner: str, repo: str, tag: str) -> Optional[str]:
        """Fetch Cargo.lock content at a specific release tag"""
        url = f"{self.base_url}/repos/{owner}/{repo}/contents/Cargo.lock?ref={tag}"
        try:
            response = self._make_request(url)
            content = base64.b64decode(response['content']).decode('utf-8')
            return content
        except Exception as e:
            print(f"Warning: Could not fetch Cargo.lock for {tag}: {e}")
            return None


class PolkadotReleaseAnalyzer:
    """Main analyzer class"""
    
    def __init__(self, github_token: Optional[str] = None, anthropic_api_key: Optional[str] = None):
        self.github = GitHubAPI(github_token)
        self.anthropic_client = anthropic.Anthropic(api_key=anthropic_api_key) if anthropic_api_key else None
        self.owner = "polkadot-fellows"
        self.repo = "runtimes"
    
    def extract_sdk_version_from_cargo_lock(self, cargo_lock_content: str) -> Optional[str]:
        """Extract SDK version from Cargo.lock content"""
        if not cargo_lock_content:
            return None
        
        # Look for key polkadot-sdk packages
        version_pattern = r'name = "polkadot-primitives"\s*\nversion = "([^"]+)"'
        match = re.search(version_pattern, cargo_lock_content)
        
        if match:
            version = match.group(1)
            # Map to SDK release (simplified - would need proper mapping in production)
            major_version = version.split('.')[0]
            version_map = {
                "15": "stable2407",
                "16": "stable2409", 
                "17": "stable2412",
                "18": "stable2503",
            }
            return version_map.get(major_version, f"v{version}")
        
        return None
    
    def get_latest_releases(self) -> Tuple[Dict, Dict]:
        """Get the two most recent releases"""
        releases = self.github.get_releases(self.owner, self.repo, limit=2)
        if len(releases) < 2:
            raise ValueError("Not enough releases found")
        return releases[0], releases[1]
    
    def get_release_and_previous(self, version: str) -> Tuple[Dict, Dict]:
        """Get a specific release and the one before it"""
        # Get the specified release
        target_release = self.github.get_release_by_tag(self.owner, self.repo, version)
        
        # Get list of releases to find the previous one
        releases = self.github.get_releases(self.owner, self.repo, limit=10)
        
        # Find the target release in the list
        target_index = None
        for i, release in enumerate(releases):
            if release['tag_name'] == version:
                target_index = i
                break
        
        if target_index is None:
            raise ValueError(f"Release {version} not found in recent releases")
        
        if target_index + 1 >= len(releases):
            # Need to fetch more releases
            releases = self.github.get_releases(self.owner, self.repo, limit=20)
            for i, release in enumerate(releases):
                if release['tag_name'] == version:
                    target_index = i
                    break
        
        if target_index + 1 >= len(releases):
            raise ValueError(f"No release found before {version}")
        
        previous_release = releases[target_index + 1]
        return target_release, previous_release
    
    def get_prs_between_releases(self, newer_release: Dict, older_release: Dict) -> List[Dict]:
        """Get all PRs merged between two releases"""
        # Get commits between releases
        commits = self.github.get_commits_between_dates(
            self.owner, 
            self.repo,
            older_release['created_at'],
            newer_release['created_at']
        )
        
        print(f"Found {len(commits)} commits between releases")
        
        # Get unique PRs from commits
        pr_numbers = set()
        prs = []
        
        # Use thread pool for concurrent PR fetching
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_commit = {
                executor.submit(self.github.get_pr_for_commit, self.owner, self.repo, commit['sha']): commit
                for commit in commits
            }
            
            for future in as_completed(future_to_commit):
                pr = future.result()
                if pr and pr['number'] not in pr_numbers:
                    pr_numbers.add(pr['number'])
                    prs.append(pr)
        
        print(f"Found {len(prs)} unique PRs")
        return prs
    
    def fetch_pr_details(self, pr_number: int) -> Dict:
        """Fetch comprehensive PR details including comments, linked issues, and diff"""
        pr_details = self.github.get_pr_details(self.owner, self.repo, pr_number)
        comments = self.github.get_pr_comments(self.owner, self.repo, pr_number)
        linked_issues = self.github.get_linked_issues(
            self.owner, self.repo, pr_details.get('body', ''), pr_number
        )
        
        # Fetch the diff
        try:
            diff = self.github.get_pr_diff(self.owner, self.repo, pr_number)
        except Exception as e:
            print(f"Warning: Could not fetch diff for PR #{pr_number}: {e}")
            diff = ""
        
        return {
            'pr': pr_details,
            'comments': comments,
            'linked_issues': linked_issues,
            'diff': diff
        }
    
    def analyze_diff(self, diff: str, max_length: int = 10000) -> Dict:
        """Analyze a diff to extract key information"""
        if not diff:
            return {
                'full_diff': 'No diff available',
                'files_changed': 0,
                'file_list': [],
                'additions': 0,
                'deletions': 0
            }
        
        lines = diff.split('\n')
        files_changed = set()
        additions = 0
        deletions = 0
        
        for line in lines:
            if line.startswith('diff --git'):
                # Extract file path
                parts = line.split(' ')
                if len(parts) >= 3:
                    file_path = parts[2].replace('a/', '')
                    files_changed.add(file_path)
            elif line.startswith('+') and not line.startswith('+++'):
                additions += 1
            elif line.startswith('-') and not line.startswith('---'):
                deletions += 1
        
        # Truncate diff if too long
        if len(diff) > max_length:
            diff = diff[:max_length] + "\n... (diff truncated)"
        
        return {
            'full_diff': diff,
            'files_changed': len(files_changed),
            'file_list': list(files_changed),
            'additions': additions,
            'deletions': deletions
        }
    
    def analyze_with_claude(self, pr_data: List[Dict], newer_release: Dict, older_release: Dict) -> str:
        """Use Claude to analyze the PR data and generate a summary"""
        if not self.anthropic_client:
            return "Claude API key not provided. Skipping AI analysis."
        
        # Prepare the data for Claude
        pr_summaries = []
        code_changes_summary = []
        
        for data in pr_data:
            pr = data['pr']
            
            # Analyze the diff
            diff_analysis = self.analyze_diff(data.get('diff', ''))
            
            summary = {
                'title': pr['title'],
                'body': pr['body'][:1000] if pr['body'] else '',
                'author': pr['user']['login'],
                'merged_at': pr['merged_at'],
                'labels': [label['name'] for label in pr.get('labels', [])],
                'comments_count': len(data['comments']),
                'files_changed': diff_analysis['files_changed'],
                'additions': diff_analysis['additions'],
                'deletions': diff_analysis['deletions'],
                'linked_issues': [
                    {
                        'title': issue['title'],
                        'body': issue['body'][:300] if issue.get('body') else '',
                        'state': issue['state']
                    }
                    for issue in data['linked_issues']
                ]
            }
            
            # Add significant comments
            significant_comments = [
                comment['body'][:200] 
                for comment in data['comments'] 
                if len(comment['body']) > 50
            ][:3]  # Limit to 3 most significant comments
            
            if significant_comments:
                summary['key_comments'] = significant_comments
            
            pr_summaries.append(summary)
            
            # Store code changes for detailed analysis
            if diff_analysis['files_changed'] > 0:
                code_changes_summary.append({
                    'pr_number': pr['number'],
                    'pr_title': pr['title'],
                    'files': diff_analysis['file_list'][:10],  # Limit files shown
                    'diff_sample': diff_analysis['full_diff'][:2000]  # Sample of diff
                })
        
        # Create the prompt for Claude
        prompt = f"""Analyze the following pull requests merged between releases {older_release['tag_name']} and {newer_release['tag_name']} of the Polkadot Fellows Runtimes repository.

Release dates:
- Previous: {older_release['tag_name']} ({older_release['created_at']})
- Latest: {newer_release['tag_name']} ({newer_release['created_at']})

PRs to analyze:
{json.dumps(pr_summaries, indent=2)}

Code changes details (samples):
{json.dumps(code_changes_summary[:10], indent=2)}

Please provide:

1. **Executive Summary for Non-Technical Users**
   - What are the main improvements and changes in plain language?
   - What benefits will users see?
   - Are there any actions users need to take?

2. **Key Changes Explained**
   - Breaking changes (explain what will stop working and why)
   - Security improvements (explain how users are better protected)
   - Performance improvements (explain how things will be faster/better)
   - New features (explain what users can now do)

3. **Technical Summary for Developers**
   - Major API/interface changes
   - Migration requirements
   - Technical improvements

4. **Code Impact Analysis**
   - Which parts of the system were most affected?
   - What types of changes were made (bug fixes, refactoring, new features)?

Please use simple, clear language especially in the non-technical sections. Avoid jargon and explain technical terms when necessary."""

        response = self.anthropic_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        return response.content[0].text
    
    def generate_report(self, output_file: str = "release_analysis.md", target_version: Optional[str] = None, json_output: Optional[str] = None):
        """Generate the full analysis report"""
        if target_version:
            print(f"Fetching release {target_version} and its predecessor...")
            newer_release, older_release = self.get_release_and_previous(target_version)
        else:
            print("Fetching latest releases...")
            newer_release, older_release = self.get_latest_releases()
        
        print(f"Analyzing changes between {older_release['tag_name']} and {newer_release['tag_name']}")
        
        # Get PRs between releases
        prs = self.get_prs_between_releases(newer_release, older_release)
        
        # Fetch detailed PR data
        print("Fetching PR details, comments, and linked issues...")
        pr_data = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_pr = {
                executor.submit(self.fetch_pr_details, pr['number']): pr
                for pr in prs
            }
            
            for future in as_completed(future_to_pr):
                try:
                    data = future.result()
                    pr_data.append(data)
                    print(f"Processed PR #{data['pr']['number']}")
                except Exception as e:
                    print(f"Error processing PR: {e}")
        
        # Generate AI analysis
        print("Analyzing with Claude...")
        ai_analysis = self.analyze_with_claude(pr_data, newer_release, older_release)
        
        # Generate the report
        report = f"""# Polkadot Fellows Runtime Release Analysis

## Release Comparison
- **Previous Release**: {older_release['tag_name']} ({older_release['created_at']})
  - SDK Version: {older_sdk_version if older_sdk_version != "unknown" else "Unable to determine"}
- **Latest Release**: {newer_release['tag_name']} ({newer_release['created_at']})
  - SDK Version: {newer_sdk_version if newer_sdk_version != "unknown" else "Unable to determine"}
- **Total PRs Merged**: {len(prs)}
{f"- **SDK Version Change**: {older_sdk_version} → {newer_sdk_version}" if older_sdk_version != newer_sdk_version and older_sdk_version != "unknown" and newer_sdk_version != "unknown" else ""}

## AI-Generated Analysis

{ai_analysis}

## Detailed PR List

"""
        
        # Add PR details
        for data in sorted(pr_data, key=lambda x: x['pr']['merged_at'], reverse=True):
            pr = data['pr']
            diff_analysis = self.analyze_diff(data.get('diff', ''))
            
            report += f"### PR #{pr['number']}: {pr['title']}\n"
            report += f"- **Author**: @{pr['user']['login']}\n"
            report += f"- **Merged**: {pr['merged_at']}\n"
            report += f"- **Files Changed**: {diff_analysis['files_changed']} (+"
            report += f"{diff_analysis['additions']}/-{diff_analysis['deletions']})\n"
            
            if pr.get('labels'):
                labels = ', '.join([f"`{label['name']}`" for label in pr['labels']])
                report += f"- **Labels**: {labels}\n"
            
            if data['linked_issues']:
                report += f"- **Linked Issues**: "
                issue_links = [f"#{issue['number']}" for issue in data['linked_issues']]
                report += ', '.join(issue_links) + "\n"
            
            report += f"- **Comments**: {len(data['comments'])}\n"
            
            # Show affected files (limit to 5)
            if diff_analysis['file_list']:
                report += f"- **Key Files Modified**:\n"
                for file in diff_analysis['file_list'][:5]:
                    report += f"  - `{file}`\n"
                if len(diff_analysis['file_list']) > 5:
                    report += f"  - ... and {len(diff_analysis['file_list']) - 5} more files\n"
            
            report += "\n"
        
        # Save the report
        with open(output_file, 'w') as f:
            f.write(report)
        
        # Extract SDK versions for both releases
        newer_cargo_lock = self.github.get_cargo_lock_at_tag(self.owner, self.repo, newer_release['tag_name'])
        newer_sdk_version = self.extract_sdk_version_from_cargo_lock(newer_cargo_lock) if newer_cargo_lock else "unknown"
        
        older_cargo_lock = self.github.get_cargo_lock_at_tag(self.owner, self.repo, older_release['tag_name'])
        older_sdk_version = self.extract_sdk_version_from_cargo_lock(older_cargo_lock) if older_cargo_lock else "unknown"
        
        # Save JSON output if requested
        if json_output:
            json_data = {
                'newer_release': {
                    'tag_name': newer_release['tag_name'],
                    'created_at': newer_release['created_at'],
                    'name': newer_release.get('name', newer_release['tag_name']),
                    'body': newer_release.get('body', ''),
                    'sdk_version': newer_sdk_version
                },
                'older_release': {
                    'tag_name': older_release['tag_name'],
                    'created_at': older_release['created_at'],
                    'name': older_release.get('name', older_release['tag_name']),
                    'sdk_version': older_sdk_version
                },
                'pr_count': len(prs),
                'ai_analysis': ai_analysis,
                'pr_details': []
            }
            
            # Add PR details with diff analysis
            for data in pr_data:
                pr = data['pr']
                diff_analysis = self.analyze_diff(data.get('diff', ''))
                
                pr_detail = {
                    'number': pr['number'],
                    'title': pr['title'],
                    'author': pr['user']['login'],
                    'merged_at': pr['merged_at'],
                    'body': pr.get('body', ''),
                    'labels': [label['name'] for label in pr.get('labels', [])],
                    'files_changed': diff_analysis['files_changed'],
                    'additions': diff_analysis['additions'],
                    'deletions': diff_analysis['deletions'],
                    'file_list': diff_analysis['file_list'],
                    'linked_issues': [
                        {
                            'number': issue['number'],
                            'title': issue['title'],
                            'state': issue['state']
                        }
                        for issue in data['linked_issues']
                    ],
                    'comment_count': len(data['comments'])
                }
                json_data['pr_details'].append(pr_detail)
            
            with open(json_output, 'w') as f:
                json.dump(json_data, f, indent=2)
            print(f"JSON data saved to {json_output}")
        
        print(f"\nAnalysis complete! Report saved to {output_file}")
        return report


def main():
    parser = argparse.ArgumentParser(description="Analyze Polkadot Fellows Runtime releases")
    parser.add_argument("--github-token", help="GitHub personal access token", 
                        default=os.environ.get("GITHUB_TOKEN"))
    parser.add_argument("--anthropic-key", help="Anthropic API key", 
                        default=os.environ.get("ANTHROPIC_API_KEY"))
    parser.add_argument("--output", help="Output file name", default="release_analysis.md")
    parser.add_argument("--version", help="Specific version to analyze (e.g., v1.2.3)", 
                        default=None)
    parser.add_argument("--json-output", help="JSON output file name", default=None)
    
    args = parser.parse_args()
    
    if not args.anthropic_key:
        print("Warning: No Anthropic API key provided. AI analysis will be skipped.")
        print("Set ANTHROPIC_API_KEY environment variable or use --anthropic-key flag")
    
    # Check GitHub token status
    if not args.github_token:
        print("\nWarning: No GitHub token provided. Using unauthenticated API access.")
        print("This limits you to 60 requests per hour, which may not be enough.")
        print("To get 5000 requests per hour, create a GitHub personal access token:")
        print("1. Go to https://github.com/settings/tokens")
        print("2. Generate a new token (classic) with 'repo' scope")
        print("3. Set GITHUB_TOKEN environment variable or use --github-token flag\n")
    else:
        print("Using authenticated GitHub API access (5000 requests/hour)")
    
    analyzer = PolkadotReleaseAnalyzer(args.github_token, args.anthropic_key)
    
    # Check current rate limit
    try:
        response = analyzer.github.session.get("https://api.github.com/rate_limit")
        if response.status_code == 200:
            data = response.json()
            core = data['rate']['core']
            remaining = core['remaining']
            limit = core['limit']
            reset_time = datetime.fromtimestamp(core['reset']).strftime('%Y-%m-%d %H:%M:%S')
            print(f"Current rate limit: {remaining}/{limit} requests remaining")
            print(f"Reset time: {reset_time}\n")
            
            if remaining < 50 and not args.github_token:
                print("Warning: Very low rate limit remaining. The script may need to wait.")
                print("Consider using a GitHub token to avoid delays.\n")
    except:
        pass
    
    analyzer.generate_report(args.output, args.version, args.json_output)


if __name__ == "__main__":
    main()