// Chat functionality
class Chatbot {
    constructor() {
        this.chatMessages = document.getElementById('chatMessages');
        this.chatInput = document.getElementById('chatInput');
        this.sendButton = document.getElementById('sendButton');
        this.typingIndicator = document.getElementById('typingIndicator');
        this.statusDot = document.getElementById('statusDot');
        this.statusText = document.getElementById('statusText');
        
        this.messageHistory = [];
        this.isProcessing = false;
        this.retryCount = 0;
        this.maxRetries = 3;
        
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.checkApiStatus();
        this.loadMessageHistory();
        this.scrollToBottom();
    }

    setupEventListeners() {
        // Input handling
        this.chatInput.addEventListener('input', () => this.handleInput());
        this.chatInput.addEventListener('keydown', (e) => this.handleKeyPress(e));
        
        // Send button
        this.sendButton.addEventListener('click', () => this.sendMessage());
        
        // Focus input on load
        this.chatInput.focus();
    }

    handleInput() {
        const hasText = this.chatInput.value.trim().length > 0;
        this.sendButton.disabled = !hasText || this.isProcessing;
        
        // Auto-resize textarea
        this.chatInput.style.height = 'auto';
        this.chatInput.style.height = Math.min(this.chatInput.scrollHeight, 150) + 'px';
    }

    handleKeyPress(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!this.sendButton.disabled) {
                this.sendMessage();
            }
        }
    }

    async checkApiStatus() {
        try {
            const response = await fetch('/api/status');
            const data = await response.json();
            
            if (data.status === 'operational') {
                this.statusDot.className = 'status-dot';
                this.statusText.textContent = 'Online';
            } else {
                this.setOfflineStatus();
            }
        } catch (error) {
            console.error('API status check failed:', error);
            this.setOfflineStatus();
        }
    }

    setOfflineStatus() {
        this.statusDot.className = 'status-dot offline';
        this.statusText.textContent = 'Offline (Fallback Mode)';
    }

    async sendMessage() {
        const message = this.chatInput.value.trim();
        if (!message || this.isProcessing) return;

        // Add user message to chat
        this.addMessage(message, 'user');
        
        // Clear input
        this.chatInput.value = '';
        this.chatInput.style.height = 'auto';
        this.sendButton.disabled = true;
        
        // Show typing indicator
        this.showTypingIndicator();
        
        // Save to history
        this.saveToHistory(message, 'user');
        
        // Reset retry count for new message
        this.retryCount = 0;
        
        // Send to API
        await this.sendToAPI(message);
    }

    async sendToAPI(message) {
        this.isProcessing = true;
        
        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: message })
            });
            
            const data = await response.json();
            
            // Hide typing indicator
            this.hideTypingIndicator();
            
            if (data.success) {
                // Add bot response
                this.addMessage(data.response, 'bot');
                this.saveToHistory(data.response, 'bot');
                this.retryCount = 0;
            } else {
                throw new Error(data.error || 'Failed to get response');
            }
            
        } catch (error) {
            console.error('Chat API error:', error);
            
            // Retry logic
            if (this.retryCount < this.maxRetries) {
                this.retryCount++;
                console.log(`Retrying... (${this.retryCount}/${this.maxRetries})`);
                
                // Show retry message
                this.hideTypingIndicator();
                this.addMessage(`Connection issue. Retrying... (${this.retryCount}/${this.maxRetries})`, 'bot');
                this.showTypingIndicator();
                
                // Wait 2 seconds then retry
                setTimeout(() => this.sendToAPI(message), 2000);
            } else {
                // Max retries exceeded, show error
                this.hideTypingIndicator();
                this.addMessage(
                    'Sorry, I\'m having trouble connecting. Please try again later or check our <a href="/guides">Guides section</a> for help.',
                    'bot'
                );
                this.isProcessing = false;
            }
        }
    }

    addMessage(content, type) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}`;
        
        // Create avatar
        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'message-avatar';
        avatarDiv.innerHTML = type === 'user' 
            ? '<i class="fas fa-user"></i>' 
            : '<i class="fas fa-robot"></i>';
        
        // Create content container
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        // Handle markdown-like formatting
        const formattedContent = this.formatMessage(content);
        contentDiv.innerHTML = formattedContent;
        
        // Add timestamp
        const timeDiv = document.createElement('div');
        timeDiv.className = 'message-time';
        timeDiv.textContent = this.getCurrentTime();
        contentDiv.appendChild(timeDiv);
        
        // Assemble message
        if (type === 'user') {
            messageDiv.appendChild(contentDiv);
            messageDiv.appendChild(avatarDiv);
        } else {
            messageDiv.appendChild(avatarDiv);
            messageDiv.appendChild(contentDiv);
        }
        
        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }

    formatMessage(content) {
        // Convert URLs to links
        content = content.replace(
            /(https?:\/\/[^\s]+)/g, 
            '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>'
        );
        
        // Convert bullet points
        content = content.replace(/^•/gm, '•');
        
        // Convert line breaks
        content = content.replace(/\n/g, '<br>');
        
        return content;
    }

    showTypingIndicator() {
        this.typingIndicator.style.display = 'flex';
        this.scrollToBottom();
    }

    hideTypingIndicator() {
        this.typingIndicator.style.display = 'none';
        this.isProcessing = false;
        
        // Re-enable send button if there's text
        if (this.chatInput.value.trim().length > 0) {
            this.sendButton.disabled = false;
        }
    }

    saveToHistory(message, type) {
        this.messageHistory.push({
            type: type,
            message: message,
            timestamp: new Date().toISOString()
        });
        
        // Keep only last 50 messages
        if (this.messageHistory.length > 50) {
            this.messageHistory.shift();
        }
        
        // Save to localStorage
        try {
            localStorage.setItem('chatHistory', JSON.stringify(this.messageHistory));
        } catch (e) {
            console.warn('Failed to save chat history:', e);
        }
    }

    loadMessageHistory() {
        try {
            const saved = localStorage.getItem('chatHistory');
            if (saved) {
                this.messageHistory = JSON.parse(saved);
                
                // Restore last 10 messages
                const recentMessages = this.messageHistory.slice(-10);
                recentMessages.forEach(msg => {
                    this.addMessage(msg.message, msg.type);
                });
            }
        } catch (e) {
            console.warn('Failed to load chat history:', e);
        }
    }

    clearHistory() {
        this.messageHistory = [];
        localStorage.removeItem('chatHistory');
        
        // Clear messages but keep welcome message
        this.chatMessages.innerHTML = '';
        this.addMessage(
            'Hello! I\'m your KUCCPS Courses Assistant. How can I help you today?',
            'bot'
        );
    }

    getCurrentTime() {
        const now = new Date();
        return now.toLocaleTimeString('en-US', { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
    }

    scrollToBottom() {
        setTimeout(() => {
            this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
        }, 100);
    }
}

// Quick question handler
function sendQuickQuestion(question) {
    const chatInput = document.getElementById('chatInput');
    const sendButton = document.getElementById('sendButton');
    
    chatInput.value = question;
    chatInput.dispatchEvent(new Event('input'));
    
    if (!sendButton.disabled) {
        document.querySelector('.chat-send-btn').click();
    }
}

// Initialize chatbot when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Only initialize on chat page
    if (document.querySelector('.chat-container')) {
        window.chatbot = new Chatbot();
    }
});