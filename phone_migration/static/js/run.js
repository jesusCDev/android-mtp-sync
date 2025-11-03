let options = {
        dry_run: true,  // Default to dry run for safety
        notify: true    // Default to notifications enabled
    };
    let pollInterval = null;
    let isRunning = false;
    let manualRules = [];
    let selectedRuleIds = [];
    
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
    
    async function startRun(manualOnly = false) {
        if (isRunning) return;
        
        isRunning = true;
        const runBtn = document.getElementById('run-btn');
        const manualBtn = document.getElementById('manual-btn');
        runBtn.disabled = true;
        manualBtn.disabled = true;
        
        if (manualOnly) {
            manualBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Running...';
        } else {
            runBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Running...';
        }
        
        // Show status and clear previous output
        updateStatus('running', manualOnly ? 'Running manual rules...' : 'Running auto rules...');
        document.getElementById('stats-card').style.display = 'block';
        document.getElementById('output-card').style.display = 'block';
        document.getElementById('operations-container').innerHTML = '';
        document.getElementById('manual-selection-card').style.display = 'none';
        displayedOperations.clear(); // Clear displayed operations set
        
        try {
            const result = await apiPost('/api/run', {
                dry_run: options.dry_run,
                include_manual: manualOnly,
                notify: options.notify
            });
            
            if (result.success) {
                startPolling();
            } else {
                throw new Error(result.error || 'Failed to start sync');
            }
        } catch (error) {
            updateStatus('error', 'Error: ' + error.message);
            resetRunButton();
        }
    }
    
    function startPolling() {
        pollInterval = setInterval(async () => {
            try {
                const status = await apiGet('/api/run/status');
                console.log('Poll status:', status);
                
                // Update stats
                if (status.stats) {
                    document.getElementById('stat-moved').textContent = status.stats.moved || 0;
                    document.getElementById('stat-backed-up').textContent = status.stats.backed_up || 0;
                    document.getElementById('stat-synced').textContent = status.stats.synced || 0;
                    document.getElementById('stat-errors').textContent = status.stats.errors || 0;
                }
                
                // Parse and display structured output
                if (status.logs && status.logs.length > 0) {
                    console.log('Got logs, length:', status.logs.length);
                    parseAndDisplayOperations(status.logs);
                } else {
                    console.log('No logs in status');
                }
                
                // Check if finished
                if (!status.running && isRunning) {
                    stopPolling();
                    const hasErrors = status.stats && status.stats.errors > 0;
                    if (hasErrors) {
                        updateStatus('error', 'Completed with errors');
                    } else {
                        updateStatus('success', 'Completed successfully!');
                    }
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
    
    function updateStatus(type, text) {
        const indicator = document.getElementById('status-indicator');
        const statusText = document.getElementById('status-text');
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
    
    let displayedOperations = new Set();
    let parsedOutput = { header: '', operations: [], summary: '', isDryRun: false };
    
    function parseAndDisplayOperations(logs) {
        const container = document.getElementById('operations-container');
        const fullLog = logs.join('\n');
        
        // Check if dry run
        const isDryRun = fullLog.includes('[DRY RUN MODE');
        
        // Parse each line for operations
        const lines = fullLog.split('\n');
        let currentOp = null;
        let inOperation = false;
        
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i].trim();
            
            // Skip empty lines and separators
            if (!line || line.match(/^[=]+$/)) continue;
            
            // Detect operation start (Move, Copy, Sync, etc.)
            // Match various arrow/emoji prefixes and arrow characters
            const opMatch = line.match(/^[\p{Emoji}\u2192🔄-]*\s*(Move|Copy|Smart Copy|Sync):\s*(.+?)\s*[→\->=>]+\s*(.+)$/u);
            if (opMatch) {
                console.log('Found operation:', opMatch);
                // Save previous operation if exists
                if (currentOp) {
                    displayOperation(container, currentOp, isDryRun);
                }
                
                const [_, mode, source, dest] = opMatch;
                currentOp = {
                    mode: mode.trim(),
                    source: source.trim(),
                    dest: dest.trim(),
                    files: [],
                    stats: {}
                };
                inOperation = true;
                continue;
            }
            
            if (inOperation && currentOp) {
                // Parse file operations
                if (line.includes('Copying:') || line.includes('Skipped:') || line.includes('Would copy:')) {
                    const fileMatch = line.match(/(?:Copying|Skipped|Would copy):\s*(.+?)\s*→/);
                    if (fileMatch) {
                        const fileName = fileMatch[1].trim();
                        const action = line.includes('Skipped') ? 'skipped' : 
                                     line.includes('Would copy') ? 'would-copy' : 'copying';
                        currentOp.files.push({ name: fileName, action });
                    }
                }
                
                // Parse stats
                const copiedMatch = line.match(/Copied:\s*(\d+)/);
                const skippedMatch = line.match(/Skipped:\s*(\d+)/);
                const deletedMatch = line.match(/Deleted:\s*(\d+)/);
                const renamedMatch = line.match(/Renamed:\s*(\d+)/);
                const syncedMatch = line.match(/Synced:\s*(\d+)/);
                const cleanedMatch = line.match(/Cleaned:\s*(\d+)/);
                
                if (copiedMatch) currentOp.stats.copied = parseInt(copiedMatch[1]);
                if (skippedMatch) currentOp.stats.skipped = parseInt(skippedMatch[1]);
                if (deletedMatch) currentOp.stats.deleted = parseInt(deletedMatch[1]);
                if (renamedMatch) currentOp.stats.renamed = parseInt(renamedMatch[1]);
                if (syncedMatch) currentOp.stats.synced = parseInt(syncedMatch[1]);
                if (cleanedMatch) currentOp.stats.cleaned = parseInt(cleanedMatch[1]);
            }
        }
        
        // Display last operation
        if (currentOp) {
            displayOperation(container, currentOp, isDryRun);
        }
        
        // Show message if no operations found
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
        const modeIcon = getModeIcon(modeClass);
        
        // Build stats display
        let statsHtml = '';
        if (op.stats.copied > 0) statsHtml += `<div class="operation-stat"><i class="fas fa-check" style="color: var(--success);"></i> <span>${op.stats.copied} copied</span></div>`;
        if (op.stats.skipped > 0) statsHtml += `<div class="operation-stat"><i class="fas fa-forward" style="color: var(--text-muted);"></i> <span>${op.stats.skipped} skipped</span></div>`;
        if (op.stats.deleted > 0) statsHtml += `<div class="operation-stat"><i class="fas fa-trash" style="color: var(--danger);"></i> <span>${op.stats.deleted} deleted</span></div>`;
        if (op.stats.synced > 0) statsHtml += `<div class="operation-stat"><i class="fas fa-sync" style="color: var(--info);"></i> <span>${op.stats.synced} synced</span></div>`;
        if (op.stats.cleaned > 0) statsHtml += `<div class="operation-stat"><i class="fas fa-broom" style="color: var(--warning);"></i> <span>${op.stats.cleaned} cleaned</span></div>`;
        
        // Show no changes message if all stats are 0
        if (!statsHtml) {
            statsHtml = '<div class="operation-stat" style="color: var(--text-muted);"><i class="fas fa-check-circle"></i> <span>No changes</span></div>';
        }
        
        const opCard = document.createElement('div');
        opCard.className = 'operation-card';
        opCard.innerHTML = `
            <div class="operation-header">
                <span class="operation-mode ${modeClass}">
                    <i class="fas fa-${modeIcon}"></i> ${op.mode}
                </span>
                ${isDryRun ? '<span style="background: rgba(245,158,11,0.15); color: var(--warning); padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: 600;"><i class="fas fa-eye"></i> DRY RUN</span>' : ''}
            </div>
            <div class="operation-paths">
                <i class="fas fa-mobile-alt" style="color: var(--icon-idle);"></i>
                <span style="color: var(--text);">${op.source}</span>
                <i class="fas fa-arrow-right" style="color: var(--text-muted);"></i>
                <i class="fas fa-desktop" style="color: var(--icon-idle);"></i>
                <span style="color: var(--text);">${op.dest}</span>
            </div>
            ${op.files.length > 0 ? `
                <details style="margin: 12px 0;">
                    <summary style="cursor: pointer; color: var(--text-muted); font-size: 13px; margin-bottom: 8px;">
                        <i class="fas fa-chevron-right" style="transition: transform 170ms; margin-right: 6px;"></i>
                        ${op.files.length} file(s)
                    </summary>
                    <div style="padding-left: 20px; max-height: 200px; overflow-y: auto;">
                        ${op.files.map(f => `
                            <div style="font-size: 12px; color: var(--text-muted); padding: 4px 0; font-family: monospace;">
                                <i class="fas fa-${f.action === 'skipped' ? 'forward' : 'file'}" style="width: 14px; color: ${f.action === 'skipped' ? 'var(--text-muted)' : 'var(--accent)'};">
                                </i> ${f.name}
                            </div>
                        `).join('')}
                    </div>
                </details>
            ` : ''}
            <div class="operation-stats">${statsHtml}</div>
        `;
        container.appendChild(opCard);
        
        // Animate chevron on details toggle
        const details = opCard.querySelector('details');
        if (details) {
            details.addEventListener('toggle', (e) => {
                const chevron = e.target.querySelector('.fa-chevron-right');
                chevron.style.transform = e.target.open ? 'rotate(90deg)' : 'rotate(0deg)';
            });
        }
    }
    
    function getModeIcon(mode) {
        return { move: 'arrow-right', copy: 'copy', smart_copy: 'lightbulb', sync: 'sync' }[mode] || 'cog';
    }
    
    function resetRunButton() {
        isRunning = false;
        document.getElementById('run-btn').disabled = false;
        document.getElementById('run-btn').innerHTML = '<i class="fas fa-play"></i> Run Auto Rules';
        document.getElementById('manual-btn').disabled = false;
        document.getElementById('manual-btn').innerHTML = '<i class="fas fa-hand-paper"></i> Run Manual Rules';
    }
    
    async function openManualRulesModal() {
        document.getElementById('manual-selection-card').style.display = 'block';
        selectedRuleIds = [];
        
        try {
            // Get current device status to find profile
            const status = await apiGet('/api/status');
            if (!status.connected) {
                showAlert('No device connected', 'error');
                closeManualSelection();
                return;
            }
            
            // Load rules for this profile
            const data = await apiGet(`/api/profiles/${status.profile_name}/rules`);
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
            showAlert('Failed to load manual rules: ' + error.message, 'error');
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
    }
    
    async function runSelectedManualRules() {
        if (selectedRuleIds.length === 0) {
            showAlert('Please select at least one rule to run', 'error');
            return;
        }
        
        closeManualSelection();
        
        // Run with specific rule IDs
        isRunning = true;
        const runBtn = document.getElementById('run-btn');
        const manualBtn = document.getElementById('manual-btn');
        runBtn.disabled = true;
        manualBtn.disabled = true;
        manualBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Running...';
        
        updateStatus('running', `Running ${selectedRuleIds.length} manual rule(s)...`);
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
            updateStatus('error', 'Error: ' + error.message);
            resetRunButton();
        }
    }
    
    function showAlert(message, type) {
        // Simple alert for now
        alert(message);
    }
    
    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeManualSelection();
        }
    });
    
    // Cleanup on page unload
    window.addEventListener('beforeunload', () => {
        stopPolling();
    });