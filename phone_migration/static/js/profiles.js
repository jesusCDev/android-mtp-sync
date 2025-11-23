// Profile Management Functions

async function loadProfiles() {
    try {
        const profiles = await apiGet('/api/profiles');
        
        const container = document.getElementById('profiles-container');
        if (!profiles || profiles.length === 0) {
            container.innerHTML = '<div style="text-align: center; padding: 40px; color: var(--text-muted);">No profiles found. Create one to get started.</div>';
            return;
        }
        
        container.innerHTML = profiles.map(profile => `
            <div class="profile-card">
                <h3>${profile.profile_name}</h3>
                <p>Device: ${profile.device_name}</p>
                <p style="font-size: 12px; color: var(--text-muted);">Rules: ${profile.rules_count}</p>
                <div class="button-group" style="display: flex; gap: 8px; margin-top: 12px;">
                    <button onclick="editProfile('${profile.profile_name}')" class="btn btn-small btn-secondary" style="flex: 1;">Edit</button>
                    <button onclick="deleteProfile('${profile.profile_name}')" class="btn btn-small btn-danger" style="flex: 1;">Delete</button>
                </div>
            </div>
        `).join('');
    
    } catch (error) {
        console.error('Error loading profiles:', error);
        document.getElementById('profiles-container').innerHTML = `<div class="alert alert-danger">Error loading profiles: ${error.message}</div>`;
    }
}

async function loadConnectedDevices() {
    try {
        const devices = await apiGet('/api/device/detect');
        const deviceSelect = document.getElementById('device-select');
        
        if (!devices || devices.length === 0) {
            deviceSelect.innerHTML = '<option value="">No devices connected</option>';
            return;
        }
        
        // Build options
        let html = '<option value="">Select a device...</option>';
        devices.forEach(device => {
            html += `<option value="${device.mtp_id}" data-device-name="${device.device_name}">${device.device_name}</option>`;
        });
        deviceSelect.innerHTML = html;
    } catch (error) {
        console.error('Error loading devices:', error);
        const deviceSelect = document.getElementById('device-select');
        deviceSelect.innerHTML = '<option value="">Error loading devices</option>';
    }
}

function openAddModal() {
    const modal = document.getElementById('add-modal');
    const deviceSelect = document.getElementById('device-select');
    
    // Reset for new profile creation
    modal.dataset.editingProfile = '';
    document.querySelector('.modal-header h2').textContent = 'Add Device Profile';
    document.querySelector('.btn-success').textContent = 'Add Profile';
    document.getElementById('profile-name').value = '';
    
    // Re-enable device select for new profiles
    deviceSelect.disabled = false;
    deviceSelect.value = '';  // Clear selection
    
    // Load connected devices
    loadConnectedDevices();
    
    // Check if we have prefilled device info from dashboard
    if (window.prefilledDevice) {
        const device = window.prefilledDevice;
        // Pre-fill profile name with device name
        document.getElementById('profile-name').value = device.name || '';
        // Select the device
        setTimeout(() => {
            deviceSelect.value = device.mtp_id || '';
        }, 100);
        // Clear the prefilled data so it doesn't persist
        delete window.prefilledDevice;
    }
    
    modal.style.display = 'flex';
}


async function deleteProfile(profileId) {
    if (!confirm('Are you sure you want to delete this profile?')) return;
    
    try {
        const response = await fetch(`/api/profiles/${profileId}`, { method: 'DELETE' });
        if (response.ok) {
            loadProfiles();
            showSuccess('Profile deleted successfully');
        } else {
            showError('Failed to delete profile');
        }
    } catch (error) {
        console.error('Error deleting profile:', error);
        showError('Failed to delete profile');
    }
}

function editProfile(profileName) {
    const modal = document.getElementById('add-modal');
    const profileNameInput = document.getElementById('profile-name');
    const deviceSelect = document.getElementById('device-select');
    const saveBtn = modal.querySelector('.btn-success');
    
    // Store current profile name for later
    modal.dataset.editingProfile = profileName;
    
    // Set form title
    document.querySelector('.modal-header h2').textContent = 'Edit Profile';
    saveBtn.textContent = 'Update Profile';
    profileNameInput.value = profileName;
    
    // Disable device select for editing (can't change device)
    deviceSelect.disabled = true;
    deviceSelect.value = '';
    
    modal.style.display = 'flex';
}

async function saveProfile() {
    const name = document.getElementById('profile-name').value;
    const deviceId = document.getElementById('device-select').value;
    const modal = document.getElementById('add-modal');
    const editingProfile = modal.dataset.editingProfile;
    
    // When editing, only name is required; when creating, both are required
    if (!name) {
        showError('Profile name is required');
        return;
    }
    
    if (!editingProfile && !deviceId) {
        showError('Please select a device');
        return;
    }
    
    try {
        // If editing, use PUT; if creating, use POST
        const method = editingProfile ? 'PUT' : 'POST';
        const url = editingProfile ? `/api/profiles/${editingProfile}` : '/api/profiles';
        
        const body = { name };
        if (!editingProfile) {
            body.device_id = deviceId;
        }
        
        const response = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        
        if (response.ok) {
            closeModal();
            loadProfiles();
            showSuccess(editingProfile ? 'Profile updated successfully' : 'Profile created successfully');
        } else {
            showError(editingProfile ? 'Failed to update profile' : 'Failed to create profile');
        }
    } catch (error) {
        console.error('Error saving profile:', error);
        showError('Failed to save profile');
    }
}

function closeModal() {
    const modal = document.getElementById('add-modal');
    const deviceSelect = document.getElementById('device-select');
    modal.dataset.editingProfile = '';
    document.getElementById('profile-name').value = '';
    deviceSelect.disabled = false;  // Re-enable for next add
    modal.style.display = 'none';
    document.querySelector('.modal-header h2').textContent = 'Add Device Profile';
    modal.querySelector('.btn-success').textContent = 'Add Profile';
}

// Load profiles on page load
document.addEventListener('DOMContentLoaded', async () => {
    loadProfiles();
    
    // Auto-open modal if coming from dashboard with prefilled device
    if (window.prefilledDevice) {
        // Small delay to ensure DOM is ready
        setTimeout(() => {
            openAddModal();
        }, 100);
    }
});
