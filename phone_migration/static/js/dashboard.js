let deviceStatus = null;
    let options = {
        dry_run: true,  // Default to dry run for safety
        notify: true    // Default to notifications enabled
    };
    let pollInterval = null;
    let isRunning = false;
    let displayedOperations = new Set();
    let manualRules = [];
    let selectedRuleIds = [];
    
    async function loadDeviceStatus() {
        try {
            const status = await apiGet('/api/status');
            deviceStatus = status;
            
            const statusHtml = status.connected
                ? `
                    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">
                        <span class="status-badge connected"><i class="fas fa-check-circle"></i> Connected</span>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; color: #94a3b8;">
                        <div style="display: flex; flex-direction: column; gap: 4px;">
                            <span style="font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px;">Device</span>
                            <span style="font-size: 15px; color: #cbd5e1; font-weight: 500;">${status.device_name}</span>
                        </div>
                        <div style="display: flex; flex-direction: column; gap: 4px;">
                            <span style="font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px;">Profile</span>
                            <span style="font-size: 15px; color: #cbd5e1; font-weight: 500;">${status.profile_name}</span>
                        </div>
                        <div style="display: flex; flex-direction: column; gap: 4px;">
                            <span style="font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px;">Rules</span>
                            <span style="font-size: 15px; color: #cbd5e1; font-weight: 500;">${status.rule_count} configured</span>
                        </div>
                    </div>
                `
                : `
                    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">
                        <span class="status-badge disconnected"><i class="fas fa-times-circle"></i> Disconnected</span>
                    </div>
                    <div style="color: #94a3b8; line-height: 1.8;">
                        <p>No phone connected or device not registered</p>
                        <p style="margin-top: 10px; font-size: 14px; color: #64748b;">
                            <i class="fas fa-info-circle"></i> Connect your phone via USB and enable File Transfer mode
                        </p>
                    </div>
                `;
            
            document.getElementById('device-status').innerHTML = statusHtml;
        } catch (error) {
            document.getElementById('device-status').innerHTML = `
                <div class="alert alert-danger">
                    Error loading device status: ${error.message}
                </div>
            `;
        }
    }
    
    function showAlert(message, type = 'success') {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type}`;
        alertDiv.textContent = message;
        
        const container = document.getElementById('alert-container');
        container.appendChild(alertDiv);
        
        setTimeout(() => alertDiv.remove(), 5000);
    }
    
    function toggleOption(option) {
        if (isRunning) return;
        
        options[option] = !options[option];
        const card = document.getElementById(`${option.replace('_', '-')}-option`);
        
        if (options[option]) {
            card.classList.add('selected');
        } else {
            card.classList.remove('selected');
        }
    }
    
    async function startRun() {
        if (!deviceStatus || !deviceStatus.connected) {
            showAlert('Please connect your phone first', 'danger');
            return;
        }
        
        if (isRunning) return;
        
        isRunning = true;
        const runBtn = document.getElementById('run-btn');
        const manualBtn = document.getElementById('manual-btn');
        runBtn.disabled = true;
        manualBtn.disabled = true;
        runBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Running...';
        
        // Clear previous results immediately
        document.getElementById('stats-card').style.display = 'none';
        document.getElementById('output-card').style.display = 'none';
        document.getElementById('stat-moved').textContent = '0';
        document.getElementById('stat-backed-up').textContent = '0';
        document.getElementById('stat-synced').textContent = '0';
        document.getElementById('stat-errors').textContent = '0';
        
        updateRunStatus('running', 'Running auto rules...');
        document.getElementById('manual-selection-card').style.display = 'none';
        document.getElementById('stats-card').style.display = 'block';
        document.getElementById('output-card').style.display = 'block';
        document.getElementById('operations-container').innerHTML = '';
        displayedOperations.clear();
        
        try {
            const result = await apiPost('/api/run', {
                dry_run: options.dry_run,
                notify: options.notify
            });
            
            if (result.success) {
                startPolling();
            } else {
                throw new Error(result.error || 'Failed to start sync');
            }
        } catch (error) {
            updateRunStatus('error', 'Error: ' + error.message);
            resetRunButton();
        }
    }
    
    function updateRunStatus(type, text) {
        const indicator = document.getElementById('run-status-indicator');
        const statusText = document.getElementById('run-status-text');
        const icon = indicator.querySelector('i');
        
        indicator.className = `status-indicator ${type}`;
        statusText.textContent = text;
        
        if (type === 'running') {
            icon.className = 'fas fa-spinner fa-spin pulse';
            icon.style.color = 'var(--info)';
            statusText.style.color = 'var(--info)';
        } else if (type === 'success') {
            icon.className = 'fas fa-check-circle';
            icon.style.color = 'var(--success)';
            statusText.style.color = 'var(--success)';
        } else if (type === 'error') {
            icon.className = 'fas fa-times-circle';
            icon.style.color = 'var(--danger)';
            statusText.style.color = 'var(--danger)';
        }
    }
    
    function startPolling() {
        pollInterval = setInterval(async () => {
            try {
                const status = await apiGet('/api/run/status');
                
                if (status.stats) {
                    document.getElementById('stat-moved').textContent = status.stats.moved || 0;
                    document.getElementById('stat-backed-up').textContent = status.stats.backed_up || 0;
                    document.getElementById('stat-synced').textContent = status.stats.synced || 0;
                    document.getElementById('stat-errors').textContent = status.stats.errors || 0;
                }
                
                if (status.logs && status.logs.length > 0) {
                    parseAndDisplayOperations(status.logs);
                }
                
                if (!status.running && isRunning) {
                    stopPolling();
                    const hasErrors = status.stats && status.stats.errors > 0;
                    updateRunStatus(hasErrors ? 'error' : 'success', 
                                   hasErrors ? 'Completed with errors' : 'Completed successfully!');
                    resetRunButton();
                }
            } catch (error) {
                console.error('Polling error:', error);
            }
        }, 1000);
    }
    
    function stopPolling() {
        if (pollInterval) {
            clearInterval(pollInterval);
            pollInterval = null;
        }
    }
    
    function parseAndDisplayOperations(logs) {
        const container = document.getElementById('operations-container');
        const fullLog = logs.join('\n');
        const isDryRun = fullLog.includes('[DRY RUN MODE');
        const lines = fullLog.split('\n');
        let currentOp = null;
        
        for (let line of lines) {
            line = line.trim();
            if (!line || line.match(/^[=]+$/)) continue;
            
            const opMatch = line.match(/^[\p{Emoji}\u2192🔄-]*\s*(Move|Copy|Smart Copy|Sync):\s*(.+?)\s*[→\->=>]+\s*(.+)$/u);
            if (opMatch) {
                if (currentOp) displayOperation(container, currentOp, isDryRun);
                const [_, mode, source, dest] = opMatch;
                currentOp = {
                    mode: mode.trim(),
                    source: source.trim(),
                    dest: dest.trim(),
                    stats: {}
                };
                continue;
            }
            
            if (currentOp) {
                const copiedMatch = line.match(/Copied:\s*(\d+)/);
                const skippedMatch = line.match(/Skipped:\s*(\d+)/);
                const deletedMatch = line.match(/Deleted:\s*(\d+)/);
                const syncedMatch = line.match(/Synced:\s*(\d+)/);
                
                if (copiedMatch) currentOp.stats.copied = parseInt(copiedMatch[1]);
                if (skippedMatch) currentOp.stats.skipped = parseInt(skippedMatch[1]);
                if (deletedMatch) currentOp.stats.deleted = parseInt(deletedMatch[1]);
                if (syncedMatch) currentOp.stats.synced = parseInt(syncedMatch[1]);
                const resumedMatch = line.match(/Resumed:\s*(\d+)/);
                const failedMatch = line.match(/Failed:\s*(\d+)/);
                
                if (resumedMatch) currentOp.stats.resumed = parseInt(resumedMatch[1]);
                if (failedMatch) currentOp.stats.failed = parseInt(failedMatch[1]);
            }
        }
        
        if (currentOp) displayOperation(container, currentOp, isDryRun);
        
        if (container.children.length === 0 && fullLog.includes('No changes needed')) {
            container.innerHTML = `
                <div style="text-align: center; padding: 40px; color: var(--text-muted);">
                    <i class="fas fa-check-circle" style="font-size: 48px; color: var(--success); margin-bottom: 16px;"></i>
                    <h3 style="color: var(--text);">No Changes Needed</h3>
                    <p>All files are already in sync</p>
                </div>
            `;
        }
    }
    
    function displayOperation(container, op, isDryRun) {
        const opKey = `${op.mode}-${op.source}-${op.dest}`;
        if (displayedOperations.has(opKey)) return;
        displayedOperations.add(opKey);
        
        const modeClass = op.mode.toLowerCase().replace(' ', '_');
        if (op.stats.resumed > 0) statsHtml += `<div style="display: flex; align-items: center; gap: 6px;"><i class="fas fa-redo" style="color: var(--info);"></i> <span>${op.stats.resumed} resumed</span></div>`;
        if (op.stats.failed > 0) statsHtml += `<div style="display: flex; align-items: center; gap: 6px;"><i class="fas fa-exclamation-triangle" style="color: var(--warning);"></i> <span>${op.stats.failed} failed</span></div>`;
        let statsHtml = '';
        if (op.stats.copied > 0) statsHtml += `<div style="display: flex; align-items: center; gap: 6px;"><i class="fas fa-check" style="color: var(--success);"></i> <span>${op.stats.copied} copied</span></div>`;
        if (op.stats.skipped > 0) statsHtml += `<div style="display: flex; align-items: center; gap: 6px;"><i class="fas fa-forward" style="color: var(--text-muted);"></i> <span>${op.stats.skipped} skipped</span></div>`;
        if (op.stats.deleted > 0) statsHtml += `<div style="display: flex; align-items: center; gap: 6px;"><i class="fas fa-trash" style="color: var(--danger);"></i> <span>${op.stats.deleted} deleted</span></div>`;
        if (op.stats.synced > 0) statsHtml += `<div style="display: flex; align-items: center; gap: 6px;"><i class="fas fa-sync" style="color: var(--info);"></i> <span>${op.stats.synced} synced</span></div>`;
        
        if (!statsHtml) statsHtml = '<div style="color: var(--text-muted);"><i class="fas fa-check-circle"></i> No changes</div>';
        
        const opCard = document.createElement('div');
        opCard.className = 'operation-card';
        opCard.innerHTML = `
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
                <span class="operation-mode ${modeClass}">
                    <i class="fas fa-arrow-right"></i> ${op.mode}
                </span>
                ${isDryRun ? '<span style="background: rgba(245,158,11,0.15); color: var(--warning); padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: 600;"><i class="fas fa-eye"></i> DRY RUN</span>' : ''}
            </div>
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px; font-size: 13px; color: var(--text-muted);">
                <i class="fas fa-mobile-alt"></i> ${op.source} <i class="fas fa-arrow-right"></i> <i class="fas fa-desktop"></i> ${op.dest}
            </div>
            <div style="display: flex; gap: 16px; font-size: 13px;">${statsHtml}</div>
        `;
        container.appendChild(opCard);
    }
    
    function resetRunButton() {
        isRunning = false;
        document.getElementById('run-btn').disabled = false;
        document.getElementById('run-btn').innerHTML = '<i class="fas fa-play"></i> Run All Rules';
        document.getElementById('manual-btn').disabled = false;
        document.getElementById('manual-btn').innerHTML = '<i class="fas fa-hand-paper"></i> Run Manual Rules';
    }
        // Clear previous results
        document.getElementById('stats-card').style.display = 'none';
        document.getElementById('output-card').style.display = 'none';
    
    async function openManualRulesModal() {
        if (!deviceStatus || !deviceStatus.connected) {
            showAlert('Please connect your phone first', 'danger');
            return;
        }
        
        document.getElementById('manual-selection-card').style.display = 'block';
        document.getElementById('run-selected-btn').disabled = true;
        selectedRuleIds = [];
        
        // Scroll to the manual selection card
        document.getElementById('manual-selection-card').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        
        try {
            // Load rules for this profile
            const data = await apiGet(`/api/profiles/${deviceStatus.profile_name}/rules`);
            manualRules = (data.rules || []).filter(r => r.manual_only);
            
            const container = document.getElementById('manual-rules-list');
            
            if (manualRules.length === 0) {
                container.innerHTML = `
                    <div style="text-align: center; padding: 40px; color: var(--text-muted);">
                        <i class="fas fa-hand-paper" style="font-size: 48px; color: var(--icon-idle); margin-bottom: 16px;"></i>
                        <h3>No Manual Rules</h3>
                        <p>All rules are set to run automatically</p>
                    </div>
                `;
                return;
            }
            
            container.innerHTML = manualRules.map(rule => `
                <label class="rule-checkbox-label">
                    <input type="checkbox" value="${rule.id}" onchange="toggleRuleSelection('${rule.id}')">
                    <div style="flex: 1;">
                        <div style="font-weight: 600; color: var(--text); margin-bottom: 4px;">
                            <span class="operation-mode ${rule.mode}" style="margin-right: 8px;">
                                <i class="fas fa-${getModeIcon(rule.mode)}"></i> ${rule.mode.toUpperCase()}
                            </span>
                            ${rule.id}
                        </div>
                        <div style="font-size: 13px; color: var(--text-muted);">
                            <i class="fas fa-mobile-alt" style="width: 16px;"></i> ${rule.phone_path} → 
                            <i class="fas fa-desktop" style="width: 16px;"></i> ${rule.desktop_path}
                        </div>
                    </div>
                </label>
            `).join('');
        } catch (error) {
            showAlert('Failed to load manual rules: ' + error.message, 'danger');
            closeManualSelection();
        }
    }
    
    function closeManualSelection() {
        document.getElementById('manual-selection-card').style.display = 'none';
    }
    
    function toggleRuleSelection(ruleId) {
        const index = selectedRuleIds.indexOf(ruleId);
        if (index === -1) {
            selectedRuleIds.push(ruleId);
        } else {
            selectedRuleIds.splice(index, 1);
        }
        
        // Enable/disable run button based on selection
        const runSelectedBtn = document.getElementById('run-selected-btn');
        if (runSelectedBtn) {
            runSelectedBtn.disabled = selectedRuleIds.length === 0;
        }
    }
    
    async function runSelectedManualRules() {
        if (selectedRuleIds.length === 0) {
            showAlert('Please select at least one rule to run', 'danger');
            return;
        }
        
        closeManualSelection();
        
        // Clear previous results immediately
        document.getElementById('stats-card').style.display = 'none';
        document.getElementById('output-card').style.display = 'none';
        document.getElementById('stat-moved').textContent = '0';
        document.getElementById('stat-backed-up').textContent = '0';
        document.getElementById('stat-synced').textContent = '0';
        document.getElementById('stat-errors').textContent = '0';
        
        // Run with specific rule IDs
        isRunning = true;
        const runBtn = document.getElementById('run-btn');
        const manualBtn = document.getElementById('manual-btn');
        runBtn.disabled = true;
        manualBtn.disabled = true;
        manualBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Running...';
        
        updateRunStatus('running', `Running ${selectedRuleIds.length} manual rule(s)...`);
        document.getElementById('stats-card').style.display = 'block';
        document.getElementById('output-card').style.display = 'block';
        document.getElementById('operations-container').innerHTML = '';
        displayedOperations.clear();
        
        try {
            const result = await apiPost('/api/run', {
                dry_run: options.dry_run,
                rule_ids: selectedRuleIds,
                notify: options.notify
            });
            
            if (result.success) {
                startPolling();
            } else {
                throw new Error(result.error || 'Failed to start sync');
            }
        } catch (error) {
            updateRunStatus('error', 'Error: ' + error.message);
            resetRunButton();
        }
    }
    
    function getModeIcon(mode) {
        return { move: 'arrow-right', copy: 'copy', smart_copy: 'lightbulb', sync: 'sync' }[mode] || 'cog';
    }
    
    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeManualSelection();
        }
    });
    
    // Load on page load
    loadDeviceStatus();
    
    // Auto-refresh every 5 seconds
    setInterval(loadDeviceStatus, 5000);
    
    // Cleanup
    window.addEventListener('beforeunload', () => {
        stopPolling();
    });