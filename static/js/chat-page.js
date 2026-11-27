(() => {
  'use strict';

  let chatMessages = [];
  let chats = [];
  let currentChatId = null;
  let isTyping = false;
  let toastTimer;

  const byId = (id) => document.getElementById(id);
  const input = () => byId('messageInput');
  const messagesArea = () => byId('messagesArea');

  function escapeHtml(value) {
    return String(value || '').replace(/[&<>"']/g, (char) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[char]);
  }

  function formatMessage(value) {
    const escaped = escapeHtml(value);
    const linked = escaped.replace(/(https?:\/\/[^\s<]+)/g, (url) => {
      const cleanUrl = url.replace(/[),.;!?]+$/, '');
      const trailing = url.slice(cleanUrl.length);
      return `<a href="${cleanUrl}" target="_blank" rel="noopener noreferrer">${cleanUrl}</a>${trailing}`;
    });
    return linked.replace(/\n/g, '<br>');
  }

  function saveChats() {
    try { localStorage.setItem('kuccps_chats', JSON.stringify(chats.slice(0, 30))); }
    catch (_) { showToast('This device could not save the conversation.'); }
  }

  function saveCurrentChat() {
    if (!currentChatId) return;
    const chat = chats.find((item) => item.id === currentChatId);
    if (chat) {
      chat.messages = chatMessages.slice(-50);
      chat.updatedAt = new Date().toISOString();
      const firstQuestion = chatMessages.find((message) => message.sender === 'user');
      if (firstQuestion) chat.title = firstQuestion.text.slice(0, 38);
    }
    saveChats();
    renderChatHistory();
  }

  function loadChats() {
    try {
      const stored = JSON.parse(localStorage.getItem('kuccps_chats') || '[]');
      chats = Array.isArray(stored) ? stored.filter((item) => item && typeof item.id === 'string' && Array.isArray(item.messages)) : [];
    } catch (_) { chats = []; }

    if (chats.length) {
      chats.sort((a, b) => Date.parse(b.updatedAt || 0) - Date.parse(a.updatedAt || 0));
      currentChatId = chats[0].id;
      chatMessages = chats[0].messages.slice(-50);
    } else {
      createChat(false);
    }
    renderChatHistory();
    renderMessages();
  }

  function renderChatHistory() {
    const history = byId('chatHistory');
    if (!history) return;
    history.replaceChildren();
    if (!chats.length) {
      const empty = document.createElement('p');
      empty.className = 'chat-history-empty';
      empty.textContent = 'Your saved conversations will appear here.';
      history.appendChild(empty);
      return;
    }

    chats.forEach((chat) => {
      const row = document.createElement('div');
      row.className = `chat-history-item${chat.id === currentChatId ? ' active' : ''}`;
      row.setAttribute('role', 'button');
      row.setAttribute('tabindex', '0');
      row.setAttribute('aria-current', chat.id === currentChatId ? 'true' : 'false');
      row.dataset.chatId = chat.id;

      const icon = document.createElement('i');
      icon.className = 'far fa-comment-dots';
      icon.setAttribute('aria-hidden', 'true');
      const title = document.createElement('span');
      title.className = 'chat-title';
      title.textContent = chat.title || 'New conversation';
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'chat-history-action';
      remove.dataset.deleteChat = chat.id;
      remove.setAttribute('aria-label', `Delete conversation: ${chat.title || 'New conversation'}`);
      remove.innerHTML = '<i class="far fa-trash-alt" aria-hidden="true"></i>';
      row.append(icon, title, remove);
      history.appendChild(row);
    });
  }

  function createChat(confirmBefore = true) {
    if (confirmBefore && chatMessages.length && !window.confirm('Start a new conversation? Your current chat will remain saved on this device.')) return;
    const chat = { id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`, title: 'New conversation', messages: [], createdAt: new Date().toISOString(), updatedAt: new Date().toISOString() };
    chats.unshift(chat);
    currentChatId = chat.id;
    chatMessages = [];
    saveChats();
    renderChatHistory();
    renderMessages();
    input()?.focus({ preventScroll: true });
    closeSidebar();
  }

  function deleteChat(chatId) {
    if (!window.confirm('Delete this conversation from this device?')) return;
    chats = chats.filter((chat) => chat.id !== chatId);
    if (currentChatId === chatId) {
      currentChatId = chats[0]?.id || null;
      chatMessages = chats[0]?.messages?.slice(-50) || [];
      if (!currentChatId) createChat(false);
    }
    saveChats();
    renderChatHistory();
    renderMessages();
  }

  function renderMessages() {
    const area = messagesArea();
    const welcome = byId('welcomeScreen');
    if (!area || !welcome) return;
    area.querySelectorAll('.message-wrapper').forEach((node) => node.remove());
    welcome.hidden = chatMessages.length > 0;
    chatMessages.slice(-50).forEach((message) => area.appendChild(makeMessage(message.text, message.sender, message.time)));
    area.scrollTop = area.scrollHeight;
  }

  function makeMessage(text, sender, time) {
    const wrapper = document.createElement('article');
    wrapper.className = `message-wrapper ${sender === 'user' ? 'user' : 'bot'}`;
    wrapper.setAttribute('aria-label', sender === 'user' ? 'Your message' : 'Courses Checker Assistant response');
    const avatar = document.createElement('span');
    avatar.className = 'message-avatar';
    avatar.setAttribute('aria-hidden', 'true');
    avatar.innerHTML = sender === 'user' ? '<i class="fas fa-user"></i>' : '<i class="fas fa-graduation-cap"></i>';
    const content = document.createElement('div');
    content.className = 'message-content';
    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    bubble.innerHTML = formatMessage(text);
    const timestamp = document.createElement('div');
    timestamp.className = 'message-time';
    timestamp.textContent = time || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    content.append(bubble, timestamp);
    wrapper.append(avatar, content);
    return wrapper;
  }

  function addMessage(text, sender) {
    const item = { text: String(text || ''), sender, time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) };
    chatMessages.push(item);
    chatMessages = chatMessages.slice(-50);
    saveCurrentChat();
    const welcome = byId('welcomeScreen');
    if (welcome) welcome.hidden = true;
    messagesArea()?.appendChild(makeMessage(item.text, sender, item.time));
    if (messagesArea()) messagesArea().scrollTop = messagesArea().scrollHeight;
  }

  function showTypingIndicator() {
    isTyping = true;
    const button = byId('sendButton');
    if (button) button.disabled = true;
    const indicator = document.createElement('article');
    indicator.className = 'message-wrapper bot';
    indicator.id = 'typingIndicator';
    indicator.setAttribute('aria-label', 'Assistant is preparing a response');
    indicator.innerHTML = '<span class="message-avatar" aria-hidden="true"><i class="fas fa-graduation-cap"></i></span><div class="message-content"><div class="typing-indicator" role="status" aria-label="Thinking"><span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span></div></div>';
    messagesArea()?.appendChild(indicator);
    if (messagesArea()) messagesArea().scrollTop = messagesArea().scrollHeight;
  }

  function hideTypingIndicator() {
    isTyping = false;
    byId('typingIndicator')?.remove();
    const send = byId('sendButton');
    if (send) send.disabled = !input()?.value.trim();
  }

  async function sendMessage() {
    const field = input();
    const message = field?.value.trim();
    if (!message || isTyping) return;
    addMessage(message, 'user');
    field.value = '';
    field.style.height = 'auto';
    const send = byId('sendButton');
    if (send) send.disabled = true;
    showTypingIndicator();

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify({ message })
      });
      const data = await response.json();
      if (!response.ok || !data.success || typeof data.response !== 'string') {
        throw new Error(data.error || 'The assistant could not answer just now.');
      }
      hideTypingIndicator();
      addMessage(data.response, 'bot');
    } catch (error) {
      hideTypingIndicator();
      addMessage(error.message || 'I could not connect just now. Please try again, or browse the Courses Checker guides.', 'bot');
    }
  }

  function clearChat() {
    if (!chatMessages.length || !window.confirm('Clear the messages in this conversation?')) return;
    chatMessages = [];
    saveCurrentChat();
    renderMessages();
    closeSidebar();
  }

  function exportChat() {
    if (!chatMessages.length) { showToast('There are no messages to export yet.'); return; }
    const content = ['Courses Checker Assistant conversation', '========================================', '', ...chatMessages.map((item) => `[${item.time || ''}] ${item.sender === 'user' ? 'You' : 'Assistant'}:\n${item.text}\n`)].join('\n');
    const blobUrl = URL.createObjectURL(new Blob([content], { type: 'text/plain;charset=utf-8' }));
    const anchor = document.createElement('a');
    anchor.href = blobUrl;
    anchor.download = `courses-checker-chat-${new Date().toISOString().slice(0, 10)}.txt`;
    anchor.click();
    URL.revokeObjectURL(blobUrl);
    showToast('Conversation exported.');
  }

  function showToast(message) {
    const toast = byId('linkToast');
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('show'), 2400);
  }

  function autoResize(field) {
    field.style.height = 'auto';
    field.style.height = `${Math.min(field.scrollHeight, 140)}px`;
    const button = byId('sendButton');
    if (button) button.disabled = !field.value.trim() || isTyping;
  }

  function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  }

  function askQuestion(question) {
    if (!input()) return;
    input().value = question;
    autoResize(input());
    sendMessage();
  }

  function toggleSidebar() {
    if (window.innerWidth > 760) return;
    const sidebar = byId('chatSidebar');
    const overlay = byId('sidebarOverlay');
    const menu = byId('chatMenuButton');
    const isOpen = sidebar?.classList.toggle('open') || false;
    sidebar?.setAttribute('aria-hidden', String(!isOpen));
    if (sidebar) sidebar.inert = !isOpen;
    overlay?.classList.toggle('show', isOpen);
    menu?.setAttribute('aria-expanded', String(isOpen));
  }

  function closeSidebar() {
    const sidebar = byId('chatSidebar');
    sidebar?.classList.remove('open');
    const hiddenOnMobile = window.innerWidth <= 760;
    sidebar?.setAttribute('aria-hidden', String(hiddenOnMobile));
    if (sidebar) sidebar.inert = hiddenOnMobile;
    byId('sidebarOverlay')?.classList.remove('show');
    byId('chatMenuButton')?.setAttribute('aria-expanded', 'false');
  }

  async function checkStatus() {
    const dot = byId('statusDot');
    const label = byId('statusText');
    try {
      const response = await fetch('/api/status', { headers: { 'Accept': 'application/json' } });
      const status = await response.json();
      if (response.ok && status.status === 'operational') {
        label.textContent = 'Ready to help';
        dot.classList.remove('offline');
      } else {
        label.textContent = 'Limited availability';
        dot.classList.add('offline');
      }
    } catch (_) {
      label.textContent = 'Connection unavailable';
      dot?.classList.add('offline');
    }
  }

  function init() {
    closeSidebar();
    loadChats();
    checkStatus();
    document.querySelectorAll('.chat-suggestion').forEach((button) => button.addEventListener('click', () => askQuestion(button.dataset.question || button.textContent)));
    byId('chatHistory')?.addEventListener('click', (event) => {
      const remove = event.target.closest('[data-delete-chat]');
      if (remove) { event.stopPropagation(); deleteChat(remove.dataset.deleteChat); return; }
      const row = event.target.closest('[data-chat-id]');
      if (!row) return;
      const chat = chats.find((item) => item.id === row.dataset.chatId);
      if (!chat) return;
      currentChatId = chat.id;
      chatMessages = chat.messages.slice(-50);
      renderChatHistory();
      renderMessages();
      closeSidebar();
    });
    byId('chatHistory')?.addEventListener('keydown', (event) => {
      if ((event.key === 'Enter' || event.key === ' ') && event.target.matches('.chat-history-item')) {
        event.preventDefault();
        event.target.click();
      }
    });
    document.addEventListener('keydown', (event) => { if (event.key === 'Escape') closeSidebar(); });
    window.addEventListener('resize', () => { if (window.innerWidth > 760) closeSidebar(); }, { passive: true });
  }

  Object.assign(window, { startNewChat: createChat, sendMessage, clearChat, exportChat, showToast, autoResize, handleKeyPress, askQuestion, toggleSidebar, closeSidebar });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true });
  else init();
})();
