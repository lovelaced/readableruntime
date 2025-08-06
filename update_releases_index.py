#!/usr/bin/env python3
"""
Updates the releases index file for the GitHub Pages site
"""

import json
import os
from pathlib import Path
from datetime import datetime


def update_releases_index():
    """Update the releases index with all available releases"""
    docs_dir = Path("docs")
    releases_dir = docs_dir / "data" / "releases"
    metadata_dir = docs_dir / "data" / "metadata"
    
    # Create directories if they don't exist
    releases_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)
    
    # Collect all release JSON files
    releases = []
    for json_file in sorted(releases_dir.glob("*.json"), reverse=True):
        if json_file.stem != "index":  # Skip the index file itself
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                    releases.append({
                        'tag_name': data['newer_release']['tag_name'],
                        'created_at': data['newer_release']['created_at'],
                        'name': data['newer_release'].get('name', data['newer_release']['tag_name']),
                        'pr_count': data['pr_count'],
                        'compared_to': data['older_release']['tag_name'],
                        'filename': json_file.stem
                    })
            except Exception as e:
                print(f"Error reading {json_file}: {e}")
    
    # Sort by creation date (newest first)
    releases.sort(key=lambda x: x['created_at'], reverse=True)
    
    # Create index file
    index_data = {
        'last_updated': datetime.utcnow().isoformat() + 'Z',
        'releases': releases,
        'total_releases': len(releases)
    }
    
    index_file = releases_dir / "index.json"
    with open(index_file, 'w') as f:
        json.dump(index_data, f, indent=2)
    
    print(f"Updated releases index with {len(releases)} releases")
    return index_data


if __name__ == "__main__":
    update_releases_index()