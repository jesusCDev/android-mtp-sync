let allHistory = [];
    
    async function loadHistory() {
        const limit = document.getElementById('filter-limit').value;
        
        try {
            allHistory = await apiGet(`/api/history?limit=${limit}`);
            filterHistory();
        } catch (error) {
            showAlert('Failed to load history: ' + error.message, 'error');
        }
    }
    
    function filterHistory() {
        const statusFilter = document.getElementById('filter-status').value;
        
        let filtered = allHistory;
        if (statusFilter !== 'all') {
            filtered = allHistory.filter(item => item.status === statusFilter);
        }
        
        displayHistory(filtered);
    }
    
    function displayHistory(history) {
        const container = document.getElementById('history-container');
        
        if (history.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-history" style="font-size: 48px; color: var(--icon-idle); margin-bottom: 16px;"></i>
                    <h3>No History</h3>
                    <p>Run some operations to see them here</p>
                </div>
            `;
            return;
        }
        
        container.innerHTML = history.map((item, idx) => `
            <div class="history-item">
                <div class="history-header">
                    <div>
                        <span class="history-status ${item.status}">
                            <i class="fas fa-${item.status === 'success' ? 'check-circle' : item.status === 'error' ? 'times-circle' : 'spinner fa-spin'}"></i>
                            ${item.status.charAt(0).toUpperCase() + item.status.slice(1)}
                        </span>
                    </div>
                    <button class="btn btn-secondary btn-sm" onclick="toggleDetails(${idx})">
                        <i class="fas fa-chevron-down" id="toggle-icon-${idx}"></i>
                    </button>
                </div>
                
                <div class="history-meta">
                    <span><i class="fas fa-clock"></i>${formatDate(item.timestamp)}</span>
                    <span><i class="fas fa-mobile-alt"></i>${item.profile || 'Unknown'}</span>
                    <span><i class="fas fa-tasks"></i>${item.rules_count || 0} rule(s)</span>
                </div>
                
                <div class="history-stats">
                    <div class="stat-item">
                        <i class="fas fa-arrow-right"></i>
                        <span>${item.stats?.moved || 0} moved</span>
                    </div>
                    <div class="stat-item">
                        <i class="fas fa-copy"></i>
                        <span>${item.stats?.backed_up || 0} backed up</span>
                    </div>
                    <div class="stat-item">
                        <i class="fas fa-sync"></i>
                        <span>${item.stats?.synced || 0} synced</span>
                    </div>
                    ${item.stats?.errors ? `
                        <div class="stat-item" style="color: var(--danger);">
                            <i class="fas fa-exclamation-triangle"></i>
                            <span>${item.stats.errors} error(s)</span>
                        </div>
                    ` : ''}
                </div>
                
                <div class="history-details" id="details-${idx}">
                    ${item.logs && item.logs.length > 0 ? `
                        <div class="log-preview">${item.logs.join('\n')}</div>
                    ` : '<p style="color: var(--text-muted); font-size: 13px;">No logs available</p>'}
                </div>
            </div>
        `).join('');
    }
    
    function toggleDetails(idx) {
        const details = document.getElementById(`details-${idx}`);
        const icon = document.getElementById(`toggle-icon-${idx}`);
        
        if (details.classList.contains('show')) {
            details.classList.remove('show');
            icon.className = 'fas fa-chevron-down';
        } else {
            details.classList.add('show');
            icon.className = 'fas fa-chevron-up';
        }
    }
    
    function formatDate(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diff = now - date;
        
        // Less than 1 minute
        if (diff < 60000) {
            return 'Just now';
        }
        
        // Less than 1 hour
        if (diff < 3600000) {
            const mins = Math.floor(diff / 60000);
            return `${mins} minute${mins > 1 ? 's' : ''} ago`;
        }
        
        // Less than 24 hours
        if (diff < 86400000) {
            const hours = Math.floor(diff / 3600000);
            return `${hours} hour${hours > 1 ? 's' : ''} ago`;
        }
        
        // Less than 7 days
        if (diff < 604800000) {
            const days = Math.floor(diff / 86400000);
            return `${days} day${days > 1 ? 's' : ''} ago`;
        }
        
        // Format as date
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
    }
    
    // Initial load
    loadHistory();