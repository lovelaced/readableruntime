#!/usr/bin/env python3
"""
Initialize the GitHub Pages site with existing releases
"""

import os
import sys
import subprocess
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from polkadot_release_analyzer import PolkadotReleaseAnalyzer, GitHubAPI
from update_releases_index import update_releases_index


def initialize_site():
    """Initialize the site with recent releases"""
    github_token = os.environ.get("GITHUB_TOKEN")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    
    if not anthropic_key:
        print("Warning: No ANTHROPIC_API_KEY found. AI analysis will be skipped.")
    
    # Create directories
    docs_dir = Path("docs")
    releases_dir = docs_dir / "data" / "releases"
    releases_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize analyzer
    analyzer = PolkadotReleaseAnalyzer(github_token, anthropic_key)
    github = GitHubAPI(github_token)
    
    # Get recent releases (11 to have 10 comparisons)
    print("Fetching recent releases...")
    releases = github.get_releases("polkadot-fellows", "runtimes", limit=11)
    
    print(f"Found {len(releases)} releases")
    
    # Analyze the 10 most recent releases (skip the oldest one as we need a previous release to compare)
    releases_to_analyze = min(10, len(releases) - 1)
    print(f"Will analyze the {releases_to_analyze} most recent releases")
    
    for i in range(releases_to_analyze):
        release = releases[i]
        tag_name = release['tag_name']
        
        # Check if already analyzed
        json_file = releases_dir / f"{tag_name}.json"
        if json_file.exists():
            print(f"Release {tag_name} already analyzed, skipping...")
            continue
        
        print(f"\nAnalyzing release {tag_name}...")
        try:
            analyzer.generate_report(
                output_file=str(releases_dir / f"{tag_name}.md"),
                target_version=tag_name,
                json_output=str(json_file)
            )
            print(f"Successfully analyzed {tag_name}")
        except Exception as e:
            print(f"Error analyzing {tag_name}: {e}")
    
    # Update the index
    print("\nUpdating releases index...")
    update_releases_index()
    
    # Generate SDK PR mappings
    print("\nGenerating SDK PR mappings...")
    # Run the populate script to generate SDK mappings
    subprocess.run([sys.executable, "scripts/populate_sdk_mappings.py"], check=True)
    
    print("\nInitialization complete!")
    print(f"Generated files in: {releases_dir}")


if __name__ == "__main__":
    initialize_site()