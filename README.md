# Polkadot Fellows Runtime Release Analyzer

This utility analyzes pull requests merged between releases in the [polkadot-fellows/runtimes](https://github.com/polkadot-fellows/runtimes) repository and provides AI-generated insights about the changes, including code analysis for non-technical users.

## Features

- Fetches the two most recent releases or analyzes a specific version
- Collects all PRs merged between releases
- Retrieves PR comments, linked issues, and **code diffs**
- Uses Claude AI to analyze changes and provide:
  - Non-technical summaries explaining what changed
  - Executive summaries for decision makers
  - Technical details for developers
  - Code impact analysis
- Generates a comprehensive markdown report with file change statistics

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up API keys:
```bash
export ANTHROPIC_API_KEY="your-anthropic-api-key"
export GITHUB_TOKEN="your-github-token"  # Optional but recommended for higher rate limits
```

## Usage

```bash
# Analyze the latest release vs the previous one
python polkadot_release_analyzer.py

# Analyze a specific version vs the previous one
python polkadot_release_analyzer.py --version v1.2.5
```

### Command line options:

- `--github-token`: GitHub personal access token (optional, improves rate limits)
- `--anthropic-key`: Anthropic API key for Claude analysis
- `--output`: Output file name (default: release_analysis.md)
- `--version`: Specific version to analyze (e.g., v1.2.3)

### Examples:

```bash
# Analyze latest release
python polkadot_release_analyzer.py --output latest_analysis.md

# Analyze specific version v1.2.5 compared to v1.2.4
python polkadot_release_analyzer.py --version v1.2.5 --output v1.2.5_analysis.md

# With authentication tokens
export GITHUB_TOKEN="your-github-token"
export ANTHROPIC_API_KEY="your-anthropic-key"
python polkadot_release_analyzer.py --version v1.2.5
```

## Output

The tool generates a markdown report containing:

1. **Release comparison details**
2. **AI-generated analysis** including:
   - **Executive Summary for Non-Technical Users** - Plain language explanation of changes
   - **Key Changes Explained** - Breaking changes, security updates, performance improvements
   - **Technical Summary for Developers** - API changes, migration requirements
   - **Code Impact Analysis** - Which parts were affected and how
3. **Detailed PR list** with:
   - Author, merge date, labels
   - Files changed with addition/deletion counts
   - Key modified files
   - Linked issues and comment counts

## Requirements

- Python 3.7+
- Anthropic API key (for AI analysis)
- GitHub token (optional but recommended)

## Rate Limits

The tool handles GitHub API rate limits automatically. If you hit rate limits without a token, consider adding a GitHub personal access token.

## GitHub Pages Site

This project includes a GitHub Pages site that automatically updates when new releases are published.

### Setting Up the Site

1. **Enable GitHub Pages** in your repository settings:
   - Go to Settings → Pages
   - Set source to "Deploy from a branch"
   - Select `main` branch and `/docs` folder
   - Save

2. **Add Secrets** to your repository:
   - Go to Settings → Secrets and variables → Actions
   - Add `ANTHROPIC_API_KEY` with your Anthropic API key

3. **Initialize the Site** with the 10 most recent releases:
   ```bash
   export GITHUB_TOKEN="your-token"
   export ANTHROPIC_API_KEY="your-key"
   python scripts/initialize_site.py
   ```
   
   This will analyze the 10 most recent releases and generate the initial site content.

4. **Commit and Push** the generated files:
   ```bash
   git add docs/
   git commit -m "Initialize GitHub Pages site"
   git push
   ```

### Automatic Updates

The site will automatically update every 6 hours via GitHub Actions:
- Checks for new releases in polkadot-fellows/runtimes
- Analyzes any new releases found
- Updates the site with the analysis
- Deploys to GitHub Pages

You can manually trigger workflows:

**To check for new releases:**
1. Go to Actions → "Update Release Notes"
2. Click "Run workflow"

**To redeploy the site (after manual changes):**
1. Go to Actions → "Deploy GitHub Pages"
2. Click "Run workflow"

### Site Features

- **Searchable Release List**: Filter releases by version
- **AI-Generated Summaries**: Non-technical explanations of changes
- **PR Details**: View all PRs, files changed, and statistics
- **Mobile Responsive**: Works on all devices
- **Auto-Updated**: Checks for new releases every 6 hours

The site will be available at: `https://[your-username].github.io/readableruntime/`