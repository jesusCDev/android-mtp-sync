let deviceStatus = null;
    let options = {
        dry_run: true,           // Default to dry run for safety
        notify: true,            // Default to notifications enabled
        rename_duplicates: true  // Default to renaming duplicates on conflict
    };
    let pollInterval = null;
    let isRunning = false;
    let displayedOperations = new Set();
    let manualRules = [];
    let selectedRuleIds = [];
    let previewExpanded = false;
    let previewLoaded = false;
    let currentPreviewType = null;  // 'auto' or 'manual'
    let allRules = [];  // Store all rules for preview
    
    function openAddModalForDevice(deviceName, mtpId, idType, idValue) {
        // Store device info in window so profiles.js can access it
        window.prefilledDevice = {
            name: deviceName,
            mtp_id: mtpId,
            id_type: idType,
            id_value: idValue
        };
        
        // Navigate to profiles page and open modal
        window.location.href = '/profiles';
    }
    
    async function loadDeviceStatus() {
        try {
            const status = await apiGet('/api/status');
            deviceStatus = status;
            
            // Update button state based on connection AND accessibility
            const runBtn = document.getElementById('run-btn');
            const manualBtn = document.getElementById('manual-btn');
            const isReady = status.connected && status.accessible;
            if (runBtn) runBtn.disabled = !isReady;
            if (manualBtn) manualBtn.disabled = !isReady;
            
            let statusHtml = '';
            
            // Add MTP exclusivity warning at the top
            const warningBanner = `
                <div style="background: rgba(255, 193, 7, 0.15); border: 1.5px solid #ffc107; border-radius: var(--radius-card); padding: 12px; margin-bottom: 16px;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <i class="fas fa-info-circle" style="color: #ffc107; font-size: 16px;"></i>
                        <span style="color: #ffc107; font-size: 13px;">
                            <strong>⚠️ MTP Limitation:</strong> Close all file managers (Nemo, Dolphin, etc.) before using this tool. Only one app can access your phone at a time.
                            <a href="#" onclick="alert('To fix:\n1. killall nemo dolphin nautilus pcmanfm thunar\n2. systemctl --user restart gvfs-daemon\n3. Reconnect your phone'); return false;" style="color: #ffc107; text-decoration: underline; margin-left: 8px;">How to fix →</a>
                        </span>
                    </div>
                </div>
            `;
            
            if (status.connected && status.accessible) {
                // Device connected and accessible - all good
                statusHtml = warningBanner + `
                    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">
                        <span class="status-badge connected"><i class="fas fa-check-circle"></i> Connected & Ready</span>
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
                `;
            } else if (status.connected && !status.accessible) {
                // Device connected but filesystem not accessible
                statusHtml = warningBanner + `
                    <div style="background: rgba(255, 107, 107, 0.15); border: 1.5px solid #ff6b6b; border-radius: var(--radius-card); padding: 16px;">
                        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
                            <i class="fas fa-exclamation-circle" style="color: #ff6b6b; font-size: 18px;"></i>
                            <span style="color: #ff6b6b; font-weight: 600; font-size: 15px;">Device Connected But Not Accessible</span>
                        </div>
                        <p style="color: #cbd5e1; margin: 8px 0; font-size: 14px;">
                            <strong>Device:</strong> ${status.device_name} (${status.profile_name})
                        </p>
                        <p style="color: #94a3b8; margin: 8px 0 12px 0; font-size: 13px;">
                            The device is detected but its filesystem cannot be accessed. This usually means:
                        </p>
                        <ul style="color: #94a3b8; margin: 8px 0 12px 16px; font-size: 13px;">
                            <li>Phone is locked or in sleep mode</li>
                            <li>USB connection is unstable</li>
                            <li>Device needs to confirm "Allow access" prompt</li>
                            <li>MTP drivers need to be reconnected</li>
                        </ul>
                        <p style="color: #94a3b8; margin: 8px 0 12px 0; font-size: 13px;">
                            <strong>Try:</strong> Unlock your phone, check File Transfer mode is enabled, and reconnect the USB cable.
                        </p>
                        <div style="background: rgba(255, 107, 107, 0.25); border: 1px solid rgba(255, 107, 107, 0.5); border-radius: 4px; padding: 8px; margin-top: 8px; font-size: 12px; color: #ff6b6b;">
                            <i class="fas fa-lock"></i> Rules are disabled until device becomes accessible
                        </div>
                    </div>
                `;
            } else {
                // Check for unregistered devices
                try {
                    const unregistered = await apiGet('/api/device/unregistered');
                    if (unregistered.length > 0) {
                        const device = unregistered[0];
                        statusHtml = `
                            <div style="background: rgba(255, 214, 153, 0.15); border: 1.5px solid var(--warning); border-radius: var(--radius-card); padding: 16px; margin-bottom: 16px;">
                                <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
                                    <i class="fas fa-exclamation-triangle" style="color: var(--warning); font-size: 18px;"></i>
                                    <span style="color: var(--warning); font-weight: 600; font-size: 15px;">Device Connected But Not Registered</span>
                                </div>
                                <p style="color: #cbd5e1; margin: 8px 0; font-size: 14px;">
                                    <strong>Device:</strong> ${device.device_name}
                                </p>
                                <p style="color: #94a3b8; margin: 8px 0 12px 0; font-size: 13px;">
                                    This device needs to be registered as a profile to use the sync tool.
                                </p>
                                <button onclick="openAddModalForDevice('${device.device_name}', '${device.mtp_id}', '${device.id_type}', '${device.id_value}')" class="btn btn-small" style="background: var(--warning); color: #1e293b;">
                                    <i class="fas fa-plus"></i> Register Device
                                </button>
                            </div>
                        `;
                    } else {
                        statusHtml = `
                            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">
                                <span class="status-badge disconnected"><i class="fas fa-times-circle"></i> Disconnected</span>
                            </div>
                            <div style="color: #94a3b8; line-height: 1.8;">
                                <p><strong>No device connected</strong></p>
                                <p style="margin-top: 10px; font-size: 14px; color: #64748b;">
                                    <i class="fas fa-info-circle"></i> Connect your phone via USB and enable File Transfer mode
                                </p>
                            </div>
                        `;
                    }
                } catch (e) {
                    statusHtml = `
                        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">
                            <span class="status-badge disconnected"><i class="fas fa-times-circle"></i> Disconnected</span>
                        </div>
                        <div style="color: #94a3b8; line-height: 1.8;">
                            <p><strong>No device connected or profile not configured</strong></p>
                            <p style="margin-top: 10px; font-size: 14px; color: #64748b;">
                                <i class="fas fa-info-circle"></i> Connect your phone via USB and enable File Transfer mode
                            </p>
                        </div>
                    `;
                }
            }
            
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
        
        // Update command preview dynamically
        updateCommandPreview();
    }
    
    function updateCommandPreview() {
        const previewContent = document.getElementById('command-preview-content');
        if (previewContent) {
            previewContent.innerHTML = buildCommandPreview(options.dry_run);
        }
    }
    
    function updateManualCommandPreview() {
        const previewDiv = document.getElementById('manual-command-preview');
        const previewContent = document.getElementById('manual-command-preview-content');
        
        if (selectedRuleIds.length > 0) {
            previewDiv.style.display = 'block';
            previewContent.innerHTML = buildCommandPreview(options.dry_run, selectedRuleIds);
        } else {
            previewDiv.style.display = 'none';
        }
    }
    
    function buildCommandPreview(isDryRun, selectedRules = []) {
        let html = '<div class="command-preview">';
        
        // Build command parts
        const parts = ['phone-sync', '--run'];
        if (isDryRun) {
            parts.push('--dry-run');
        } else {
            parts.push('-y');
        }
        
        if (options.notify) {
            parts.push('--notify');
        }
        
        // Add to HTML
        html += '<div class="command-line">';
        html += `<span class="command-prompt">$</span>`;
        html += '<span class="command-text">';
        
        for (let i = 0; i < parts.length; i++) {
            if (i > 0) html += ' ';
            
            if (parts[i] === '--dry-run') {
                html += `<span class="command-dry-run">${parts[i]}</span>`;
            } else if (parts[i].startsWith('-')) {
                html += `<span class="command-flag">${parts[i]}</span>`;
            } else if (i === 0 || parts[i - 1].startsWith('-')) {
                html += `<span class="command-text">${parts[i]}</span>`;
            } else {
                html += parts[i];
            }
        }
        
        html += '</span></div>';
        
        // Add selected rules if manual
        if (selectedRules.length > 0) {
            html += '<div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid rgba(255,255,255,0.1);">';
            html += '<div style="font-size: 12px; color: var(--text-muted); margin-bottom: 8px;"><i class="fas fa-check"></i> Selected Rules:</div>';
            selectedRules.forEach(id => {
                html += `<div style="font-size: 13px; color: var(--text); font-family: monospace; margin-left: 16px;">- ${id}</div>`;
            });
            html += '</div>';
        }
        
        // Add warning if not dry run
        if (!isDryRun) {
            html += `
                <div class="command-warning">
                    <i class="fas fa-exclamation-triangle command-warning-icon"></i>
                    <span style="color: var(--warning);"><strong>⚡ This will EXECUTE operations.</strong> Files will be moved, copied, or synced.</span>
                </div>
            `;
        } else {
            html += `
                <div style="background: rgba(96, 165, 250, 0.1); border: 1px solid rgba(96, 165, 250, 0.3); border-radius: var(--radius-card); padding: 12px; margin-top: 12px; font-size: 13px;">
                    <i class="fas fa-eye" style="color: var(--info); margin-right: 8px;"></i>
                    <span style="color: var(--info);"><strong>👁️ Preview mode.</strong> No files will be modified.</span>
                </div>
            `;
        }
        
        html += '</div>';
        return html;
    }
    
    async function loadRulesPreview(type = 'auto') {
        if (!deviceStatus || !deviceStatus.connected) {
            return;
        }
        
        currentPreviewType = type;
        
        try {
            // Load rules for the current profile
            const data = await apiGet(`/api/profiles/${deviceStatus.profile_name}/rules`);
            allRules = data.rules || [];
            
            let rulesToShow = [];
            let title = '';
            
            if (type === 'auto') {
                // Filter non-manual rules
                rulesToShow = allRules.filter(r => !r.manual_only);
                title = `Auto Rules (${rulesToShow.length})`;
            } else {
                // Show selected manual rules or all manual rules
                if (selectedRuleIds.length > 0) {
                    rulesToShow = allRules.filter(r => selectedRuleIds.includes(r.id));
                    title = `Selected Manual Rules (${rulesToShow.length})`;
                } else {
                    rulesToShow = allRules.filter(r => r.manual_only);
                    title = `All Manual Rules (${rulesToShow.length})`;
                }
            }
            
            if (rulesToShow.length === 0) {
                document.getElementById('rules-preview-title').textContent = `No ${type === 'auto' ? 'auto' : 'manual'} rules configured`;
                document.getElementById('rules-preview-content').innerHTML = '<div style="padding: 20px; text-align: center; color: var(--text-muted); font-size: 12px;">No rules to display</div>';
                previewLoaded = true;
                return;
            }
            
            // Build preview HTML
            document.getElementById('rules-preview-title').textContent = title;
            const previewContent = document.getElementById('rules-preview-content');
            
            // Show current options at the top
            let optionsHtml = '<div style="background: rgba(0,0,0,0.4); border: 1px solid rgba(255,255,255,0.15); border-radius: 6px; padding: 10px; margin-bottom: 12px; font-size: 12px;">';
            optionsHtml += '<div style="color: var(--text-muted); margin-bottom: 6px; font-weight: 600;"><i class="fas fa-cog"></i> Run Options:</div>';
            optionsHtml += '<div style="display: flex; gap: 12px; flex-wrap: wrap;">';
            
            if (options.dry_run) {
                optionsHtml += '<span style="background: rgba(96,165,250,0.2); color: var(--info); padding: 3px 8px; border-radius: 4px;"><i class="fas fa-eye"></i> Dry Run</span>';
            } else {
                optionsHtml += '<span style="background: rgba(245,158,11,0.2); color: var(--warning); padding: 3px 8px; border-radius: 4px;"><i class="fas fa-exclamation-triangle"></i> Live Execution</span>';
            }
            
            if (options.notify) {
                optionsHtml += '<span style="background: rgba(34,197,94,0.2); color: var(--success); padding: 3px 8px; border-radius: 4px;"><i class="fas fa-bell"></i> Notifications</span>';
            }
            
            if (options.rename_duplicates) {
                optionsHtml += '<span style="background: rgba(34,197,94,0.2); color: var(--success); padding: 3px 8px; border-radius: 4px;"><i class="fas fa-copy"></i> Rename Conflicts</span>';
            } else {
                optionsHtml += '<span style="background: rgba(100,116,139,0.2); color: var(--text-muted); padding: 3px 8px; border-radius: 4px;"><i class="fas fa-forward"></i> Skip Conflicts</span>';
            }
            
            optionsHtml += '</div></div>';
            
            previewContent.innerHTML = optionsHtml + rulesToShow.map(rule => {
                const modeClass = rule.mode || 'unknown';
                const modeIcon = getModeIcon(modeClass);
                return `
                    <div style="background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; padding: 12px; margin-bottom: 8px;">
                        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                            <span class="operation-mode ${modeClass}" style="font-size: 11px; padding: 3px 8px;">
                                <i class="fas fa-${modeIcon}"></i> ${rule.mode.toUpperCase()}
                            </span>
                            <span style="font-size: 12px; color: var(--text-muted); font-family: monospace;">${rule.id}</span>
                        </div>
                        <div style="font-size: 12px; color: var(--text); display: flex; align-items: center; gap: 8px;">
                            <i class="fas fa-mobile-alt" style="width: 14px; color: var(--info);"></i>
                            <span style="flex: 1; overflow: hidden; text-overflow: ellipsis;">${rule.phone_path}</span>
                        </div>
                        <div style="font-size: 12px; color: var(--text); display: flex; align-items: center; gap: 8px; margin-top: 4px;">
                            <i class="fas fa-desktop" style="width: 14px; color: var(--success);"></i>
                            <span style="flex: 1; overflow: hidden; text-overflow: ellipsis;">${rule.desktop_path}</span>
                        </div>
                    </div>
                `;
            }).join('');
            
            previewLoaded = true;
            
        } catch (error) {
            console.error('Failed to load rules preview:', error);
            document.getElementById('rules-preview-title').textContent = 'Error loading rules';
            document.getElementById('rules-preview-content').innerHTML = '<div style="padding: 20px; text-align: center; color: var(--danger); font-size: 12px;">Failed to load rules</div>';
            previewLoaded = true;
        }
    }
    
    async function toggleRulesPreview() {
        const content = document.getElementById('rules-preview-content');
        const chevron = document.getElementById('preview-chevron');
        
        if (previewExpanded) {
            // Collapse
            content.style.display = 'none';
            chevron.style.transform = 'rotate(0deg)';
            previewExpanded = false;
        } else {
            // Expand - load if not loaded yet
            if (!previewLoaded || currentPreviewType !== (selectedRuleIds.length > 0 ? 'manual' : 'auto')) {
                await loadRulesPreview(selectedRuleIds.length > 0 ? 'manual' : 'auto');
            }
            content.style.display = 'block';
            chevron.style.transform = 'rotate(180deg)';
            previewExpanded = true;
        }
    }
    
    async function startRun() {
        if (!deviceStatus || !deviceStatus.connected) {
            showAlert('Please connect your phone first', 'danger');
            return;
        }
        
        if (isRunning) return;
        
        // Load preview for auto rules and run directly
        previewLoaded = false;
        currentPreviewType = 'auto';
        await loadRulesPreview('auto');
        executeRun();
    }
    
    async function executeRun() {
        if (!deviceStatus || !deviceStatus.connected) {
            showAlert('Please connect your phone first', 'danger');
            return;
        }
        
        if (isRunning) return;
        
        isRunning = true;
        const runBtn = document.getElementById('run-btn');
        const manualBtn = document.getElementById('manual-btn');
        const dryRunOption = document.getElementById('dry-run-option');
        const notifyOption = document.getElementById('notify-option');
        const renameOption = document.getElementById('rename-duplicates-option');
        
        // Disable all buttons and options
        runBtn.disabled = true;
        manualBtn.disabled = true;
        if (dryRunOption) dryRunOption.style.pointerEvents = 'none';
        if (notifyOption) notifyOption.style.pointerEvents = 'none';
        if (renameOption) renameOption.style.pointerEvents = 'none';
        
        runBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Running...';
        
        // Clear previous results immediately
        document.getElementById('stats-card').style.display = 'none';
        document.getElementById('output-card').style.display = 'none';
        document.getElementById('stat-copied').textContent = '0';
        document.getElementById('stat-skipped').textContent = '0';
        document.getElementById('stat-deleted').textContent = '0';
        document.getElementById('stat-errors').textContent = '0';
        document.getElementById('smart-copy-progress').style.display = 'none';
        
        // Command preview already showing and updated
        
        updateRunStatus('running', 'Running auto rules...');
        document.getElementById('manual-selection-card').style.display = 'none';
        document.getElementById('stats-card').style.display = 'block';
        document.getElementById('output-card').style.display = 'block';
        document.getElementById('operations-container').innerHTML = '';
        displayedOperations.clear();
        
        try {
            const result = await apiPost('/api/run', {
                dry_run: options.dry_run,
                notify: options.notify,
                rename_duplicates: options.rename_duplicates
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
                    document.getElementById('stat-copied').textContent = status.stats.copied || 0;
                    document.getElementById('stat-skipped').textContent = status.stats.skipped || 0;
                    document.getElementById('stat-deleted').textContent = status.stats.deleted || 0;
                    document.getElementById('stat-errors').textContent = status.stats.errors || 0;
                    
                    // Show smart-copy progress if available
                    if (status.stats.smart_copy_total && status.stats.smart_copy_current !== undefined) {
                        const total = status.stats.smart_copy_total;
                        const current = status.stats.smart_copy_current;
                        const percent = (current / total) * 100;
                        const remaining = total - current;
                        
                        document.getElementById('smart-copy-progress').style.display = 'block';
                        document.getElementById('smart-copy-current').textContent = `Processing: ${current}/${total} files (${remaining} remaining) - ${percent.toFixed(1)}%`;
                        document.getElementById('smart-copy-bar').style.width = percent + '%';
                    } else {
                        document.getElementById('smart-copy-progress').style.display = 'none';
                    }
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
    
    let currentOperationLogs = [];
    
    function parseAndDisplayOperations(logs) {
        currentOperationLogs = logs; // Store for detail view
        const container = document.getElementById('operations-container');
        const fullLog = logs.join('\n');
        const isDryRun = fullLog.includes('[DRY RUN MODE');
        const lines = fullLog.split('\n');
        let currentOp = null;
        let operationLog = []; // Collect lines for current operation
        
        for (let line of lines) {
            line = line.trim();
            if (!line || line.match(/^[=]+$/)) continue;
            
            const opMatch = line.match(/^[\p{Emoji}\u2192🔄-]*\s*(Move|Copy|Smart Copy|Sync):\s*(.+?)\s*[→\->=>]+\s*(.+)$/u);
            if (opMatch) {
                if (currentOp) {
                    currentOp.logLines = operationLog; // Store logs for this operation
                    displayOperation(container, currentOp, isDryRun);
                }
                const [_, mode, source, dest] = opMatch;
                currentOp = {
                    mode: mode.trim(),
                    source: source.trim(),
                    dest: dest.trim(),
                    stats: {},
                    logLines: []
                };
                operationLog = []; // Reset for new operation
                continue;
            }
            
            if (currentOp) {
                // Store all lines for this operation
                operationLog.push(line);
                
                // Existing stats matching
                const copiedMatch = line.match(/Copied:\s*(\d+)/);
                const skippedMatch = line.match(/Skipped:\s*(\d+)/);
                const deletedMatch = line.match(/Deleted:\s*(\d+)/);
                const syncedMatch = line.match(/Synced:\s*(\d+)/);
                const resumedMatch = line.match(/Resumed:\s*(\d+)/);
                const failedMatch = line.match(/Failed:\s*(\d+)/);
                
                if (copiedMatch) currentOp.stats.copied = parseInt(copiedMatch[1]);
                if (skippedMatch) currentOp.stats.skipped = parseInt(skippedMatch[1]);
                if (deletedMatch) currentOp.stats.deleted = parseInt(deletedMatch[1]);
                if (syncedMatch) currentOp.stats.synced = parseInt(syncedMatch[1]);
                if (resumedMatch) currentOp.stats.resumed = parseInt(resumedMatch[1]);
                if (failedMatch) currentOp.stats.failed = parseInt(failedMatch[1]);
                
                // New: Progress tracking for smart-copy
                const totalMatch = line.match(/Total files:\s*(\d+)/);
                const progressMatch = line.match(/Progress:\s*(\d+)\/(\d+)/);
                const percentMatch = line.match(/(\d+(?:\.\d+)?)%/);
                
                if (totalMatch) currentOp.stats.total = parseInt(totalMatch[1]);
                if (progressMatch) {
                    currentOp.stats.current = parseInt(progressMatch[1]);
                    currentOp.stats.total = parseInt(progressMatch[2]);
                }
                if (percentMatch) currentOp.stats.percent = parseFloat(percentMatch[1]);
            }
        }
        
        if (currentOp) {
            currentOp.logLines = operationLog;
            displayOperation(container, currentOp, isDryRun);
        }
        
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
        const opId = `op-${displayedOperations.size}`;
        let statsHtml = '';
        if (op.stats.copied > 0) statsHtml += `<div style="display: flex; align-items: center; gap: 6px;"><i class="fas fa-check" style="color: var(--success);"></i> <span>${op.stats.copied} copied</span></div>`;
        if (op.stats.skipped > 0) statsHtml += `<div style="display: flex; align-items: center; gap: 6px;"><i class="fas fa-forward" style="color: var(--text-muted);"></i> <span>${op.stats.skipped} skipped</span></div>`;
        if (op.stats.deleted > 0) statsHtml += `<div style="display: flex; align-items: center; gap: 6px;"><i class="fas fa-trash" style="color: var(--danger);"></i> <span>${op.stats.deleted} deleted</span></div>`;
        if (op.stats.synced > 0) statsHtml += `<div style="display: flex; align-items: center; gap: 6px;"><i class="fas fa-sync" style="color: var(--info);"></i> <span>${op.stats.synced} synced</span></div>`;
        if (op.stats.resumed > 0) statsHtml += `<div style="display: flex; align-items: center; gap: 6px;"><i class="fas fa-redo" style="color: var(--info);"></i> <span>${op.stats.resumed} resumed</span></div>`;
        if (op.stats.failed > 0) statsHtml += `<div style="display: flex; align-items: center; gap: 6px;"><i class="fas fa-exclamation-triangle" style="color: var(--warning);"></i> <span>${op.stats.failed} failed</span></div>`;
        
        if (!statsHtml) statsHtml = '<div style="color: var(--text-muted);"><i class="fas fa-check-circle"></i> No changes</div>';
        
        // Build progress bar for smart-copy
        let progressHtml = '';
        if (op.mode === 'Smart Copy' && op.stats.total) {
            const percent = op.stats.percent || (op.stats.current / op.stats.total * 100);
            const remaining = op.stats.total - (op.stats.copied || 0) - (op.stats.skipped || 0);
            progressHtml = `
                <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border-subtle);">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 12px;">
                        <span>Progress: ${op.stats.copied || 0}/${op.stats.total} ${remaining > 0 ? `(${remaining} remaining)` : ''}</span>
                        <span style="color: var(--accent); font-weight: 600;">${percent.toFixed(1)}%</span>
                    </div>
                    <div style="width: 100%; height: 6px; background: rgba(0,0,0,0.3); border-radius: 3px; overflow: hidden;">
                        <div style="height: 100%; background: linear-gradient(90deg, var(--info), var(--success)); width: ${percent}%; transition: width 300ms ease;"></div>
                    </div>
                </div>
            `;
        }
        
        const opCard = document.createElement('div');
        opCard.className = 'operation-card';
        opCard.setAttribute('data-op-id', opId);
        opCard.setAttribute('data-op-data', JSON.stringify(op));
        opCard.setAttribute('data-op-log', JSON.stringify(op.logLines || []));
        opCard.innerHTML = `
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
                <span class="operation-mode ${modeClass}">
                    <i class="fas fa-arrow-right"></i> ${op.mode}
                </span>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <button class="btn btn-secondary btn-sm" onclick="toggleOperationDetails('${opId}')" style="cursor: pointer;">
                        <i class="fas fa-expand-alt"></i> Expand
                    </button>
                    ${isDryRun ? '<span style="background: rgba(245,158,11,0.15); color: var(--warning); padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: 600;"><i class="fas fa-eye"></i> DRY RUN</span>' : ''}
                </div>
            </div>
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px; font-size: 13px; color: var(--text-muted);">
                <i class="fas fa-mobile-alt"></i> ${op.source} <i class="fas fa-arrow-right"></i> <i class="fas fa-desktop"></i> ${op.dest}
            </div>
            <div style="display: flex; gap: 16px; font-size: 13px;">${statsHtml}</div>
            ${progressHtml}
        `;
        container.appendChild(opCard);
    }
    
    function resetRunButton() {
        isRunning = false;
        const runBtn = document.getElementById('run-btn');
        const manualBtn = document.getElementById('manual-btn');
        const dryRunOption = document.getElementById('dry-run-option');
        const notifyOption = document.getElementById('notify-option');
        const renameOption = document.getElementById('rename-duplicates-option');
        
        // Re-enable buttons and options
        runBtn.disabled = false;
        manualBtn.disabled = false;
        if (dryRunOption) dryRunOption.style.pointerEvents = 'auto';
        if (notifyOption) notifyOption.style.pointerEvents = 'auto';
        if (renameOption) renameOption.style.pointerEvents = 'auto';
        
        runBtn.innerHTML = '<i class="fas fa-play"></i> Run All Rules';
        manualBtn.innerHTML = '<i class="fas fa-hand-paper"></i> Run Manual Rules';
    }
    
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
        
        // Update manual command preview dynamically
        updateManualCommandPreview();
    }
    
    async function runSelectedManualRules() {
        if (selectedRuleIds.length === 0) {
            showAlert('Please select at least one rule to run', 'danger');
            return;
        }
        
        closeManualSelection();
        
        // Load preview for manual rules and run directly
        previewLoaded = false;
        currentPreviewType = 'manual';
        await loadRulesPreview('manual');
        executeManualRun();
    }
    
    async function executeManualRun() {
        if (selectedRuleIds.length === 0) {
            showAlert('Please select at least one rule to run', 'danger');
            return;
        }
        
        // Clear previous results immediately
        document.getElementById('stats-card').style.display = 'none';
        document.getElementById('output-card').style.display = 'none';
        document.getElementById('stat-copied').textContent = '0';
        document.getElementById('stat-skipped').textContent = '0';
        document.getElementById('stat-deleted').textContent = '0';
        document.getElementById('stat-errors').textContent = '0';
        document.getElementById('smart-copy-progress').style.display = 'none';
        
        // Run with specific rule IDs
        isRunning = true;
        const runBtn = document.getElementById('run-btn');
        const manualBtn = document.getElementById('manual-btn');
        const dryRunOption = document.getElementById('dry-run-option');
        const notifyOption = document.getElementById('notify-option');
        const renameOption = document.getElementById('rename-duplicates-option');
        
        // Disable all buttons and options
        runBtn.disabled = true;
        manualBtn.disabled = true;
        if (dryRunOption) dryRunOption.style.pointerEvents = 'none';
        if (notifyOption) notifyOption.style.pointerEvents = 'none';
        if (renameOption) renameOption.style.pointerEvents = 'none';
        
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
                notify: options.notify,
                rename_duplicates: options.rename_duplicates
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
            // Check which modal/card is open and close it
            const manualCard = document.getElementById('manual-selection-card');
            
            if (previewExpanded) {
                toggleRulesPreview();
            } else if (manualCard && manualCard.style.display !== 'none') {
                closeManualSelection();
            }
        }
    });
    
    // Load on page load
    loadDeviceStatus();
    updateCommandPreview(); // Initialize command preview
    
    // Auto-refresh every 5 seconds
    setInterval(loadDeviceStatus, 5000);
    
    // Per-operation expand functions
    let expandedModalId = null;
    
    function toggleOperationDetails(opId) {
        const existingModal = document.getElementById('op-detail-modal');
        if (existingModal) {
            existingModal.remove();
            if (expandedModalId === opId) {
                expandedModalId = null;
                return;
            }
        }
        
        expandedModalId = opId;
        const opCard = document.querySelector(`[data-op-id="${opId}"]`);
        if (!opCard) return;
        
        const opData = JSON.parse(opCard.getAttribute('data-op-data'));
        const opLog = JSON.parse(opCard.getAttribute('data-op-log'));
        
        const modal = createOperationModal(opId, opData, opLog);
        document.body.appendChild(modal);
    }
    
    function createOperationModal(opId, opData, opLog) {
        const modal = document.createElement('div');
        modal.id = 'op-detail-modal';
        modal.style.cssText = 'position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.8); z-index: 1001; overflow: auto; display: flex; align-items: center; justify-content: center;';
        modal.onclick = (e) => {
            if (e.target === modal) toggleOperationDetails(opId);
        };
        
        const operations = parseOperationLog(opLog);
        const detailsHtml = buildOperationDetails(operations);
        
        const modeClass = opData.mode.toLowerCase().replace(' ', '_');
        
        modal.innerHTML = `
            <div style="position: relative; max-width: 900px; width: 90%; background: var(--surface); border-radius: var(--radius-card); padding: 24px; box-shadow: 0 20px 60px rgba(0,0,0,0.4);">
                <button onclick="document.getElementById('op-detail-modal').onclick({target: document.getElementById('op-detail-modal')})" style="position: absolute; top: 20px; right: 20px; background: none; border: none; color: var(--text-muted); font-size: 24px; cursor: pointer; padding: 0; width: 24px; height: 24px;">
                    <i class="fas fa-times"></i>
                </button>
                
                <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 20px;">
                    <span class="operation-mode ${modeClass}">
                        <i class="fas fa-${getModeIcon(opData.mode)}"></i> ${opData.mode}
                    </span>
                    <span style="color: var(--text-muted); font-size: 13px;">
                        <i class="fas fa-mobile-alt"></i> ${opData.source} <i class="fas fa-arrow-right"></i> <i class="fas fa-desktop"></i> ${opData.dest}
                    </span>
                </div>
                
                ${detailsHtml}
            </div>
        `;
        
        // Close with Escape
        const handleEscape = (e) => {
            if (e.key === 'Escape') {
                modal.remove();
                expandedModalId = null;
                document.removeEventListener('keydown', handleEscape);
            }
        };
        document.addEventListener('keydown', handleEscape);
        
        return modal;
    }
    
    function parseOperationLog(logLines) {
        const operations = {
            'Files Copying': [],
            'Folders': [],
            'Files Deleting': [],
            'Files Skipped': [],
            'Sync Summary': []
        };
        
        let hasSyncDetails = false;
        let smartCopyFiles = [];
        
        for (let line of logLines) {
            // Keep original line for checking, but also trim for parsing
            const trimmed = line.trim();
            if (!trimmed) continue;
            
            // For sync operations, check if we have detailed file listing
            if (trimmed.includes('⊙') && trimmed.includes('unchanged')) {
                hasSyncDetails = true;
            }
            
            // Skip most summary lines but not sync-specific ones
            if (trimmed.match(/^✓\s+(Copied|Deleted|Renamed|Folders):|^×|^📊|^\[DRY/)) {
                continue;
            }
            
            // Parse sync summary info
            if (trimmed.match(/^✓\s+Synced:|^⊙\s+Skipped:|Cleaned:/)) {
                operations['Sync Summary'].push({ details: trimmed });
                continue;
            }
            
            // Parse Smart Copy progress lines: [NNN/MMM - X.X%] filename
            const smartCopyMatch = trimmed.match(/^\[(\d+)\/(\d+)\s*-\s*[\d.]+%\]\s+(.+)$/);
            if (smartCopyMatch) {
                const filename = smartCopyMatch[3];
                if (filename && !smartCopyFiles.includes(filename)) {
                    smartCopyFiles.push(filename);
                    operations['Files Copying'].push({ source: filename, dest: '✓' });
                }
                continue;
            }
            
            // Parse folder/directory entries (📦 symbol)
            if (trimmed.includes('📦')) {
                const parts = trimmed.split(/→|->/);
                if (parts.length === 2) {
                    const folder = parts[0].replace('📦', '').trim();
                    const dest = parts[1].trim();
                    if (folder && dest) {
                        operations['Folders'].push({ folder, dest });
                    }
                }
            }
            // Parse copied files (→ arrow with leading spaces/indentation)
            else if (trimmed.match(/^→\s/) && trimmed.includes('→')) {
                const parts = trimmed.replace(/^→\s+/, '').split(/→|->/);
                if (parts.length === 2) {
                    const source = parts[0].trim();
                    const dest = parts[1].trim();
                    if (source && dest) {
                        operations['Files Copying'].push({ source, dest });
                    }
                }
            }
            // Parse deleted files (× symbol)
            else if (trimmed.match(/^×\s/)) {
                const file = trimmed.replace(/^×\s+/, '').trim();
                if (file) {
                    operations['Files Deleting'].push({ file });
                }
            }
            // Parse skipped files (⊙ symbol) - sync operations show these for unchanged files
            else if (trimmed.match(/^⊙\s/)) {
                const file = trimmed.replace(/^⊙\s+/, '').replace(/\(unchanged\)/, '').trim();
                if (file) {
                    operations['Files Skipped'].push({ file });
                }
            }
        }
        
        // If no detailed sync info was found, create a note about it
        if (operations['Sync Summary'].length > 0 && !hasSyncDetails) {
            operations['Sync Summary'].push({ 
                details: 'Note: Sync operations only show summary in non-verbose mode. Individual file details are not available.' 
            });
        }
        
        return operations;
    }
    
    function buildOperationDetails(operations) {
        let html = '';
        
        for (const [category, items] of Object.entries(operations)) {
            if (items.length === 0) continue;
            
            const icon = {
                'Files Copying': 'fas fa-copy',
                'Files Deleting': 'fas fa-trash',
                'Files Skipped': 'fas fa-forward',
                'Folders': 'fas fa-folder',
                'Sync Summary': 'fas fa-info-circle'
            }[category] || 'fas fa-file';
            
            html += `
                <div style="background: rgba(0,0,0,0.2); border: 1px solid var(--border-subtle); border-radius: var(--radius-card); padding: 16px; margin-bottom: 16px;">
                    <h4 style="margin: 0 0 12px 0; color: var(--text); display: flex; align-items: center; gap: 8px;">
                        <i class="${icon}"></i> ${category} (${items.length})
                    </h4>
                    <div style="max-height: 400px; overflow-y: auto;">
                        ${items.map(item => {
                            if (item.folder && item.dest) {
                                return `<div style="margin-bottom: 8px; padding: 8px; background: rgba(0,0,0,0.2); border-radius: 4px; font-size: 12px; font-family: monospace;">
                                    <div style="color: var(--text-muted); margin-bottom: 2px;">📁 ${item.folder}/</div>
                                    <div style="color: var(--success); display: flex; align-items: center; gap: 4px;"><i class="fas fa-arrow-right"></i> ${item.dest}</div>
                                </div>`;
                            } else if (item.source && item.dest) {
                                return `<div style="margin-bottom: 8px; padding: 8px; background: rgba(0,0,0,0.2); border-radius: 4px; font-size: 12px; font-family: monospace;">
                                    <div style="color: var(--text-muted); margin-bottom: 2px;">📄 ${item.source}</div>
                                    <div style="color: var(--success); display: flex; align-items: center; gap: 4px;"><i class="fas fa-arrow-right"></i> ${item.dest}</div>
                                </div>`;
                            } else if (item.file) {
                                return `<div style="margin-bottom: 4px; padding: 6px; background: rgba(0,0,0,0.2); border-radius: 4px; font-size: 12px; font-family: monospace;">${item.file}</div>`;
                            } else if (item.details) {
                                return `<div style="margin-bottom: 4px; padding: 6px; background: rgba(0,0,0,0.2); border-radius: 4px; font-size: 12px; color: var(--text);">${item.details}</div>`;
                            }
                            return '';
                        }).join('')}
                    </div>
                </div>
            `;
        }
        
        return html || '<p style="color: var(--text-muted);">No file-level details available</p>';
    }
    
    // Cleanup
    window.addEventListener('beforeunload', () => {
        stopPolling();
    });
    
    // Close modal with escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && isResultsExpanded) {
            toggleResultsExpanded();
        }
    });
