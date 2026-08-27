let allHistory = [];
let shownHistory = [];

async function loadHistory() {
    const limit = document.getElementById('filter-limit').value;

    try {
        allHistory = await apiGet(`/api/history?limit=${encodeURIComponent(limit)}`);
        filterHistory();
    } catch (error) {
        showAlert('Failed to load history: ' + error.message, 'error');
    }
}

function filterHistory() {
    const statusFilter = document.getElementById('filter-status').value;

    shownHistory = statusFilter === 'all'
        ? allHistory
        : allHistory.filter(item => item.status === statusFilter);

    displayHistory(shownHistory);
}

const ACTION_ICONS = {
    copied: 'fa-copy',
    moved: 'fa-arrow-right',
    synced: 'fa-sync',
    deleted: 'fa-trash',
    skipped: 'fa-forward',
    renamed: 'fa-pen',
    failed: 'fa-exclamation-triangle',
    folder: 'fa-folder'
};

function renderRuleFiles(rule) {
    const files = rule.files || [];
    if (files.length === 0) {
        return '';
    }

    // ponytail: cap the DOM at 200 rows per rule; the full list stays in the log.
    const rows = files.slice(0, 200).map(file => `
        <div class="history-file">
            <i class="fas ${ACTION_ICONS[file.action] || 'fa-file'}"></i>
            <span class="history-file-action">${escapeHtml(file.action)}</span>
            <span>${escapeHtml(file.src)}</span>
            ${file.dst ? `<i class="fas fa-arrow-right"></i> <span>${escapeHtml(file.dst)}</span>` : ''}
            ${file.error ? `<span style="color: var(--danger);">${escapeHtml(file.error)}</span>` : ''}
        </div>
    `).join('');

    const more = files.length > 200
        ? `<div style="color: var(--text-muted); font-size: 12px;">... and ${files.length - 200} more</div>`
        : '';

    return `
        <div class="history-rule">
            <div class="history-rule-header">
                <strong>${escapeHtml(rule.id)}</strong>
                <span>${escapeHtml(rule.mode)}</span>
                <span>${escapeHtml(rule.phone_path)}</span>
                <i class="fas fa-arrow-right"></i>
                <span>${escapeHtml(rule.desktop_path)}</span>
            </div>
            ${rule.error ? `<div style="color: var(--danger);">${escapeHtml(rule.error)}</div>` : ''}
            ${rows}
            ${more}
        </div>
    `;
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

    container.innerHTML = history.map((item, idx) => {
        const status = item.status || 'unknown';
        const statusIcon = status === 'success' ? 'check-circle'
            : status === 'error' ? 'times-circle' : 'spinner fa-spin';
        const stats = item.stats || {};

        return `
            <div class="history-item">
                <div class="history-header">
                    <div>
                        <span class="history-status ${escapeHtml(status)}">
                            <i class="fas fa-${statusIcon}"></i>
                            ${escapeHtml(status.charAt(0).toUpperCase() + status.slice(1))}
                        </span>
                        ${item.dry_run ? '<span class="badge-dry-run"><i class="fas fa-eye"></i> DRY RUN</span>' : ''}
                    </div>
                    <button class="btn btn-secondary btn-sm" data-toggle-index="${idx}">
                        <i class="fas fa-chevron-down" id="toggle-icon-${idx}"></i>
                    </button>
                </div>

                <div class="history-meta">
                    <span><i class="fas fa-clock"></i>${escapeHtml(formatDate(item.timestamp))}</span>
                    <span><i class="fas fa-mobile-alt"></i>${escapeHtml(item.profile || 'Unknown')}</span>
                    <span><i class="fas fa-tasks"></i>${escapeHtml(item.rules_count || 0)} rule(s)</span>
                </div>

                <div class="history-stats">
                    <div class="stat-item">
                        <i class="fas fa-arrow-right"></i>
                        <span>${escapeHtml(stats.moved || 0)} moved</span>
                    </div>
                    <div class="stat-item">
                        <i class="fas fa-copy"></i>
                        <span>${escapeHtml(stats.backed_up || 0)} backed up</span>
                    </div>
                    <div class="stat-item">
                        <i class="fas fa-sync"></i>
                        <span>${escapeHtml(stats.synced || 0)} synced</span>
                    </div>
                    ${stats.errors ? `
                        <div class="stat-item" style="color: var(--danger);">
                            <i class="fas fa-exclamation-triangle"></i>
                            <span>${escapeHtml(stats.errors)} error(s)</span>
                        </div>
                    ` : ''}
                </div>

                <div class="history-details" id="details-${idx}">
                    ${(item.rules || []).map(renderRuleFiles).join('')}
                    ${item.logs && item.logs.length > 0
                        ? `<pre class="log-preview" data-log-index="${idx}"></pre>`
                        : '<p style="color: var(--text-muted); font-size: 13px;">No logs available</p>'}
                </div>
            </div>
        `;
    }).join('');

    // Log lines are raw CLI output: textContent, never innerHTML.
    container.querySelectorAll('.log-preview').forEach(pre => {
        const entry = history[Number(pre.dataset.logIndex)];
        pre.textContent = (entry.logs || []).join('\n');
    });
}

document.getElementById('history-container').addEventListener('click', (event) => {
    const button = event.target.closest('button[data-toggle-index]');
    if (button) toggleDetails(button.dataset.toggleIndex);
});

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
    const diff = new Date() - date;

    if (isNaN(diff)) {
        return 'Unknown';
    }

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

    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
}

// Initial load
loadHistory();
