// App state
const state = {
    releases: [],
    currentRelease: null,
    searchTerm: ''
};

// DOM elements
const releaseList = document.getElementById('releaseList');
const releaseContent = document.getElementById('releaseContent');
const searchInput = document.getElementById('releaseSearch');
const lastUpdatedSpan = document.getElementById('lastUpdated');

// Initialize the app
async function init() {
    try {
        // Load releases index
        const response = await fetch('data/releases/index.json');
        if (!response.ok) {
            throw new Error('Failed to load releases index');
        }
        
        const data = await response.json();
        state.releases = data.releases;
        
        // Update last updated time
        const lastUpdated = new Date(data.last_updated);
        lastUpdatedSpan.textContent = lastUpdated.toLocaleDateString();
        
        // Render release list
        renderReleaseList();
        
        // Check for release in URL hash
        const hash = window.location.hash.slice(1);
        if (hash && state.releases.find(r => r.tag_name === hash)) {
            loadRelease(hash);
        }
        
    } catch (error) {
        console.error('Error initializing app:', error);
        releaseList.innerHTML = `
            <div class="error-message">
                <p>Failed to load releases. Please check back later.</p>
            </div>
        `;
    }
}

// Render the release list
function renderReleaseList() {
    const filteredReleases = state.releases.filter(release => 
        release.tag_name.toLowerCase().includes(state.searchTerm.toLowerCase()) ||
        release.name.toLowerCase().includes(state.searchTerm.toLowerCase())
    );
    
    if (filteredReleases.length === 0) {
        releaseList.innerHTML = `
            <div class="no-results">
                <p>No releases found matching "${state.searchTerm}"</p>
            </div>
        `;
        return;
    }
    
    releaseList.innerHTML = filteredReleases.map(release => `
        <div class="release-item ${state.currentRelease === release.tag_name ? 'active' : ''}" 
             data-release="${release.tag_name}">
            <h3>${release.tag_name}</h3>
            <div class="release-meta">
                <span>${new Date(release.created_at).toLocaleDateString()}</span>
                <span>${release.pr_count} PRs</span>
            </div>
            <div class="release-meta">
                <span>vs ${release.compared_to}</span>
            </div>
        </div>
    `).join('');
    
    // Add click handlers
    document.querySelectorAll('.release-item').forEach(item => {
        item.addEventListener('click', () => {
            const releaseTag = item.dataset.release;
            loadRelease(releaseTag);
        });
    });
}

// Load a specific release
async function loadRelease(tagName) {
    // Show loading state
    releaseContent.innerHTML = `
        <div class="loading">
            <div class="spinner"></div>
            <p>Loading release analysis...</p>
        </div>
    `;
    
    try {
        // Find the release
        const release = state.releases.find(r => r.tag_name === tagName);
        if (!release) {
            throw new Error('Release not found');
        }
        
        // Load release data
        const response = await fetch(`data/releases/${release.filename}.json`);
        if (!response.ok) {
            throw new Error('Failed to load release data');
        }
        
        const data = await response.json();
        
        // Update state and URL
        state.currentRelease = tagName;
        window.location.hash = tagName;
        
        // Render release content
        renderRelease(data);
        
        // Update release list to show active state
        renderReleaseList();
        
    } catch (error) {
        console.error('Error loading release:', error);
        releaseContent.innerHTML = `
            <div class="error-message">
                <h3>Error Loading Release</h3>
                <p>Failed to load release data. Please try again later.</p>
            </div>
        `;
    }
}

// Render release content
function renderRelease(data) {
    const createdDate = new Date(data.newer_release.created_at);
    
    // Parse the AI analysis into sections
    const aiSections = parseAIAnalysis(data.ai_analysis);
    
    releaseContent.innerHTML = `
        <div class="release-header">
            <div class="release-title">
                <h2>${data.newer_release.tag_name}</h2>
                <a href="https://github.com/polkadot-fellows/runtimes/releases/tag/${data.newer_release.tag_name}" 
                   target="_blank" class="github-link">View on GitHub</a>
            </div>
            <div class="release-stats">
                <div class="stat-item">
                    <span class="stat-label">Release Date</span>
                    <span class="stat-value">${createdDate.toLocaleDateString()}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Compared To</span>
                    <span class="stat-value">${data.older_release.tag_name}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">PRs Merged</span>
                    <span class="stat-value">${data.pr_count}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Total Changes</span>
                    <span class="stat-value">
                        +${data.pr_details.reduce((sum, pr) => sum + pr.additions, 0).toLocaleString()} 
                        / -${data.pr_details.reduce((sum, pr) => sum + pr.deletions, 0).toLocaleString()}
                    </span>
                </div>
            </div>
        </div>
        
        <div class="ai-analysis">
            ${renderAIAnalysis(aiSections)}
        </div>
        
        <div class="pr-list">
            <h3>Pull Requests (${data.pr_details.length})</h3>
            ${renderPRList(data.pr_details)}
        </div>
    `;
    
    // Apply syntax highlighting to code blocks
    document.querySelectorAll('pre code').forEach((block) => {
        hljs.highlightElement(block);
    });
}

// Parse AI analysis into sections
function parseAIAnalysis(analysis) {
    // This is a simple parser - you might need to adjust based on actual format
    const sections = [];
    const lines = analysis.split('\n');
    let currentSection = null;
    
    for (const line of lines) {
        if (line.match(/^\d+\.\s+\*\*(.+)\*\*/)) {
            if (currentSection) {
                sections.push(currentSection);
            }
            currentSection = {
                title: line.replace(/^\d+\.\s+\*\*(.+)\*\*/, '$1'),
                content: []
            };
        } else if (currentSection && line.trim()) {
            currentSection.content.push(line);
        }
    }
    
    if (currentSection) {
        sections.push(currentSection);
    }
    
    // If no sections found, treat entire content as one section
    if (sections.length === 0) {
        sections.push({
            title: 'Analysis',
            content: lines
        });
    }
    
    return sections;
}

// Render AI analysis sections
function renderAIAnalysis(sections) {
    return sections.map(section => `
        <div class="analysis-section">
            <h3>${section.title}</h3>
            <div class="analysis-content markdown-content">
                ${marked.parse(section.content.join('\n'))}
            </div>
        </div>
    `).join('');
}

// Render PR list
function renderPRList(prs) {
    return prs.map(pr => `
        <div class="pr-item">
            <div class="pr-header">
                <div>
                    <a href="https://github.com/polkadot-fellows/runtimes/pull/${pr.number}" 
                       target="_blank" class="pr-title">
                        #${pr.number}: ${pr.title}
                    </a>
                    <div class="pr-meta">
                        <span>by @${pr.author}</span>
                        <span>${new Date(pr.merged_at).toLocaleDateString()}</span>
                        ${pr.comment_count > 0 ? `<span>${pr.comment_count} comments</span>` : ''}
                    </div>
                </div>
                <div class="pr-stats">
                    <span class="pr-stat additions">+${pr.additions}</span>
                    <span class="pr-stat deletions">-${pr.deletions}</span>
                    <span class="pr-stat">${pr.files_changed} files</span>
                </div>
            </div>
            ${pr.labels.length > 0 ? `
                <div class="pr-labels">
                    ${pr.labels.map(label => `<span class="label">${label}</span>`).join('')}
                </div>
            ` : ''}
            ${pr.linked_issues.length > 0 ? `
                <div class="pr-meta">
                    Closes: ${pr.linked_issues.map(issue => 
                        `<a href="https://github.com/polkadot-fellows/runtimes/issues/${issue.number}" 
                            target="_blank">#${issue.number}</a>`
                    ).join(', ')}
                </div>
            ` : ''}
        </div>
    `).join('');
}

// Search functionality
searchInput.addEventListener('input', (e) => {
    state.searchTerm = e.target.value;
    renderReleaseList();
});

// Initialize on load
document.addEventListener('DOMContentLoaded', init);

// Handle browser back/forward
window.addEventListener('hashchange', () => {
    const hash = window.location.hash.slice(1);
    if (hash && hash !== state.currentRelease) {
        loadRelease(hash);
    }
});