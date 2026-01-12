// static/js/pwa.js

// Register service worker
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/static/service-worker.js')
            .then(registration => {
                console.log('ServiceWorker registration successful with scope: ', registration.scope);
                
                // Check for updates
                registration.addEventListener('updatefound', () => {
                    const newWorker = registration.installing;
                    console.log('ServiceWorker update found!');
                    
                    newWorker.addEventListener('statechange', () => {
                        if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                            // New content is available, show update notification
                            showUpdateNotification();
                        }
                    });
                });
            })
            .catch(error => {
                console.log('ServiceWorker registration failed: ', error);
            });
    });
}

// Periodic sync for background updates
if ('periodicSync' in navigator && 'serviceWorker' in navigator) {
    navigator.serviceWorker.ready.then(registration => {
        registration.periodicSync.register('update-courses', {
            minInterval: 24 * 60 * 60 * 1000 // Once per day
        }).catch(err => {
            console.error('Periodic sync registration failed:', err);
        });
    });
}

// Handle offline/online status
window.addEventListener('online', () => {
    document.body.classList.remove('offline');
    showNotification('You are back online', 'success');
});

window.addEventListener('offline', () => {
    document.body.classList.add('offline');
    showNotification('You are offline. Some features may not work.', 'warning');
});

// Show update notification
function showUpdateNotification() {
    if (confirm('New version available. Update now?')) {
        window.location.reload();
    }
}

// Helper function for notifications
function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <span>${message}</span>
        <button onclick="this.parentElement.remove()">×</button>
    `;
    
    // Add styles
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 12px 20px;
        background: ${type === 'success' ? '#10b981' : type === 'warning' ? '#f59e0b' : '#3b82f6'};
        color: white;
        border-radius: 8px;
        display: flex;
        align-items: center;
        gap: 10px;
        z-index: 1000;
        animation: slideIn 0.3s ease;
    `;
    
    document.body.appendChild(notification);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        if (notification.parentElement) {
            notification.remove();
        }
    }, 5000);
}