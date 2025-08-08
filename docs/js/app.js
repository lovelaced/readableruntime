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
            <h3>Fellowship Pull Requests (${data.pr_details.length})</h3>
            ${renderPRList(data.pr_details)}
        </div>
        
        <div class="sdk-pr-list" id="sdkPRList">
            <div class="loading">Loading SDK PRs...</div>
        </div>
    `;
    
    // Apply syntax highlighting to code blocks
    document.querySelectorAll('pre code').forEach((block) => {
        hljs.highlightElement(block);
    });
    
    // Load SDK PRs for this release
    loadSDKPRsForRelease(data.newer_release.tag_name);
}

// Parse AI analysis into sections
function parseAIAnalysis(analysis) {
    // Split by numbered sections with bold headers
    const sectionRegex = /^(\d+)\.\s+\*\*(.+?)\*\*$/gm;
    const sections = [];
    let lastIndex = 0;
    let match;
    
    const matches = [];
    while ((match = sectionRegex.exec(analysis)) !== null) {
        matches.push({
            index: match.index,
            title: match[2],
            fullMatch: match[0]
        });
    }
    
    // Process each section
    for (let i = 0; i < matches.length; i++) {
        const current = matches[i];
        const nextIndex = i < matches.length - 1 ? matches[i + 1].index : analysis.length;
        
        // Get content between this header and the next section (or end)
        const content = analysis.substring(
            current.index + current.fullMatch.length,
            nextIndex
        ).trim();
        
        sections.push({
            title: current.title,
            content: content
        });
    }
    
    // If no sections found, check for other common patterns
    if (sections.length === 0) {
        // Try to split by H2 headers (##)
        const h2Sections = analysis.split(/^##\s+/m).filter(s => s.trim());
        if (h2Sections.length > 1) {
            for (const section of h2Sections) {
                const lines = section.trim().split('\n');
                if (lines.length > 0) {
                    sections.push({
                        title: lines[0].replace(/\*\*/g, ''),
                        content: lines.slice(1).join('\n').trim()
                    });
                }
            }
        } else {
            // Fallback: treat entire content as one section
            sections.push({
                title: 'Analysis',
                content: analysis
            });
        }
    }
    
    return sections;
}

// Render AI analysis sections
function renderAIAnalysis(sections) {
    return sections.map(section => {
        // Ensure content is a string
        const content = typeof section.content === 'string' 
            ? section.content 
            : section.content.join('\n');
        
        return `
            <div class="analysis-section">
                <h3>${section.title}</h3>
                <div class="analysis-content markdown-content">
                    ${marked.parse(content)}
                </div>
            </div>
        `;
    }).join('');
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

// Load and render SDK PRs for a specific release
async function loadSDKPRsForRelease(releaseTagName) {
    const sdkPRContainer = document.getElementById('sdkPRList');
    
    if (!sdkMappings) {
        sdkPRContainer.innerHTML = `
            <div class="sdk-pr-info">
                <p>SDK PR mappings not available</p>
            </div>
        `;
        return;
    }
    
    try {
        // Get the runtime version (with 'v' prefix)
        const runtimeVersionKey = releaseTagName.startsWith('v') ? releaseTagName : 'v' + releaseTagName;
        const runtimeVersion = releaseTagName.replace(/^v/, '');
        
        // Get SDK version info for this runtime release
        const sdkVersionInfo = sdkMappings.runtime_sdk_versions ? 
            sdkMappings.runtime_sdk_versions[runtimeVersionKey] : null;
        
        // Find SDK PRs for this release (sample PRs)
        const sdkPRs = [];
        
        if (sdkMappings.pr_to_releases) {
            for (const [prNumber, releases] of Object.entries(sdkMappings.pr_to_releases)) {
                const releaseMatch = releases.find(r => r.runtime_version === runtimeVersion);
                if (releaseMatch) {
                    const prDetails = sdkMappings.pr_details ? sdkMappings.pr_details[prNumber] : null;
                    sdkPRs.push({
                        number: prNumber,
                        details: prDetails,
                        release: releaseMatch
                    });
                }
            }
        }
        
        // If we have SDK version info, display it
        if (sdkVersionInfo && sdkVersionInfo.sdk_version) {
            // Sort PRs by PR number (descending)
            sdkPRs.sort((a, b) => parseInt(b.number) - parseInt(a.number));
            
            // Render with SDK info
            sdkPRContainer.innerHTML = `
                <div class="sdk-pr-info">
                    <h3>SDK Pull Requests</h3>
                    <div class="sdk-stats">
                        <div class="stat-item">
                            <span class="stat-label">SDK Version:</span>
                            <span class="stat-value">${sdkVersionInfo.sdk_version}</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">SDK Release Date:</span>
                            <span class="stat-value">${new Date(sdkVersionInfo.release_date).toLocaleDateString()}</span>
                        </div>
                    </div>
                    ${sdkPRs.length > 0 ? `
                        <div class="sdk-pr-list">
                            <h4>SDK PRs included in this release (${sdkPRs.length})</h4>
                            <div class="sdk-pr-items">
                                ${renderSDKPRList(sdkPRs)}
                            </div>
                        </div>
                    ` : `
                        <p>No SDK PR details available for this release.</p>
                    `}
                </div>
            `;
            return;
        }
        
        // Fallback to old behavior if no SDK version info
        if (sdkPRs.length === 0) {
            sdkPRContainer.innerHTML = `
                <div class="sdk-pr-info">
                    <h3>SDK Pull Requests</h3>
                    <p>No SDK PRs found for this release.</p>
                </div>
            `;
            return;
        }
        
        // Sort by PR number (descending)
        sdkPRs.sort((a, b) => parseInt(b.number) - parseInt(a.number));
        
        // Render SDK PRs
        sdkPRContainer.innerHTML = `
            <h3>SDK Pull Requests (${sdkPRs.length})</h3>
            <div class="sdk-pr-items">
                ${renderSDKPRList(sdkPRs)}
            </div>
        `;
        
    } catch (error) {
        console.error('Error loading SDK PRs:', error);
        sdkPRContainer.innerHTML = `
            <div class="sdk-pr-info">
                <h3>SDK Pull Requests</h3>
                <p>Error loading SDK PRs for this release.</p>
            </div>
        `;
    }
}

// Render SDK PR list
function renderSDKPRList(sdkPRs) {
    return sdkPRs.map(pr => {
        const details = pr.details;
        const release = pr.release;
        
        if (!details) {
            // For PRs without details, try to determine type from release metadata
            let prType = '';
            let prTypeClass = '';
            
            if (release.is_backport) {
                prType = 'Backport';
                prTypeClass = 'backport-badge';
            } else if (release.from_master) {
                prType = 'Master';
                prTypeClass = 'master-badge';
            } else if (release.is_direct) {
                prType = 'Direct to ' + release.sdk_branch;
                prTypeClass = 'direct-badge';
            }
            
            // Check if we have backport info in release metadata
            const originalPR = release.original_pr;
            const originalPRDetails = originalPR && sdkMappings?.pr_details ? sdkMappings.pr_details[originalPR] : null;
            
            return `
                <div class="sdk-pr-item">
                    <div class="sdk-pr-header">
                        <a href="https://github.com/paritytech/polkadot-sdk/pull/${pr.number}" 
                           target="_blank" class="sdk-pr-title">
                            SDK PR #${pr.number}
                        </a>
                        <div class="sdk-pr-meta">
                            ${prType ? `<span class="sdk-version-badge ${prTypeClass}">${prType}</span>` : ''}
                        </div>
                    </div>
                    ${release.is_backport && originalPR ? `
                        <div class="backport-info-inline">
                            <span class="backport-label-inline">Backport of:</span>
                            <a href="https://github.com/paritytech/polkadot-sdk/pull/${originalPR}" target="_blank" class="backport-link-inline">
                                #${originalPR}${originalPRDetails ? `: ${originalPRDetails.title}` : ''}
                            </a>
                        </div>
                    ` : ''}
                </div>
            `;
        }
        
        // Determine PR type based on PR details and release metadata
        let prType = '';
        let prTypeClass = '';
        
        if (details.is_backport) {
            prType = 'Backport';
            prTypeClass = 'backport-badge';
        } else if (details.from_master) {
            prType = 'Master';
            prTypeClass = 'master-badge';
        } else if (details.is_direct) {
            prType = 'Direct to ' + release.sdk_branch;
            prTypeClass = 'direct-badge';
        }
        
        // Check if this is a backport and get original PR info
        const isBackport = details.is_backport;
        const originalPR = details.original_pr;
        const originalPRDetails = originalPR && sdkMappings?.pr_details ? sdkMappings.pr_details[originalPR] : null;
        
        return `
            <div class="sdk-pr-item">
                <div class="sdk-pr-header">
                    <div>
                        <a href="${details.url}" target="_blank" class="sdk-pr-title">
                            SDK PR #${details.number}: ${details.title}
                        </a>
                        <div class="sdk-pr-meta">
                            <span>by @${details.author}</span>
                            ${details.merged_at ? `<span>${new Date(details.merged_at).toLocaleDateString()}</span>` : ''}
                            ${prType ? `<span class="sdk-version-badge ${prTypeClass}">${prType}</span>` : ''}
                        </div>
                    </div>
                </div>
                ${isBackport && originalPR ? `
                    <div class="backport-info-inline">
                        <span class="backport-label-inline">Backport of:</span>
                        <a href="https://github.com/paritytech/polkadot-sdk/pull/${originalPR}" target="_blank" class="backport-link-inline">
                            #${originalPR}${originalPRDetails ? `: ${originalPRDetails.title}` : ''}
                        </a>
                    </div>
                ` : ''}
                ${details.labels && details.labels.length > 0 ? `
                    <div class="sdk-pr-labels">
                        ${details.labels.map(label => `<span class="pr-label">${label}</span>`).join('')}
                    </div>
                ` : ''}
            </div>
        `;
    }).join('');
}

// Search functionality
searchInput.addEventListener('input', (e) => {
    state.searchTerm = e.target.value;
    renderReleaseList();
});

// SDK PR Search functionality
const prSearchModal = document.getElementById('prSearchModal');
const openPRSearchBtn = document.getElementById('openPRSearch');
const closePRSearchBtn = document.getElementById('closePRSearch');
const sdkPRInput = document.getElementById('sdkPRInput');
const searchSDKPRBtn = document.getElementById('searchSDKPR');
const prSearchResults = document.getElementById('prSearchResults');

let sdkMappings = null;

// Load SDK mappings
async function loadSDKMappings() {
    try {
        const response = await fetch('data/sdk-mappings/sdk_pr_mappings.json');
        if (response.ok) {
            sdkMappings = await response.json();
            
            // Display mapping statistics in console
            if (sdkMappings.statistics) {
                console.log('SDK Mapping Statistics:', sdkMappings.statistics);
            }
        }
    } catch (error) {
        console.error('Failed to load SDK mappings:', error);
    }
}

// Open PR search modal
openPRSearchBtn.addEventListener('click', () => {
    prSearchModal.classList.add('show');
    sdkPRInput.focus();
});

// Close PR search modal
closePRSearchBtn.addEventListener('click', () => {
    prSearchModal.classList.remove('show');
    prSearchResults.innerHTML = '';
    sdkPRInput.value = '';
});

// Close modal on outside click
prSearchModal.addEventListener('click', (e) => {
    if (e.target === prSearchModal) {
        prSearchModal.classList.remove('show');
        prSearchResults.innerHTML = '';
        sdkPRInput.value = '';
    }
});

// Search for SDK PR
async function searchSDKPR() {
    const searchQuery = sdkPRInput.value.trim();
    
    if (!searchQuery) {
        prSearchResults.innerHTML = `
            <div class="pr-search-error">
                Please enter a PR number or title
            </div>
        `;
        return;
    }
    
    // Check if it's a number-only search
    const isNumberSearch = /^\d+$/.test(searchQuery);
    
    // Show loading state
    prSearchResults.innerHTML = `
        <div class="pr-search-loading">
            <div class="spinner"></div>
            <p>Searching for ${isNumberSearch ? `SDK PR #${searchQuery}` : `"${searchQuery}"`}...</p>
        </div>
    `;
    searchSDKPRBtn.disabled = true;
    
    try {
        if (isNumberSearch) {
            // Number search - check original PR and backports
            const prNumber = searchQuery;
            
            // Check if this number might be an original PR that was backported
            let effectivePRNumber = prNumber;
            let searchNote = '';
            
            // First check if we have local mapping data
            if (sdkMappings && sdkMappings.pr_to_releases) {
                // Check if this PR exists directly
                if (sdkMappings.pr_to_releases[prNumber]) {
                    // Format data for display
                    const prData = {
                        pr_details: sdkMappings.pr_details ? sdkMappings.pr_details[prNumber] : null,
                        runtime_releases: sdkMappings.pr_to_releases[prNumber]
                    };
                    displaySDKPRResults(prData, prNumber);
                } else if (sdkMappings.original_to_backports && sdkMappings.original_to_backports[prNumber]) {
                    // This is an original PR with backports
                    const backports = sdkMappings.original_to_backports[prNumber];
                    
                    // Check if any backport is in runtime releases
                    let foundBackport = null;
                    for (const backportNum of backports) {
                        if (sdkMappings.pr_to_releases[backportNum]) {
                            foundBackport = backportNum;
                            break;
                        }
                    }
                    
                    if (foundBackport) {
                        // Show the backport that made it into a runtime
                        const prData = {
                            pr_details: sdkMappings.pr_details ? sdkMappings.pr_details[foundBackport] : null,
                            runtime_releases: sdkMappings.pr_to_releases[foundBackport]
                        };
                        displaySDKPRResults(prData, foundBackport);
                    } else {
                        // Show original PR info with backport list
                        displayOriginalPRWithBackports(prNumber, backports);
                    }
                } else {
                    // Try to load individual PR file
                    const response = await fetch(`data/sdk-mappings/prs/${prNumber}.json`);
                    if (response.ok) {
                        const prData = await response.json();
                        displaySDKPRResults(prData, prNumber);
                    } else {
                        // PR not found in mappings
                        prSearchResults.innerHTML = `
                            <div class="pr-search-not-found">
                                <h3>PR #${prNumber} Not Found</h3>
                                <p>This SDK PR hasn't been included in any runtime releases yet, or the mapping data hasn't been updated.</p>
                                ${sdkMappings && sdkMappings.statistics ? `
                                <p style="margin-top: 0.5rem; font-size: 0.875rem; color: var(--text-secondary);">
                                    Currently tracking ${sdkMappings.statistics.total_prs_tracked} SDK PRs across ${sdkMappings.statistics.runtime_releases_analyzed} runtime releases.
                                </p>` : ''}
                                <p style="margin-top: 1rem;">
                                    <a href="https://github.com/paritytech/polkadot-sdk/pull/${prNumber}" 
                                       target="_blank" class="sdk-pr-link">
                                        View PR on GitHub →
                                    </a>
                                </p>
                            </div>
                        `;
                    }
                }
            }
        } else {
            // Title search - search through all PR details
            const searchResults = searchPRsByTitle(searchQuery);
            
            if (searchResults.length > 0) {
                displaySearchResults(searchResults, searchQuery);
            } else {
                prSearchResults.innerHTML = `
                    <div class="pr-search-not-found">
                        <h3>No Results Found</h3>
                        <p>No SDK PRs found matching "${searchQuery}"</p>
                        ${sdkMappings && sdkMappings.statistics ? `
                        <p style="margin-top: 0.5rem; font-size: 0.875rem; color: var(--text-secondary);">
                            Searched ${sdkMappings.statistics.total_prs_tracked} SDK PRs across ${sdkMappings.statistics.runtime_releases_analyzed} runtime releases.
                        </p>` : ''}
                    </div>
                `;
            }
        }
    } catch (error) {
        console.error('Error searching for SDK PR:', error);
        prSearchResults.innerHTML = `
            <div class="pr-search-error">
                <h3>Error</h3>
                <p>Failed to search for PR. Please try again later.</p>
            </div>
        `;
    } finally {
        searchSDKPRBtn.disabled = false;
    }
}

// Search PRs by title
function searchPRsByTitle(query) {
    if (!sdkMappings || !sdkMappings.pr_to_releases) {
        return [];
    }
    
    const lowerQuery = query.toLowerCase();
    const results = [];
    
    // Search through all PRs
    for (const [prNumber, releases] of Object.entries(sdkMappings.pr_to_releases)) {
        const prDetails = sdkMappings.pr_details ? sdkMappings.pr_details[prNumber] : null;
        
        if (prDetails && prDetails.title) {
            // Check if title contains the search query
            if (prDetails.title.toLowerCase().includes(lowerQuery)) {
                results.push({
                    pr_number: prNumber,
                    pr_details: prDetails,
                    runtime_releases: releases,
                    relevance: calculateRelevance(prDetails.title, query)
                });
            }
        }
    }
    
    // Sort by relevance (higher score = more relevant)
    results.sort((a, b) => b.relevance - a.relevance);
    
    return results;
}

// Calculate relevance score for search results
function calculateRelevance(title, query) {
    const lowerTitle = title.toLowerCase();
    const lowerQuery = query.toLowerCase();
    
    // Exact match gets highest score
    if (lowerTitle === lowerQuery) return 100;
    
    // Start of title match
    if (lowerTitle.startsWith(lowerQuery)) return 90;
    
    // Word boundary match
    const wordBoundaryRegex = new RegExp(`\\b${lowerQuery}\\b`, 'i');
    if (wordBoundaryRegex.test(title)) return 80;
    
    // Contains match (already filtered for this)
    return 50;
}

// Display search results for title search
function displaySearchResults(results, query) {
    let html = `
        <div class="search-results-header">
            <h3>Found ${results.length} PR${results.length !== 1 ? 's' : ''} matching "${query}"</h3>
        </div>
        <div class="search-results-list">
    `;
    
    // Show up to 10 results
    const maxResults = 10;
    const displayResults = results.slice(0, maxResults);
    
    for (const result of displayResults) {
        const { pr_number, pr_details, runtime_releases } = result;
        const releaseCount = runtime_releases.length;
        
        html += `
            <div class="search-result-item" data-pr="${pr_number}">
                <div class="search-result-header">
                    <div class="search-result-title">
                        #${pr_number}: ${pr_details.title}
                    </div>
                    <div class="search-result-meta">
                        <span>by @${pr_details.author || 'unknown'}</span>
                        ${pr_details.merged_at ? `<span>${new Date(pr_details.merged_at).toLocaleDateString()}</span>` : ''}
                    </div>
                </div>
                <div class="search-result-footer">
                    <span class="release-count">In ${releaseCount} release${releaseCount !== 1 ? 's' : ''}</span>
                    <button class="view-details-btn" onclick="viewPRDetails('${pr_number}')">View Details →</button>
                </div>
            </div>
        `;
    }
    
    if (results.length > maxResults) {
        html += `
            <div class="search-results-footer">
                <p>Showing ${maxResults} of ${results.length} results. Try a more specific search term.</p>
            </div>
        `;
    }
    
    html += '</div>';
    prSearchResults.innerHTML = html;
}

// View details for a specific PR (from search results)
window.viewPRDetails = function(prNumber) {
    // Load the PR details
    const prData = {
        pr_details: sdkMappings.pr_details ? sdkMappings.pr_details[prNumber] : null,
        runtime_releases: sdkMappings.pr_to_releases[prNumber]
    };
    displaySDKPRResults(prData, prNumber);
};

// Display original PR that has backports but isn't directly in releases
function displayOriginalPRWithBackports(prNumber, backportNumbers) {
    // Get original PR details if available
    const originalDetails = sdkMappings?.pr_details?.[prNumber];
    
    let html = `
        <div class="sdk-pr-info">
            <div class="sdk-pr-header">
                <div class="sdk-pr-title">SDK PR #${prNumber}${originalDetails ? `: ${originalDetails.title}` : ''}</div>
                <div class="sdk-pr-meta">
                    ${originalDetails ? `<span>by @${originalDetails.author || 'unknown'}</span>` : ''}
                    ${originalDetails?.merged_at ? `<span>Merged: ${new Date(originalDetails.merged_at).toLocaleDateString()}</span>` : ''}
                </div>
                ${originalDetails?.labels && originalDetails.labels.length > 0 ? `
                    <div class="sdk-pr-labels">
                        ${originalDetails.labels.map(label => `<span class="pr-label">${label}</span>`).join('')}
                    </div>
                ` : ''}
            </div>
            <a href="https://github.com/paritytech/polkadot-sdk/pull/${prNumber}" 
               target="_blank" class="sdk-pr-link">
                View on GitHub →
            </a>
        </div>
        
        <div class="runtime-releases">
            <h3>Runtime Releases</h3>
            <p>This PR is not directly included in any runtime releases, but was included through the following backports:</p>
            <div class="backport-releases">
    `;
    
    // Show which backports are in releases
    let foundInRelease = false;
    for (const backportNum of backportNumbers) {
        const backportDetails = sdkMappings?.pr_details?.[backportNum];
        const backportReleases = sdkMappings?.pr_to_releases?.[backportNum];
        
        if (backportReleases && backportReleases.length > 0) {
            foundInRelease = true;
            html += `
                <div class="backport-release-item">
                    <div>Via backport <a href="#" onclick="viewPRDetails('${backportNum}'); return false;">#${backportNum}</a>:</div>
                    ${backportReleases.map(release => `
                        <div class="runtime-release-item" data-version="${release.runtime_version}" style="margin-left: 1rem; margin-top: 0.5rem;">
                            <div class="runtime-release-version">
                                Runtime v${release.runtime_version}
                                <span class="sdk-version-badge">SDK ${release.sdk_version}</span>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
        }
    }
    
    if (!foundInRelease) {
        html += '<p style="color: var(--text-secondary);">None of the backports have been included in runtime releases yet.</p>';
    }
    
    html += `
            </div>
        </div>
    `;
    
    prSearchResults.innerHTML = html;
}

// Display SDK PR results
function displaySDKPRResults(prData, prNumber) {
    const { pr_details, runtime_releases } = prData;
    
    let html = '';
    
    // PR info section
    if (pr_details) {
        // Extract labels for display
        const labels = pr_details.labels || [];
        const labelHtml = labels.length > 0 ? labels.map(label => 
            `<span class="pr-label">${label}</span>`
        ).join('') : '';
        
        // Check if this is a backport
        const isBackport = pr_details.is_backport || false;
        const originalPR = pr_details.original_pr;
        
        // Check if this PR has backports
        const backports = (sdkMappings?.original_to_backports && sdkMappings.original_to_backports[prNumber]) || [];
        
        html += `
            <div class="sdk-pr-info">
                <div class="sdk-pr-header">
                    <div class="sdk-pr-title">SDK PR #${pr_details.number}: ${pr_details.title}</div>
                    <div class="sdk-pr-meta">
                        <span>by @${pr_details.author || 'unknown'}</span>
                        ${pr_details.merged_at ? `<span>Merged: ${new Date(pr_details.merged_at).toLocaleDateString()}</span>` : ''}
                    </div>
                    ${labelHtml ? `<div class="sdk-pr-labels">${labelHtml}</div>` : ''}
                </div>
                
                ${isBackport && originalPR ? `
                    <div class="backport-info">
                        <span class="backport-label">Backport of:</span>
                        <a href="#" onclick="viewPRDetails('${originalPR}'); return false;" class="backport-link">
                            #${originalPR}${sdkMappings?.pr_details?.[originalPR] ? `: ${sdkMappings.pr_details[originalPR].title}` : ''}
                        </a>
                    </div>
                ` : ''}
                
                <a href="${pr_details.url}" target="_blank" class="sdk-pr-link">
                    View on GitHub →
                </a>
            </div>
        `;
    } else {
        html += `
            <div class="sdk-pr-info">
                <div class="sdk-pr-header">
                    <div class="sdk-pr-title">SDK PR #${prNumber}</div>
                </div>
                <a href="https://github.com/paritytech/polkadot-sdk/pull/${prNumber}" 
                   target="_blank" class="sdk-pr-link">
                    View on GitHub →
                </a>
            </div>
        `;
    }
    
    // Runtime releases section
    if (runtime_releases && runtime_releases.length > 0) {
        // Group releases by how they were found
        const releasesByMethod = runtime_releases.reduce((acc, release) => {
            const method = release.included_via || 'unknown';
            if (!acc[method]) acc[method] = [];
            acc[method].push(release);
            return acc;
        }, {});
        
        html += `
            <div class="runtime-releases">
                <h3>Included in ${runtime_releases.length} Runtime Release${runtime_releases.length > 1 ? 's' : ''}:</h3>
                ${runtime_releases.map(release => {
                    // Determine PR type based on release metadata
                    let prType = '';
                    let prTypeClass = '';
                    
                    if (release.is_backport) {
                        prType = 'Backport';
                        prTypeClass = 'backport-badge';
                    } else if (release.from_master) {
                        prType = 'Master';
                        prTypeClass = 'master-badge';
                    } else if (release.is_direct) {
                        prType = 'Direct to ' + release.sdk_branch;
                        prTypeClass = 'direct-badge';
                    } else if (pr_details) {
                        // Fallback to PR details
                        if (pr_details.is_backport) {
                            prType = 'Backport';
                            prTypeClass = 'backport-badge';
                        } else if (pr_details.from_master) {
                            prType = 'Master';
                            prTypeClass = 'master-badge';
                        } else if (pr_details.is_direct) {
                            prType = 'Direct';
                            prTypeClass = 'direct-badge';
                        }
                    }
                    
                    return `
                        <div class="runtime-release-item" data-version="${release.runtime_version}">
                            <div class="runtime-release-version">
                                Runtime v${release.runtime_version}
                                ${release.sdk_version !== 'unknown' ? 
                                    `<span class="sdk-version-badge">SDK ${release.sdk_version}</span>` : ''}
                                ${prType ? 
                                    `<span class="sdk-version-badge ${prTypeClass}">${prType}</span>` : ''}
                            </div>
                            ${release.sdk_version_from ? 
                                `<div class="runtime-release-context">SDK: ${release.sdk_version_from} → ${release.sdk_version}</div>` : ''}
                        </div>
                    `;
                }).join('')}
            </div>
        `;
    } else {
        html += `
            <div class="runtime-releases">
                <h3>Not Yet Included in Runtime Releases</h3>
                <p>This PR hasn't been included in any runtime releases yet.</p>
            </div>
        `;
    }
    
    prSearchResults.innerHTML = html;
    
    // Add click handlers to runtime release items
    document.querySelectorAll('.runtime-release-item').forEach(item => {
        item.addEventListener('click', () => {
            const version = item.dataset.version;
            // Close modal
            prSearchModal.classList.remove('show');
            prSearchResults.innerHTML = '';
            sdkPRInput.value = '';
            // Navigate to the release
            const release = state.releases.find(r => r.tag_name === `v${version}` || r.tag_name === version);
            if (release) {
                loadRelease(release.tag_name);
            }
        });
    });
}

// Search button click handler
searchSDKPRBtn.addEventListener('click', searchSDKPR);

// Enter key handler
sdkPRInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        searchSDKPR();
    }
});

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    init();
    loadSDKMappings();
});

// Handle browser back/forward
window.addEventListener('hashchange', () => {
    const hash = window.location.hash.slice(1);
    if (hash && hash !== state.currentRelease) {
        loadRelease(hash);
    }
});

// Global keyboard shortcuts
document.addEventListener('keydown', (e) => {
    // Cmd/Ctrl + K to open PR search
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        openPRSearchBtn.click();
    }
    
    // Escape to close modal
    if (e.key === 'Escape' && prSearchModal.classList.contains('show')) {
        prSearchModal.classList.remove('show');
        prSearchResults.innerHTML = '';
        sdkPRInput.value = '';
    }
});