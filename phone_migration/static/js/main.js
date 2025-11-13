// Shared API utility functions
async function apiGet(url) {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    return await response.json();
}

async function apiPost(url, data) {
    const response = await fetch(url, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    });
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    return await response.json();
}

async function apiDelete(url) {
    const response = await fetch(url, {method: 'DELETE'});
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    return await response.json();
}

// Shared UI utility functions
function showError(message) {
    const container = document.getElementById('alert-container');
    if (!container) return;
    
    const alert = document.createElement('div');
    alert.className = 'alert alert-danger';
    alert.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${message}`;
    container.appendChild(alert);
    
    setTimeout(() => alert.remove(), 5000);
}

function showSuccess(message) {
    const container = document.getElementById('alert-container');
    if (!container) return;
    
    const alert = document.createElement('div');
    alert.className = 'alert alert-success';
    alert.innerHTML = `<i class="fas fa-check-circle"></i> ${message}`;
    container.appendChild(alert);
    
    setTimeout(() => alert.remove(), 5000);
}

function showInfo(message) {
    const container = document.getElementById('alert-container');
    if (!container) return;
    
    const alert = document.createElement('div');
    alert.className = 'alert alert-info';
    alert.innerHTML = `<i class="fas fa-info-circle"></i> ${message}`;
    container.appendChild(alert);
    
    setTimeout(() => alert.remove(), 5000);
}

function showAlert(message, type = 'success') {
    if (type === 'success') {
        showSuccess(message);
    } else if (type === 'danger' || type === 'error') {
        showError(message);
    } else if (type === 'info') {
        showInfo(message);
    } else {
        showSuccess(message);
    }
}
