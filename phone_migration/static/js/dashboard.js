let deviceStatus = null;
    let options = {
        dry_run: true,           // Default to dry run for safety
        notify: true,            // Default to notifications enabled
        rename_duplicates: true  // Default to renaming duplicates on conflict
    };
    let pollInterval = null;
    let isRunning = false;
    let lastResult = null;      // the RunResult of the finished run
    let manualRules = [];
    let selectedRuleIds = [];
    let previewExpanded = false;
    let previewLoaded = false;
    let currentPreviewType = null;  // 'auto' or 'manual'
    let allRules = [];  // Store all rules for preview
    let isValidating = false;  // Track if validation is in progress
    let validationComplete = false;  // Track if validation has completed
    
    // Device names are phone-reported, so they travel in dataset attributes and
    // are read back by one delegated listener - never through an inline onclick.
    let unregisteredDevice = null;
    
    function registerDetectedDevice() {
        if (!unregisteredDevice) return;
        window.prefilledDevice = {
            name: unregisteredDevice.device_name,
            mtp_id: unregisteredDevice.mtp_id,
            id_type: unregisteredDevice.id_type,
            id_value: unregisteredDevice.id_value
        };
        window.location.href = '/profiles';
    }
    
    document.getElementById('device-status').addEventListener('click', (event) => {
        if (event.target.closest('[data-register-device]')) {
            registerDetectedDevice();
        } else if (event.target.closest('[data-mtp-help]')) {
            event.preventDefault();
            showInfo('Close other file managers: killall nemo dolphin nautilus pcmanfm thunar, '
                     + 'then systemctl --user restart gvfs-daemon, then reconnect your phone.');
        }
    });
    
    async function loadDeviceStatus() {
        try {
            const status = await apiGet('/api/status');
            deviceStatus = status;
            
            // Track validation state
            isValidating = status.validation_in_progress || false;
            if (!isValidating && status.connected && status.accessible) {
                validationComplete = true;
            }
            
            // Update button state based on connection, accessibility, AND validation
            // Block operations if validation is in progress OR if not ready
            const runBtn = document.getElementById('run-btn');
            const manualBtn = document.getElementById('manual-btn');
            const isReady = status.connected && status.accessible && !isValidating;
            if (!isRunning) {
                if (runBtn) {
                    runBtn.disabled = !isReady;
                    if (isValidating) {
                        runBtn.title = "Validating rules, please wait...";
                    } else {
                        runBtn.title = "";
                    }
                }
                if (manualBtn) {
                    manualBtn.disabled = !isReady;
                    if (isValidating) {
                        manualBtn.title = "Validating rules, please wait...";
                    } else {
                        manualBtn.title = "";
                    }
                }
            }
            
            let statusHtml = '';
            
            // Add MTP exclusivity warning at the top
            const warningBanner = `
                <div style="background: rgba(255, 193, 7, 0.15); border: 1.5px solid #ffc107; border-radius: var(--radius-card); padding: 12px; margin-bottom: 16px;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <i class="fas fa-info-circle" style="color: #ffc107; font-size: 16px;"></i>
                        <span style="color: #ffc107; font-size: 13px;">
                            <strong>MTP Limitation:</strong> Close all file managers (Nemo, Dolphin, etc.) before using this tool. Only one app can access your phone at a time.
                            <a href="#" data-mtp-help style="color: #ffc107; text-decoration: underline; margin-left: 8px;">How to fix</a>
                        </span>
                    </div>
                </div>
            `;
            
            if (status.connected && status.accessible) {
                // Device connected and accessible - all good
                statusHtml = warningBanner;
                
                // Show validation in progress indicator
                if (status.validation_in_progress) {
                    statusHtml += `
                        <div style="background: rgba(157, 212, 255, 0.15); border: 1.5px solid var(--info); border-radius: var(--radius-card); padding: 14px; margin-bottom: 16px;">
                            <div style="display: flex; align-items: center; gap: 12px;">
                                <div class="spinner" style="width: 16px; height: 16px; border-width: 2px;"></div>
                                <span style="color: var(--info); font-weight: 600; font-size: 14px;"><i class="fas fa-search"></i> Validating Rules...</span>
                            </div>
                            <div style="margin-top: 8px; font-size: 12px; color: #94a3b8;">
                                Checking if all configured paths exist and are accessible. Operations are blocked until validation completes.
                            </div>
                        </div>
                    `;
                }
                
                // Add validation warnings if any
                if (status.validation_warnings && status.validation_warnings.length > 0) {
                    statusHtml += `
                        <div style="background: rgba(255, 214, 153, 0.15); border: 1.5px solid var(--warning); border-radius: var(--radius-card); padding: 14px; margin-bottom: 16px;">
                            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px;">
                                <i class="fas fa-exclamation-triangle" style="color: var(--warning); font-size: 16px;"></i>
                                <span style="color: var(--warning); font-weight: 600; font-size: 14px;">Rule Configuration Issues (${status.validation_warnings.length})</span>
                            </div>
                            <div style="display: flex; flex-direction: column; gap: 8px;">
                    `;
                    
                    status.validation_warnings.forEach(warning => {
                        const icon = (warning.type || '').includes('phone') ? 'fa-mobile-alt' : 'fa-desktop';
                        statusHtml += `
                            <div style="background: rgba(255, 214, 153, 0.1); border-radius: 6px; padding: 8px 10px; font-size: 13px;">
                                <div style="color: #ffc107; font-weight: 500; margin-bottom: 4px;">
                                    <i class="fas ${icon}"></i> Rule ${escapeHtml(warning.rule_id)} (${escapeHtml(String(warning.rule_mode || '').toUpperCase())})
                                </div>
                                <div style="color: #cbd5e1; font-size: 12px;">${escapeHtml(warning.message)}</div>
                            </div>
                        `;
                    });
                    
                    statusHtml += `
                            </div>
                            <div style="margin-top: 10px; font-size: 12px; color: #94a3b8;">
                                <i class="fas fa-info-circle"></i> Fix these issues before running operations to avoid errors
                            </div>
                        </div>
                    `;
                }
                
                statusHtml += `
                    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">
                        <span class="status-badge connected"><i class="fas fa-check-circle"></i> Connected & Ready</span>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; color: #94a3b8;">
                        <div style="display: flex; flex-direction: column; gap: 4px;">
                            <span style="font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px;">Device</span>
                            <span style="font-size: 15px; color: #cbd5e1; font-weight: 500;">${escapeHtml(status.device_name)}</span>
                        </div>
                        <div style="display: flex; flex-direction: column; gap: 4px;">
                            <span style="font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px;">Profile</span>
                            <span style="font-size: 15px; color: #cbd5e1; font-weight: 500;">${escapeHtml(status.profile_name)}</span>
                        </div>
                        <div style="display: flex; flex-direction: column; gap: 4px;">
                            <span style="font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px;">Rules</span>
                            <span style="font-size: 15px; color: #cbd5e1; font-weight: 500;">${escapeHtml(status.rule_count)} configured</span>
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
                            <strong>Device:</strong> ${escapeHtml(status.device_name)} (${escapeHtml(status.profile_name)})
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
                        unregisteredDevice = unregistered[0];
                        statusHtml = `
                            <div style="background: rgba(255, 214, 153, 0.15); border: 1.5px solid var(--warning); border-radius: var(--radius-card); padding: 16px; margin-bottom: 16px;">
                                <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
                                    <i class="fas fa-exclamation-triangle" style="color: var(--warning); font-size: 18px;"></i>
                                    <span style="color: var(--warning); font-weight: 600; font-size: 15px;">Device Connected But Not Registered</span>
                                </div>
                                <p style="color: #cbd5e1; margin: 8px 0; font-size: 14px;">
                                    <strong>Device:</strong> ${escapeHtml(unregisteredDevice.device_name)}
                                </p>
                                <p style="color: #94a3b8; margin: 8px 0 12px 0; font-size: 13px;">
                                    This device needs to be registered as a profile to use the sync tool.
                                </p>
                                <button data-register-device class="btn btn-small" style="background: var(--warning); color: #1e293b;">
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
                    Error loading device status: ${escapeHtml(error.message)}
                </div>
            `;
        }
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
        
        // Build command parts. Bare `--run` previews (dry-run is the CLI
        // default); `-y` executes. `--dry-run` and `--rename-duplicates` are
        // not real CLI flags - the latter is web-only.
        const parts = ['phone-sync', '--run'];
        if (!isDryRun) {
            parts.push('-y');
        }

        if (options.notify) {
            parts.push('--notify');
        }

        selectedRules.forEach(id => {
            parts.push('-r', escapeHtml(id));
        });

        // Add to HTML
        html += '<div class="command-line">';
        html += `<span class="command-prompt">$</span>`;
        html += '<span class="command-text">';

        for (let i = 0; i < parts.length; i++) {
            if (i > 0) html += ' ';

            if (parts[i].startsWith('-')) {
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
                html += `<div style="font-size: 13px; color: var(--text); font-family: monospace; margin-left: 16px;">- ${escapeHtml(id)}</div>`;
            });
            html += '</div>';
        }
        
        // Add warning if not dry run
        if (!isDryRun) {
            html += `
                <div class="command-warning">
                    <i class="fas fa-exclamation-triangle command-warning-icon"></i>
                    <span style="color: var(--warning);"><strong>This will EXECUTE operations.</strong> Files will be moved, copied, or synced.</span>
                </div>
            `;
        } else {
            html += `
                <div style="background: rgba(96, 165, 250, 0.1); border: 1px solid rgba(96, 165, 250, 0.3); border-radius: var(--radius-card); padding: 12px; margin-top: 12px; font-size: 13px;">
                    <i class="fas fa-eye" style="color: var(--info); margin-right: 8px;"></i>
                    <span style="color: var(--info);"><strong>Preview mode.</strong> No files will be modified.</span>
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
            const data = await apiGet(`/api/profiles/${encodeURIComponent(deviceStatus.profile_name)}/rules`);
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
                return `
                    <div style="background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; padding: 12px; margin-bottom: 8px;">
                        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                            <span class="operation-mode ${escapeHtml(modeClass)}" style="font-size: 11px; padding: 3px 8px;">
                                <i class="fas fa-${getModeIcon(modeClass)}"></i> ${escapeHtml(getModeLabel(modeClass))}
                            </span>
                            <span style="font-size: 12px; color: var(--text-muted); font-family: monospace;">${escapeHtml(rule.id)}</span>
                        </div>
                        <div style="font-size: 12px; color: var(--text); display: flex; align-items: center; gap: 8px;">
                            <i class="fas fa-mobile-alt" style="width: 14px; color: var(--info);"></i>
                            <span style="flex: 1; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(rule.phone_path)}</span>
                        </div>
                        <div style="font-size: 12px; color: var(--text); display: flex; align-items: center; gap: 8px; margin-top: 4px;">
                            <i class="fas fa-desktop" style="width: 14px; color: var(--success);"></i>
                            <span style="flex: 1; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(rule.desktop_path)}</span>
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
        const navLinks = document.querySelectorAll('.nav-link');
        
        // Show operation progress card
        showOperationProgress('auto');
        
        // Disable all buttons and options
        runBtn.disabled = true;
        manualBtn.disabled = true;
        
        // Disable navigation
        navLinks.forEach(link => link.classList.add('disabled'));
        
        // Disable options with CSS class for smooth animation
        if (dryRunOption) dryRunOption.classList.add('disabled');
        if (notifyOption) notifyOption.classList.add('disabled');
        if (renameOption) renameOption.classList.add('disabled');
        
        runBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Running...';
        
        // Clear previous results and show cards immediately
        document.getElementById('stats-card').style.display = 'block';
        document.getElementById('output-card').style.display = 'block';
        ['copied', 'skipped', 'deleted', 'errors'].forEach(key => {
            document.getElementById(`stat-${key}`).textContent = '0';
        });
        lastResult = null;
        document.getElementById('operations-container').innerHTML =
            '<pre class="run-log" id="run-log"></pre>';
        
        // Command preview already showing and updated
        
        updateRunStatus('running', 'Running auto rules...');
        setOperationPhase(options.dry_run ? 'Dry Run - Preview Only' : 'Executing Operations');
        document.getElementById('manual-selection-card').style.display = 'none';
        
        try {
            const result = await apiPost('/api/run', {
                dry_run: options.dry_run,
                notify: options.notify,
                rename_duplicates: options.rename_duplicates
            });
            
            if (result.success) {
                saveOperationState();
                startPolling();
            } else {
                throw new Error(result.error || 'Failed to start sync');
            }
        } catch (error) {
            updateRunStatus('error', 'Error: ' + error.message);
            sessionStorage.removeItem('isRunning');
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
    
    function showOperationProgress(type) {
        const card = document.getElementById('operation-progress-card');
        const statusText = document.getElementById('operation-status-text');
        const rulesList = document.getElementById('rules-progress-list');
        
        if (!card) return;
        
        card.style.display = 'block';
        
        // Determine which rules to show
        const rulesToShow = type === 'manual' && selectedRuleIds.length > 0
            ? allRules.filter(r => selectedRuleIds.includes(r.id))
            : allRules.filter(r => !r.manual_only);
        
        statusText.textContent = `Processing ${rulesToShow.length} rule${rulesToShow.length !== 1 ? 's' : ''}...`;
        
        // Build rules progress list
        rulesList.innerHTML = rulesToShow.map(rule => `
            <div class="rule-progress-item pending" data-rule-progress="${escapeHtml(rule.id)}">
                <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 8px;">
                    <div class="rule-status-icon" style="width: 24px; height: 24px; display: flex; align-items: center; justify-content: center;">
                        <i class="fas fa-clock" style="color: var(--text-muted);"></i>
                    </div>
                    <div style="flex: 1;">
                        <div style="font-weight: 600; font-size: 14px; color: var(--text);">
                            <span class="operation-mode ${escapeHtml(rule.mode)}" style="font-size: 11px; padding: 3px 8px; margin-right: 8px;">
                                <i class="fas fa-${getModeIcon(rule.mode)}"></i> ${escapeHtml(getModeLabel(rule.mode))}
                            </span>
                            ${escapeHtml(rule.id)}
                        </div>
                        <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">
                            <i class="fas fa-mobile-alt" style="color: #0ea5e9;"></i> ${escapeHtml(rule.phone_path)}
                            <i class="fas fa-arrow-right" style="margin: 0 6px; color: var(--text-muted);"></i>
                            <i class="fas fa-desktop" style="color: #10b981;"></i> ${escapeHtml(rule.desktop_path)}
                        </div>
                    </div>
                </div>
                <div class="rule-progress-bar" style="display: none; height: 4px; background: rgba(255,255,255,0.1); border-radius: 2px; margin-top: 8px;">
                    <div class="rule-progress-fill" style="height: 100%; width: 0%; background: linear-gradient(90deg, #0ea5e9, #10b981); border-radius: 2px; transition: width 0.3s ease;"></div>
                </div>
                <div class="rule-stats" style="display: none; margin-top: 8px; font-size: 12px; color: var(--text-muted);"></div>
            </div>
        `).join('');
    }
    
    function updateRuleProgress(ruleId, status, stats) {
        const item = [...document.querySelectorAll('[data-rule-progress]')]
            .find(el => el.dataset.ruleProgress === String(ruleId));
        if (!item) return;
        
        const icon = item.querySelector('.rule-status-icon i');
        const progressFill = item.querySelector('.rule-progress-fill');
        const statsDiv = item.querySelector('.rule-stats');
        
        item.className = `rule-progress-item ${status}`;
        
        if (status === 'running') {
            icon.className = 'fas fa-sync fa-spin';
            icon.style.color = '#0ea5e9';
        } else if (status === 'completed') {
            icon.className = 'fas fa-check-circle';
            icon.style.color = '#10b981';
            if (progressFill) progressFill.style.width = '100%';
        } else if (status === 'error') {
            icon.className = 'fas fa-exclamation-circle';
            icon.style.color = '#ef4444';
        }
        
        // Stats come from the RunResult, so they are counts - not parsed text.
        const parts = STAT_LABELS
            .filter(([key]) => (stats || {})[key] > 0)
            .map(([key, label]) => `${stats[key]} ${label}`);
        if (parts.length && statsDiv) {
            statsDiv.textContent = parts.join(' | ');
            statsDiv.style.display = 'block';
        }
    }
    
    // The rules list is built pending; the finished RunResult settles each one.
    function applyResultToProgress(result) {
        const rules = (result && result.rules) || [];
        rules.forEach(rule => {
            updateRuleProgress(rule.id, rule.error ? 'error' : 'completed', rule.stats);
        });
        const statusText = document.getElementById('operation-status-text');
        if (statusText) {
            statusText.textContent = `Finished ${rules.length} rule${rules.length !== 1 ? 's' : ''}`;
        }
    }
    
    function setOperationPhase(text) {
        const phaseText = document.getElementById('operation-phase-text');
        if (phaseText) phaseText.textContent = text;
    }
    
    function saveOperationState() {
        // Save state to sessionStorage so it persists across tab switches/refreshes
        sessionStorage.setItem('isRunning', isRunning.toString());
        sessionStorage.setItem('operationType', selectedRuleIds.length > 0 ? 'manual' : 'auto');
        sessionStorage.setItem('selectedRuleIds', JSON.stringify(selectedRuleIds));
    }
    
    function restoreOperationState() {
        // Check if an operation was running before page refresh
        const wasRunning = sessionStorage.getItem('isRunning') === 'true';
        if (wasRunning) {
            isRunning = true;
            const operationType = sessionStorage.getItem('operationType');
            const savedRuleIds = sessionStorage.getItem('selectedRuleIds');
            if (savedRuleIds) {
                selectedRuleIds = JSON.parse(savedRuleIds);
            }
            
            // Show appropriate UI state. The log pane has to exist before
            // polling starts, or a restored run streams into nothing.
            document.getElementById('stats-card').style.display = 'block';
            document.getElementById('output-card').style.display = 'block';
            document.getElementById('operations-container').innerHTML =
                '<pre class="run-log" id="run-log"></pre>';
            
            if (operationType === 'manual') {
                updateRunStatus('running', `Running ${selectedRuleIds.length} manual rule(s)...`);
                document.getElementById('manual-btn').innerHTML = '<i class="fas fa-spinner fa-spin"></i> Running...';
            } else {
                updateRunStatus('running', 'Running auto rules...');
                document.getElementById('run-btn').innerHTML = '<i class="fas fa-spinner fa-spin"></i> Running...';
            }
            
            // Disable controls
            const runBtn = document.getElementById('run-btn');
            const manualBtn = document.getElementById('manual-btn');
            const dryRunOption = document.getElementById('dry-run-option');
            const notifyOption = document.getElementById('notify-option');
            const renameOption = document.getElementById('rename-duplicates-option');
            const navLinks = document.querySelectorAll('.nav-link');
            
            // Show operation progress card
            showOperationProgress(operationType);
            
            runBtn.disabled = true;
            manualBtn.disabled = true;
            
            // Disable navigation
            navLinks.forEach(link => link.classList.add('disabled'));
            
            // Disable options with CSS class
            if (dryRunOption) dryRunOption.classList.add('disabled');
            if (notifyOption) notifyOption.classList.add('disabled');
            if (renameOption) renameOption.classList.add('disabled');
            
            // Resume polling
            startPolling();
        }
    }
    
    function startPolling() {
        pollInterval = setInterval(async () => {
            try {
                const status = await apiGet('/api/run/status');
                
                showLiveLog(status.logs || []);
                
                if (!status.running && isRunning) {
                    stopPolling();
                    lastResult = status.result;
                    renderResult(status.result, status.logs || []);
                    applyResultToProgress(status.result);
                    
                    const errors = (status.result && status.result.stats
                                    && status.result.stats.errors) || 0;
                    const failed = !status.result || errors > 0;
                    updateRunStatus(failed ? 'error' : 'success',
                                    failed ? 'Completed with errors' : 'Completed successfully');
                    
                    document.getElementById('stats-card').style.display = 'block';
                    document.getElementById('output-card').style.display = 'block';
                    
                    // Clear session state when the operation completes
                    sessionStorage.removeItem('isRunning');
                    sessionStorage.removeItem('operationType');
                    sessionStorage.removeItem('selectedRuleIds');
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
    
    const STAT_LABELS = [
        ['copied', 'copied', 'fa-check', 'var(--success)'],
        ['moved', 'moved', 'fa-arrow-right', 'var(--info)'],
        ['synced', 'synced', 'fa-sync', 'var(--info)'],
        ['backed_up', 'backed up', 'fa-save', 'var(--success)'],
        ['renamed', 'renamed', 'fa-pen', 'var(--warning)'],
        ['skipped', 'skipped', 'fa-forward', 'var(--text-muted)'],
        ['deleted', 'deleted', 'fa-trash', 'var(--danger)'],
        ['resumed', 'already backed up', 'fa-redo', 'var(--info)'],
        ['folders', 'folders', 'fa-folder', 'var(--text-muted)'],
        ['errors', 'errors', 'fa-times-circle', 'var(--danger)']
    ];
    
    function showLiveLog(logs) {
        const log = document.getElementById('run-log');
        if (!log) return;
        
        // Raw CLI output: textContent, never innerHTML.
        log.textContent = logs.join('\n');
        log.scrollTop = log.scrollHeight;
    }
    
    function renderStats(stats) {
        const parts = STAT_LABELS
            .filter(([key]) => (stats || {})[key] > 0)
            .map(([key, label, icon, color]) => `
                <div style="display: flex; align-items: center; gap: 6px;">
                    <i class="fas ${icon}" style="color: ${color};"></i>
                    <span>${escapeHtml(stats[key])} ${escapeHtml(label)}</span>
                </div>
            `);
        
        return parts.length
            ? parts.join('')
            : '<div style="color: var(--text-muted);"><i class="fas fa-check-circle"></i> No changes</div>';
    }
    
    function renderResult(result, logs) {
        const container = document.getElementById('operations-container');
        
        if (!result) {
            container.innerHTML = '<pre class="run-log" id="run-log"></pre>';
            showLiveLog(logs);
            return;
        }
        
        const stats = result.stats || {};
        ['copied', 'skipped', 'deleted', 'errors'].forEach(key => {
            const el = document.getElementById(`stat-${key}`);
            if (el) el.textContent = stats[key] || 0;
        });
        
        // The badge is a fact from the run, not a substring of its output.
        const dryRunBadge = result.dry_run
            ? '<span class="dry-run-badge"><i class="fas fa-eye"></i> DRY RUN</span>'
            : '';
        
        const rules = result.rules || [];
        const cards = rules.map((rule, index) => `
            <div class="operation-card">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
                    <span class="operation-mode ${escapeHtml(rule.mode)}">
                        <i class="fas fa-${getModeIcon(rule.mode)}"></i> ${escapeHtml(getModeLabel(rule.mode))}
                    </span>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="color: var(--text-muted); font-size: 12px;">${escapeHtml(rule.id)}</span>
                        <button class="btn btn-secondary btn-sm" data-rule-index="${index}">
                            <i class="fas fa-expand-alt"></i> Expand
                        </button>
                        ${dryRunBadge}
                    </div>
                </div>
                <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px; font-size: 13px; color: var(--text-muted);">
                    <i class="fas fa-mobile-alt"></i> ${escapeHtml(rule.phone_path)}
                    <i class="fas fa-arrow-right"></i>
                    <i class="fas fa-desktop"></i> ${escapeHtml(rule.desktop_path)}
                </div>
                ${rule.error ? `<div class="alert alert-danger">${escapeHtml(rule.error)}</div>` : ''}
                <div style="display: flex; flex-wrap: wrap; gap: 16px; font-size: 13px;">${renderStats(rule.stats)}</div>
            </div>
        `).join('');
        
        const empty = rules.length === 0 ? `
            <div style="text-align: center; padding: 40px; color: var(--text-muted);">
                <i class="fas fa-check-circle" style="font-size: 48px; color: var(--success); margin-bottom: 16px;"></i>
                <h3 style="color: var(--text);">${result.profile ? 'No Rules Ran' : 'No Device Matched'}</h3>
                <p>${result.profile ? 'Nothing was selected to run' : 'Connect a registered phone and try again'}</p>
            </div>
        ` : '';
        
        container.innerHTML = `${empty}${cards}<pre class="run-log" id="run-log"></pre>`;
        showLiveLog(logs);
    }
    
    // One delegated handler for every Expand button.
    document.getElementById('operations-container').addEventListener('click', (event) => {
        const button = event.target.closest('button[data-rule-index]');
        if (button) openRuleDetails(Number(button.dataset.ruleIndex));
    });
    
    function openRuleDetails(index) {
        closeRuleDetails();
        
        const rule = lastResult && (lastResult.rules || [])[index];
        if (!rule) return;
        
        const groups = {};
        (rule.files || []).forEach(file => {
            (groups[file.action] = groups[file.action] || []).push(file);
        });
        
        const sections = Object.entries(groups).map(([action, files]) => `
            <div style="background: rgba(0,0,0,0.2); border: 1px solid var(--border-subtle); border-radius: var(--radius-card); padding: 16px; margin-bottom: 16px;">
                <h4 style="margin: 0 0 12px 0; color: var(--text); display: flex; align-items: center; gap: 8px;">
                    <i class="fas ${ACTION_ICONS[action] || 'fa-file'}"></i> ${escapeHtml(action)} (${files.length})
                </h4>
                <div style="max-height: 400px; overflow-y: auto;">
                    ${files.map(file => `
                        <div class="file-row">
                            <div>${escapeHtml(file.src)}</div>
                            ${file.dst ? `<div style="color: var(--success);"><i class="fas fa-arrow-right"></i> ${escapeHtml(file.dst)}</div>` : ''}
                            ${file.error ? `<div style="color: var(--danger);">${escapeHtml(file.error)}</div>` : ''}
                        </div>
                    `).join('')}
                </div>
            </div>
        `).join('');
        
        const modal = document.createElement('div');
        modal.id = 'op-detail-modal';
        modal.style.cssText = 'position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.8); z-index: 1001; overflow: auto; display: flex; align-items: center; justify-content: center;';
        modal.innerHTML = `
            <div style="position: relative; max-width: 900px; width: 90%; max-height: 85vh; overflow: auto; background: var(--surface); border-radius: var(--radius-card); padding: 24px; box-shadow: 0 20px 60px rgba(0,0,0,0.4);">
                <button id="op-detail-close" style="position: absolute; top: 20px; right: 20px; background: none; border: none; color: var(--text-muted); font-size: 24px; cursor: pointer;">
                    <i class="fas fa-times"></i>
                </button>
                <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 20px;">
                    <span class="operation-mode ${escapeHtml(rule.mode)}">
                        <i class="fas fa-${getModeIcon(rule.mode)}"></i> ${escapeHtml(getModeLabel(rule.mode))}
                    </span>
                    <span style="color: var(--text-muted); font-size: 13px;">
                        <i class="fas fa-mobile-alt"></i> ${escapeHtml(rule.phone_path)}
                        <i class="fas fa-arrow-right"></i>
                        <i class="fas fa-desktop"></i> ${escapeHtml(rule.desktop_path)}
                    </span>
                </div>
                ${sections || '<p style="color: var(--text-muted);">No file-level details available</p>'}
            </div>
        `;
        
        modal.addEventListener('click', (event) => {
            if (event.target === modal || event.target.closest('#op-detail-close')) {
                closeRuleDetails();
            }
        });
        
        document.body.appendChild(modal);
    }
    
    function closeRuleDetails() {
        const modal = document.getElementById('op-detail-modal');
        if (modal) modal.remove();
    }
    
    function resetRunButton() {
        isRunning = false;
        const runBtn = document.getElementById('run-btn');
        const manualBtn = document.getElementById('manual-btn');
        const dryRunOption = document.getElementById('dry-run-option');
        const notifyOption = document.getElementById('notify-option');
        const renameOption = document.getElementById('rename-duplicates-option');
        const navLinks = document.querySelectorAll('.nav-link');
        
        // Re-enable buttons and options
        runBtn.disabled = false;
        manualBtn.disabled = false;
        
        // Re-enable navigation
        navLinks.forEach(link => link.classList.remove('disabled'));
        
        // Re-enable options
        if (dryRunOption) dryRunOption.classList.remove('disabled');
        if (notifyOption) notifyOption.classList.remove('disabled');
        if (renameOption) renameOption.classList.remove('disabled');
        
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
            const data = await apiGet(`/api/profiles/${encodeURIComponent(deviceStatus.profile_name)}/rules`);
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
                    <input type="checkbox" value="${escapeHtml(rule.id)}" data-select-rule="${escapeHtml(rule.id)}">
                    <div style="flex: 1;">
                        <div style="font-weight: 600; color: var(--text); margin-bottom: 4px;">
                            <span class="operation-mode ${escapeHtml(rule.mode)}" style="margin-right: 8px;">
                                <i class="fas fa-${getModeIcon(rule.mode)}"></i> ${escapeHtml(getModeLabel(rule.mode))}
                            </span>
                            ${escapeHtml(rule.id)}
                        </div>
                        <div style="font-size: 13px; color: var(--text-muted);">
                            <i class="fas fa-mobile-alt" style="width: 16px;"></i> ${escapeHtml(rule.phone_path)}
                            <i class="fas fa-arrow-right"></i>
                            <i class="fas fa-desktop" style="width: 16px;"></i> ${escapeHtml(rule.desktop_path)}
                        </div>
                    </div>
                </label>
            `).join('');
        } catch (error) {
            showAlert('Failed to load manual rules: ' + error.message, 'danger');
            closeManualSelection();
        }
    }
    
    document.getElementById('manual-rules-list').addEventListener('change', (event) => {
        const box = event.target.closest('[data-select-rule]');
        if (box) toggleRuleSelection(box.dataset.selectRule);
    });
    
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
        
        // Clear previous results
        document.getElementById('stats-card').style.display = 'none';
        document.getElementById('output-card').style.display = 'none';
        ['copied', 'skipped', 'deleted', 'errors'].forEach(key => {
            document.getElementById(`stat-${key}`).textContent = '0';
        });
        lastResult = null;
        document.getElementById('operations-container').innerHTML =
            '<pre class="run-log" id="run-log"></pre>';
        
        // Run with specific rule IDs
        isRunning = true;
        const runBtn = document.getElementById('run-btn');
        const manualBtn = document.getElementById('manual-btn');
        const dryRunOption = document.getElementById('dry-run-option');
        const notifyOption = document.getElementById('notify-option');
        const renameOption = document.getElementById('rename-duplicates-option');
        const navLinks = document.querySelectorAll('.nav-link');
        
        // Show operation progress card
        showOperationProgress('manual');
        
        // Disable all buttons and options
        runBtn.disabled = true;
        manualBtn.disabled = true;
        
        // Disable navigation
        navLinks.forEach(link => link.classList.add('disabled'));
        
        // Disable options with CSS class
        if (dryRunOption) dryRunOption.classList.add('disabled');
        if (notifyOption) notifyOption.classList.add('disabled');
        if (renameOption) renameOption.classList.add('disabled');
        
        manualBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Running...';
        
        updateRunStatus('running', `Running ${selectedRuleIds.length} manual rule(s)...`);
        setOperationPhase(options.dry_run ? 'Dry Run - Preview Only' : 'Executing Operations');
        
        try {
            const result = await apiPost('/api/run', {
                dry_run: options.dry_run,
                rule_ids: selectedRuleIds,
                notify: options.notify,
                rename_duplicates: options.rename_duplicates
            });
            
            if (result.success) {
                saveOperationState();
                startPolling();
            } else {
                throw new Error(result.error || 'Failed to start sync');
            }
        } catch (error) {
            updateRunStatus('error', 'Error: ' + error.message);
            sessionStorage.removeItem('isRunning');
            resetRunButton();
        }
    }
    
    function getModeIcon(mode) {
        return { move: 'arrow-right', copy: 'copy', backup: 'save',
                 smart_copy: 'save', sync: 'sync' }[mode] || 'cog';
    }
    
    function getModeLabel(mode) {
        return { move: 'Move', copy: 'Copy', backup: 'Backup',
                 smart_copy: 'Backup', sync: 'Sync' }[mode] || mode;
    }
    
    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            // Check which modal/card is open and close it
            const manualCard = document.getElementById('manual-selection-card');
            
            if (document.getElementById('op-detail-modal')) {
                closeRuleDetails();
            } else if (previewExpanded) {
                toggleRulesPreview();
            } else if (manualCard && manualCard.style.display !== 'none') {
                closeManualSelection();
            }
        }
    });
    
    // Load on page load
    loadDeviceStatus();
    updateCommandPreview(); // Initialize command preview
    restoreOperationState(); // Restore state if page was refreshed during operation
    
    // Auto-refresh every 5 seconds
    setInterval(loadDeviceStatus, 5000);
    
    // Cleanup
    window.addEventListener('beforeunload', () => {
        stopPolling();
    });
