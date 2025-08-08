# Project Structure

## Overview
Readable Runtime is a tool that provides AI-generated analysis of Polkadot runtime releases, making technical updates accessible to everyone.

## Directory Structure

```
readableruntime/
├── .github/workflows/         # GitHub Actions workflows
│   ├── deploy-pages.yml      # Deploy to GitHub Pages
│   ├── update-release-notes.yml  # Check for new releases and analyze
│   └── update-sdk-mappings.yml   # Update SDK PR mappings
├── docs/                      # Website files
│   ├── css/                   # Stylesheets
│   │   └── style.css         # Main styles
│   ├── js/                    # JavaScript
│   │   └── app.js            # Main application logic
│   ├── data/                  # Generated data files
│   │   ├── releases/         # Release analysis data
│   │   └── sdk-mappings/     # SDK PR mapping data
│   │       └── prs/          # Individual PR files
│   ├── index.html            # Main website page
│   ├── COMPREHENSIVE_SDK_MAPPER_DOCUMENTATION.md  # Detailed mapper docs
│   ├── SDK_MAPPER_DECISION_LOGIC.md              # Design decisions
│   └── SDK_MAPPER_QUICK_REFERENCE.md             # Developer reference
├── scripts/                   # Core operational scripts
│   ├── comprehensive_branch_aware_mapper.py  # SDK PR mapper
│   ├── polkadot_release_analyzer.py         # Runtime release analyzer
│   ├── update_releases_index.py              # Update release index
│   └── initialize_site.py                    # Initialize new deployment
├── .gitignore
├── README.md                  # Project documentation
├── UPDATE_GUIDE.md           # Update instructions
├── CHANGES_PR_DETAILS.md     # Change history
├── PROJECT_STRUCTURE.md      # This file
└── requirements.txt          # Python dependencies
```

## Key Components

### Main Scripts

1. **comprehensive_branch_aware_mapper.py**
   - Tracks SDK PRs across all release branches
   - Maps backports to original PRs
   - Ensures each PR is only counted once
   - Generates JSON data for the website

2. **polkadot_release_analyzer.py**
   - Analyzes Fellowship runtime releases
   - Compares releases to find changes
   - Uses Claude AI to generate summaries
   - Creates both markdown and JSON output

3. **update_releases_index.py**
   - Updates the release index file
   - Maintains list of all analyzed releases

### Website

The `docs/` directory contains the static website that displays the analysis:
- Single-page application using vanilla JavaScript
- Displays runtime releases and their changes
- SDK PR search functionality
- Responsive design with dark theme

### Workflows

GitHub Actions automatically:
- Check for new runtime releases every 6 hours
- Analyze new releases with AI
- Update SDK mappings daily
- Deploy to GitHub Pages

## Data Flow

1. **New Release Detection** → GitHub Action triggers
2. **Release Analysis** → polkadot_release_analyzer.py
3. **SDK Mapping** → comprehensive_branch_aware_mapper.py  
4. **Data Generation** → JSON files in docs/data/
5. **Website Update** → GitHub Pages deployment
6. **User Access** → Interactive web interface

## Development

To run locally:
```bash
# Install dependencies
pip install -r requirements.txt

# Run release analyzer
python scripts/polkadot_release_analyzer.py --version v1.6.1

# Update SDK mappings
python scripts/comprehensive_branch_aware_mapper.py

# Start local server
python -m http.server -d docs 8000
```

## Environment Variables

- `GITHUB_TOKEN` - GitHub API access
- `ANTHROPIC_API_KEY` - Claude AI API access