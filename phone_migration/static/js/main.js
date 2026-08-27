// Shared API utility functions
async function apiRequest(url, options) {
    const response = await fetch(url, options);
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.error || `API error: ${response.status}`);
    return body;
}

async function apiGet(url) {
    return apiRequest(url);
}

async function apiPost(url, data) {
    return apiRequest(url, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    });
}

async function apiPut(url, data) {
    return apiRequest(url, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    });
}

async function apiDelete(url) {
    return apiRequest(url, {method: 'DELETE'});
}

// Shared UI utility functions

// Escape server-supplied text before it reaches innerHTML. Phone filenames are
// attacker-controlled: a file named `<img onerror=...>` must never execute.
// Quotes are escaped too - values also land inside data-* attributes.
const HTML_ESCAPES = {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'};

function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    return String(text).replace(/[&<>"']/g, ch => HTML_ESCAPES[ch]);
}

function showAlertIcon(message, className, icon) {
    const container = document.getElementById('alert-container');
    if (!container) return;

    const alert = document.createElement('div');
    alert.className = `alert ${className}`;
    alert.innerHTML = `<i class="fas ${icon}"></i> ${escapeHtml(message)}`;
    container.appendChild(alert);

    setTimeout(() => alert.remove(), 5000);
}

function showError(message) {
    showAlertIcon(message, 'alert-danger', 'fa-exclamation-circle');
}

function showSuccess(message) {
    showAlertIcon(message, 'alert-success', 'fa-check-circle');
}

function showInfo(message) {
    showAlertIcon(message, 'alert-info', 'fa-info-circle');
}

function showAlert(message, type = 'success') {
    if (type === 'danger' || type === 'error') {
        showError(message);
    } else if (type === 'info') {
        showInfo(message);
    } else {
        showSuccess(message);
    }
}
