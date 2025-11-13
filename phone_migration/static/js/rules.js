let currentProfile = null;
    let profiles = [];
    
    async function loadProfiles() {
        try {
            // Get current device status
            const status = await apiGet('/api/status');
            
            if (!status.connected) {
                document.getElementById('rules-container').innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-mobile-alt" style="font-size: 48px; color: var(--icon-idle); margin-bottom: 16px;"></i>
                        <h3>No Device Connected</h3>
                        <p>Please connect your device to manage rules</p>
                    </div>
                `;
                return;
            }
            
            // Show current profile info
            document.getElementById('profile-info').style.display = 'block';
            document.getElementById('current-profile').textContent = `${status.device_name} (${status.profile_name})`;
            
            // Load rules for connected device's profile
            currentProfile = status.profile_name;
            loadRules();
        } catch (error) {
            showAlert('Failed to load status: ' + error.message, 'danger');
        }
    }
    
    async function loadRules() {
        if (!currentProfile) {
            return;
        }
        
        document.getElementById('rules-container').innerHTML = '<div class="spinner"></div>';
        
        try {
            const data = await apiGet(`/api/profiles/${currentProfile}/rules`);
            const rules = data.rules || [];
            
            if (rules.length === 0) {
                document.getElementById('rules-container').innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-inbox"></i>
                        <p>No rules configured yet</p>
                        <button class="btn" onclick="openAddModal()" style="margin-top: 16px;"><i class="fas fa-plus"></i> Add Your First Rule</button>
                    </div>
                `;
                return;
            }
            
            // Group rules by mode
            const groupedRules = {};
            rules.forEach(rule => {
                if (!groupedRules[rule.mode]) {
                    groupedRules[rule.mode] = [];
                }
                groupedRules[rule.mode].push(rule);
            });
            
            // Order of display
            const modeOrder = ['move', 'copy', 'smart_copy', 'sync'];
            let html = '';
            
            modeOrder.forEach(mode => {
                if (groupedRules[mode] && groupedRules[mode].length > 0) {
                    html += `
                        <div style="margin-bottom: 32px;">
                            <h3 style="font-size: 15px; font-weight: 600; color: var(--text); margin-bottom: 16px; display: flex; align-items: center; gap: 8px;">
                                <i class="fas fa-${getModeIcon(mode)}" style="color: var(--accent);"></i>
                                ${getModeLabel(mode)} Rules
                                <span style="font-size: 13px; color: var(--text-muted); font-weight: 500;">(${groupedRules[mode].length})</span>
                            </h3>
                            <div style="display: grid; gap: 12px;">
                                ${groupedRules[mode].map(rule => `
                                    <div class="rule-card">
                                        <div class="rule-header">
                                            <div style="display: flex; align-items: center; gap: 12px;">
                                                <span class="rule-mode ${rule.mode}">
                                                    <i class="fas fa-${getModeIcon(rule.mode)}"></i>
                                                    ${getModeLabel(rule.mode)}
                                                </span>
                                                ${rule.manual_only ? '<span class="badge-manual"><i class="fas fa-hand-paper"></i> Manual</span>' : ''}
                                            </div>
                                            <span style="color: var(--text-muted); font-size: 13px;">${rule.id}</span>
                                        </div>
                                        
                                        <div class="rule-paths">
                                            <div class="rule-path">
                                                <i class="fas fa-mobile-alt" style="color: var(--icon-idle); width: 16px;"></i>
                                                <span>${rule.phone_path}</span>
                                            </div>
                                            <div class="rule-path" style="color: var(--text-muted); font-size: 13px;">
                                                <i class="fas fa-arrow-down" style="width: 16px;"></i>
                                            </div>
                                            <div class="rule-path">
                                                <i class="fas fa-desktop" style="color: var(--icon-idle); width: 16px;"></i>
                                                <span>${rule.desktop_path.replace(/\/home\/[^\/]+/, '~')}</span>
                                            </div>
                                        </div>
                                        
                                        <div class="rule-actions">
                                            <button class="btn btn-small btn-danger" onclick="deleteRule('${rule.id}')">
                                                <i class="fas fa-trash"></i> Delete
                                            </button>
                                        </div>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    `;
                }
            });
            
            document.getElementById('rules-container').innerHTML = html;
        } catch (error) {
            document.getElementById('rules-container').innerHTML = `<div class="alert alert-danger">Error loading rules: ${error.message}</div>`;
        }
    }
    
    function getModeIcon(mode) {
        const icons = {
            move: 'arrow-right',
            copy: 'copy',
            smart_copy: 'lightbulb',
            sync: 'sync'
        };
        return icons[mode] || 'cog';
    }
    
    function getModeLabel(mode) {
        const labels = {
            move: 'Move',
            copy: 'Copy',
            smart_copy: 'Smart Copy',
            sync: 'Sync'
        };
        return labels[mode] || mode;
    }
    
    function openAddModal() {
        if (!currentProfile) {
            showAlert('Please select a profile first', 'danger');
            return;
        }
        
        document.getElementById('modal-title').textContent = 'Add Rule';
        document.getElementById('rule-form').reset();
        document.getElementById('rule-modal').classList.add('active');
    }
    
    function closeModal() {
        document.getElementById('rule-modal').classList.remove('active');
    }
    
    async function saveRule(event) {
        event.preventDefault();
        
        const mode = document.getElementById('mode').value;
        const phonePath = document.getElementById('phone-path').value;
        const desktopPath = document.getElementById('desktop-path').value;
        const manualOnly = document.getElementById('manual-only').checked;
        
        try {
            const result = await apiPost('/api/rules', {
                profile: currentProfile,
                mode: mode,
                phone_path: phonePath,
                desktop_path: desktopPath,
                manual_only: manualOnly
            });
            
            if (result.success) {
                showAlert('Rule added successfully!', 'success');
                closeModal();
                loadRules();
            } else {
                showAlert(result.error || 'Failed to add rule', 'danger');
            }
        } catch (error) {
            showAlert('Error: ' + error.message, 'danger');
        }
    }
    
    async function deleteRule(ruleId) {
        if (!confirm('Are you sure you want to delete this rule?')) {
            return;
        }
        
        try {
            const result = await apiDelete(`/api/rules/${currentProfile}/${ruleId}`);
            
            if (result.success) {
                showAlert('Rule deleted successfully!', 'success');
                loadRules();
            } else {
                showAlert(result.error || 'Failed to delete rule', 'danger');
            }
        } catch (error) {
            showAlert('Error: ' + error.message, 'danger');
        }
    }
    
    function showAlert(message, type = 'success') {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type}`;
        alertDiv.textContent = message;
        alertDiv.style.marginBottom = '12px';
        
        const container = document.getElementById('alert-container');
        container.appendChild(alertDiv);
        
        setTimeout(() => alertDiv.remove(), 5000);
    }
    
    // Close modal on escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeModal();
        }
    });
    
    // Close modal on backdrop click
    document.getElementById('rule-modal').addEventListener('click', (e) => {
        if (e.target.id === 'rule-modal') {
            closeModal();
        }
    });
    
    // Load profiles on page load
    loadProfiles();
    
    // ========================================
    // Folder Browser Functionality
    // ========================================
    
    let browserState = {
        type: null,  // 'phone' or 'desktop'
        currentPath: null,
        targetInput: null,
        selectedPath: null,
        loading: false,
        showHidden: false
    };
    
    function openPhoneBrowser() {
        const input = document.getElementById('phone-path');
        const initialPath = input.value.trim() || '/';
        
        browserState = {
            type: 'phone',
            currentPath: initialPath,
            targetInput: input,
            selectedPath: null,
            loading: false,
            showHidden: false
        };
        
        // Reset toggle checkbox
        document.getElementById('show-hidden-toggle').checked = false;
        
        document.getElementById('browser-title').textContent = 'Browse Phone Folders';
        document.getElementById('browser-modal').classList.add('active');
        loadBrowserDirectory(initialPath);
    }
    
    function openDesktopBrowser() {
        const input = document.getElementById('desktop-path');
        let initialPath = input.value.trim();
        
        // Start at home directory by default
        if (!initialPath) {
            initialPath = '~';
        }
        
        browserState = {
            type: 'desktop',
            currentPath: initialPath,
            targetInput: input,
            selectedPath: null,
            loading: false,
            showHidden: false
        };
        
        // Reset toggle checkbox
        document.getElementById('show-hidden-toggle').checked = false;
        
        document.getElementById('browser-title').textContent = 'Browse Desktop Folders';
        document.getElementById('browser-modal').classList.add('active');
        loadBrowserDirectory(initialPath);
    }
    
    function closeBrowser() {
        document.getElementById('browser-modal').classList.remove('active');
        browserState = { type: null, currentPath: null, targetInput: null, selectedPath: null, loading: false };
    }
    
    async function loadBrowserDirectory(path) {
        if (browserState.loading) return;
        
        browserState.loading = true;
        browserState.currentPath = path;
        browserState.selectedPath = null;
        
        const listEl = document.getElementById('browser-list');
        listEl.innerHTML = '<div class="spinner"></div>';
        
        try {
            const endpoint = browserState.type === 'phone' ? '/api/browse/phone' : '/api/browse/desktop';
            const params = new URLSearchParams({ path: path || '/' });
            const response = await fetch(`${endpoint}?${params}`);
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to load directory');
            }
            
            // Update current path from response
            browserState.currentPath = data.path;
            
            // Update path input field
            document.getElementById('browser-path-input').value = data.path;
            
            // Render breadcrumbs
            renderBreadcrumbs(data.path);
            
            // Filter entries based on showHidden setting
            let filteredEntries = data.entries;
            if (!browserState.showHidden) {
                filteredEntries = data.entries.filter(entry => !entry.name.startsWith('.'));
            }
            
            // Render entries
            if (filteredEntries.length === 0) {
                const message = data.entries.length > 0 && !browserState.showHidden 
                    ? 'No visible items (all items are hidden)' 
                    : 'This folder is empty';
                listEl.innerHTML = `<div class="browser-empty"><i class="fas fa-folder-open" style="font-size: 48px; color: var(--icon-idle); margin-bottom: 16px;"></i><p>${message}</p></div>`;
            } else {
                const html = filteredEntries.map(entry => {
                    const isDir = entry.type === 'dir';
                    const icon = isDir ? 'fa-folder' : 'fa-file';
                    const disabledClass = isDir ? '' : 'disabled';
                    
                    return `
                        <div class="browser-entry type-${entry.type} ${disabledClass}" 
                             data-path="${escapeHtml(entry.path)}" 
                             data-type="${entry.type}">
                            <i class="fas ${icon}"></i>
                            <span>${escapeHtml(entry.name)}</span>
                        </div>
                    `;
                }).join('');
                
                listEl.innerHTML = html;
                
                // Add click handlers after rendering
                listEl.querySelectorAll('.browser-entry.type-dir').forEach(entryEl => {
                    entryEl.addEventListener('click', function() {
                        const path = this.getAttribute('data-path');
                        const type = this.getAttribute('data-type');
                        handleEntryClick(path, type);
                    });
                });
            }
            
            // Update up button state
            const canGoUp = browserState.type === 'desktop' ? data.canGoUp : (data.path !== '/');
            document.getElementById('btn-up').disabled = !canGoUp;
            
        } catch (error) {
            listEl.innerHTML = `<div class="browser-error"><i class="fas fa-exclamation-triangle"></i> ${escapeHtml(error.message)}</div>`;
        } finally {
            browserState.loading = false;
        }
    }
    
    function handleEntryClick(path, type) {
        if (type !== 'dir') return;
        
        // Check if already selected - if so, navigate into it
        if (browserState.selectedPath === path) {
            loadBrowserDirectory(path);
        } else {
            // Single click - select it
            browserState.selectedPath = path;
            
            // Update UI
            document.querySelectorAll('.browser-entry').forEach(el => {
                el.classList.remove('selected');
            });
            
            const clickedEntry = document.querySelector(`.browser-entry[data-path="${path.replace(/"/g, '\\"')}"]`);
            if (clickedEntry) {
                clickedEntry.classList.add('selected');
            }
        }
    }
    
    function goUpOneLevel() {
        const currentPath = browserState.currentPath;
        
        if (!currentPath || currentPath === '/') {
            return; // Already at root
        }
        
        // Compute parent path
        const parts = currentPath.split('/').filter(p => p);
        parts.pop();
        const parentPath = '/' + parts.join('/');
        
        loadBrowserDirectory(parentPath);
    }
    
    function renderBreadcrumbs(path) {
        const breadcrumbsEl = document.getElementById('browser-breadcrumbs');
        
        if (!path || path === '/') {
            breadcrumbsEl.innerHTML = '<i class="fas fa-home"></i> <span class="breadcrumb-item" data-path="/">Root</span>';
            // Add click handler for root
            breadcrumbsEl.querySelector('.breadcrumb-item').addEventListener('click', () => loadBrowserDirectory('/'));
            return;
        }
        
        const parts = path.split('/').filter(p => p);
        const segments = ['<i class="fas fa-home"></i>', '<span class="breadcrumb-item" data-path="/">Root</span>'];
        
        let accumulated = '';
        parts.forEach((part, index) => {
            accumulated += '/' + part;
            const fullPath = accumulated;
            segments.push('<span class="breadcrumb-separator">/</span>');
            segments.push(`<span class="breadcrumb-item" data-path="${escapeHtml(fullPath)}">${escapeHtml(part)}</span>`);
        });
        
        breadcrumbsEl.innerHTML = segments.join(' ');
        
        // Add click handlers to all breadcrumb items
        breadcrumbsEl.querySelectorAll('.breadcrumb-item').forEach(item => {
            item.addEventListener('click', function() {
                const targetPath = this.getAttribute('data-path');
                loadBrowserDirectory(targetPath);
            });
        });
    }
    
    function selectCurrentPath() {
        const pathToSelect = browserState.selectedPath || browserState.currentPath;
        
        if (!pathToSelect) {
            showAlert('Please select a folder', 'danger');
            return;
        }
        
        if (browserState.targetInput) {
            browserState.targetInput.value = pathToSelect;
        }
        
        closeBrowser();
    }
    
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    function navigateToTypedPath() {
        const pathInput = document.getElementById('browser-path-input');
        const path = pathInput.value.trim();
        
        if (path) {
            loadBrowserDirectory(path);
        }
    }
    
    function toggleHiddenFiles() {
        const checkbox = document.getElementById('show-hidden-toggle');
        browserState.showHidden = checkbox.checked;
        
        // Reload current directory with new filter
        if (browserState.currentPath) {
            loadBrowserDirectory(browserState.currentPath);
        }
    }
    
    async function showCreateFolderPrompt() {
        const folderName = prompt('Enter new folder name:');
        
        if (!folderName || !folderName.trim()) {
            return;
        }
        
        const newFolderPath = browserState.currentPath + (browserState.currentPath.endsWith('/') ? '' : '/') + folderName.trim();
        
        try {
            // For desktop, we can create folders via an API endpoint
            if (browserState.type === 'desktop') {
                const response = await fetch('/api/folder/create', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ path: newFolderPath })
                });
                
                const result = await response.json();
                
                if (response.ok && result.success) {
                    showAlert('Folder created successfully!', 'success');
                    // Refresh current directory
                    loadBrowserDirectory(browserState.currentPath);
                } else {
                    showAlert(result.error || 'Failed to create folder', 'danger');
                }
            } else {
                showAlert('Creating folders on phone is not supported yet', 'info');
            }
        } catch (error) {
            showAlert('Error: ' + error.message, 'danger');
        }
    }
    
    // Close browser on ESC key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && browserState.type) {
            closeBrowser();
        }
    });
    
    // Close browser on backdrop click
    document.getElementById('browser-modal').addEventListener('click', (e) => {
        if (e.target.id === 'browser-modal') {
            closeBrowser();
        }
    });