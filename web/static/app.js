/**
 * OpenHT Web UI - Frontend JavaScript
 * Chat arayüzü, WebSocket bağlantısı, konuşma yönetimi
 */

// ==================== Global State ====================
let currentConversationId = null;
let ws = null;
let models = [];
let isProcessing = false;

// ==================== DOM Elements ====================
const chatMessages = document.getElementById('chatMessages');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const conversationsList = document.getElementById('conversationsList');
const chatTitle = document.getElementById('chatTitle');
const currentModelBadge = document.getElementById('currentModel');
const settingsPanel = document.getElementById('settingsPanel');
const loadingOverlay = document.getElementById('loadingOverlay');
const welcomeMessage = document.getElementById('welcomeMessage');
const modelSelect = document.getElementById('modelSelect');
const temperatureSlider = document.getElementById('temperatureSlider');
const tempValue = document.getElementById('tempValue');
const maxTokensInput = document.getElementById('maxTokensInput');
const systemPrompt = document.getElementById('systemPrompt');

// ==================== Initialization ====================
document.addEventListener('DOMContentLoaded', async () => {
    await loadModels();
    await loadConversations();
    autoResizeTextarea();

    // Configure marked for markdown rendering
    marked.setOptions({
        highlight: function (code, lang) {
            if (lang && hljs.getLanguage(lang)) {
                return hljs.highlight(code, { language: lang }).value;
            }
            return hljs.highlightAuto(code).value;
        },
        breaks: true
    });
});

// ==================== API Functions ====================
async function apiCall(endpoint, options = {}) {
    try {
        const response = await fetch(endpoint, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });

        if (!response.ok) {
            throw new Error(`API Error: ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

async function loadModels() {
    try {
        const data = await apiCall('/api/models');
        models = data.models;

        // Populate model select
        modelSelect.innerHTML = models.map(model =>
            `<option value="${model.id}">${model.name} (${model.provider})</option>`
        ).join('');
    } catch (error) {
        console.error('Failed to load models:', error);
    }
}

async function loadConversations() {
    try {
        const data = await apiCall('/api/conversations');
        renderConversationsList(data.conversations);
    } catch (error) {
        console.error('Failed to load conversations:', error);
    }
}

async function createNewChat() {
    try {
        const data = await apiCall('/api/conversations', {
            method: 'POST',
            body: JSON.stringify({ title: 'Yeni Sohbet' })
        });

        currentConversationId = data.id;
        chatTitle.textContent = data.title;
        clearChatMessages();
        showWelcomeMessage();
        await loadConversations();

        // Update active state
        updateActiveConversation(data.id);
    } catch (error) {
        console.error('Failed to create conversation:', error);
    }
}

async function loadConversation(convId) {
    try {
        const data = await apiCall(`/api/conversations/${convId}`);

        currentConversationId = data.id;
        chatTitle.textContent = data.title;

        // Update settings
        modelSelect.value = data.model;
        currentModelBadge.textContent = data.model.split('/')[1] || data.model;

        if (data.settings) {
            temperatureSlider.value = data.settings.temperature || 1.0;
            tempValue.textContent = temperatureSlider.value;
            maxTokensInput.value = data.settings.max_tokens || 4096;
            systemPrompt.value = data.settings.system_prompt || '';
        }

        // Render messages
        clearChatMessages();

        if (data.messages.length === 0) {
            showWelcomeMessage();
        } else {
            hideWelcomeMessage();
            data.messages.forEach(msg => {
                addMessageToChat(msg.role, msg.content);
            });
        }

        updateActiveConversation(convId);
    } catch (error) {
        console.error('Failed to load conversation:', error);
    }
}

async function deleteConversation(convId, event) {
    event.stopPropagation();

    if (!confirm('Bu sohbeti silmek istediğinizden emin misiniz?')) {
        return;
    }

    try {
        await apiCall(`/api/conversations/${convId}`, {
            method: 'DELETE'
        });

        if (currentConversationId === convId) {
            currentConversationId = null;
            chatTitle.textContent = 'Yeni Sohbet';
            clearChatMessages();
            showWelcomeMessage();
        }

        await loadConversations();
    } catch (error) {
        console.error('Failed to delete conversation:', error);
    }
}

// ==================== Send Message ====================
async function sendMessage() {
    const message = messageInput.value.trim();

    if (!message || isProcessing) return;

    // Ensure we have a conversation
    if (!currentConversationId) {
        await createNewChat();
    }

    // Clear input
    messageInput.value = '';
    autoResizeTextarea();

    // Hide welcome message
    hideWelcomeMessage();

    // Add user message to chat
    addMessageToChat('user', message);

    // Show loading
    setProcessing(true);

    try {
        // Use simple POST endpoint instead of WebSocket for simplicity
        const data = await apiCall('/api/chat', {
            method: 'POST',
            body: JSON.stringify({
                conversation_id: currentConversationId,
                message: message
            })
        });

        // Add assistant response
        if (data.response) {
            addMessageToChat('assistant', data.response);
        }

        // Refresh conversations list (title might have updated)
        await loadConversations();

    } catch (error) {
        console.error('Failed to send message:', error);
        addMessageToChat('assistant', `❌ Hata: ${error.message}`);
    } finally {
        setProcessing(false);
    }
}

function sendQuickMessage(text) {
    messageInput.value = text;
    sendMessage();
}

// ==================== UI Functions ====================
function renderConversationsList(conversations) {
    if (conversations.length === 0) {
        conversationsList.innerHTML = `
            <div class="empty-state" style="text-align: center; padding: 20px; color: var(--text-muted);">
                <p>Henüz sohbet yok</p>
            </div>
        `;
        return;
    }

    conversationsList.innerHTML = conversations.map(conv => `
        <div class="conversation-item ${conv.id === currentConversationId ? 'active' : ''}"
             onclick="loadConversation('${conv.id}')">
            <span class="icon">💬</span>
            <span class="title">${escapeHtml(conv.title)}</span>
            <button class="delete-btn" onclick="deleteConversation('${conv.id}', event)">🗑️</button>
        </div>
    `).join('');
}

function addMessageToChat(role, content) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;

    const avatar = role === 'user' ? '👤' : '🤖';
    const renderedContent = role === 'assistant' ? marked.parse(content) : escapeHtml(content);

    messageDiv.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-content">${renderedContent}</div>
    `;

    chatMessages.appendChild(messageDiv);

    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;

    // Highlight code blocks
    messageDiv.querySelectorAll('pre code').forEach(block => {
        hljs.highlightElement(block);
    });
}

function clearChatMessages() {
    chatMessages.innerHTML = '';
}

function showWelcomeMessage() {
    if (welcomeMessage) {
        welcomeMessage.style.display = 'block';
    } else {
        chatMessages.innerHTML = `
            <div class="welcome-message" id="welcomeMessage">
                <div class="welcome-icon">🤖</div>
                <h2>OpenHT'ye Hoş Geldiniz</h2>
                <p>Size nasıl yardımcı olabilirim?</p>
                <div class="quick-actions">
                    <button onclick="sendQuickMessage('Python ile basit bir web scraper yaz')">
                        🐍 Web Scraper
                    </button>
                    <button onclick="sendQuickMessage('Türkiye ekonomisi hakkında güncel bilgi ver')">
                        📊 Ekonomi Bilgisi
                    </button>
                    <button onclick="sendQuickMessage('Markdown formatında bir README şablonu oluştur')">
                        📝 README Şablonu
                    </button>
                </div>
            </div>
        `;
    }
}

function hideWelcomeMessage() {
    const welcome = document.getElementById('welcomeMessage');
    if (welcome) {
        welcome.style.display = 'none';
    }
}

function updateActiveConversation(convId) {
    document.querySelectorAll('.conversation-item').forEach(item => {
        item.classList.remove('active');
    });

    const activeItem = document.querySelector(`.conversation-item[onclick="loadConversation('${convId}')"]`);
    if (activeItem) {
        activeItem.classList.add('active');
    }
}

function setProcessing(processing) {
    isProcessing = processing;
    sendBtn.disabled = processing;

    if (processing) {
        loadingOverlay.classList.add('active');
    } else {
        loadingOverlay.classList.remove('active');
    }
}

// ==================== Settings ====================
function toggleSettings() {
    settingsPanel.classList.toggle('open');
}

async function updateModel() {
    const model = modelSelect.value;
    currentModelBadge.textContent = model.split('/')[1] || model;

    if (currentConversationId) {
        await updateConversationSettings({ model });
    }
}

async function updateTemperature() {
    const temp = parseFloat(temperatureSlider.value);
    tempValue.textContent = temp.toFixed(1);

    if (currentConversationId) {
        await updateConversationSettings({ temperature: temp });
    }
}

async function updateMaxTokens() {
    const maxTokens = parseInt(maxTokensInput.value);

    if (currentConversationId) {
        await updateConversationSettings({ max_tokens: maxTokens });
    }
}

async function updateSystemPrompt() {
    const prompt = systemPrompt.value;

    if (currentConversationId) {
        await updateConversationSettings({ system_prompt: prompt });
    }
}

async function updateConversationSettings(settings) {
    if (!currentConversationId) return;

    try {
        await apiCall(`/api/conversations/${currentConversationId}/settings`, {
            method: 'PUT',
            body: JSON.stringify(settings)
        });
    } catch (error) {
        console.error('Failed to update settings:', error);
    }
}

// ==================== Input Handling ====================
function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

function autoResizeTextarea() {
    messageInput.style.height = 'auto';
    messageInput.style.height = Math.min(messageInput.scrollHeight, 150) + 'px';
}

messageInput.addEventListener('input', autoResizeTextarea);

// ==================== Utilities ====================
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ==================== Error Handling ====================
window.onerror = function (msg, url, lineNo, columnNo, error) {
    console.error('Error:', msg, url, lineNo, columnNo, error);
    return false;
};

// ==================== File Handling ====================
let attachedFiles = [];
let attachedLinks = [];
let codeModeActive = false;

function handleFileSelect(event) {
    const files = Array.from(event.target.files);
    addFilesToList(files);
    event.target.value = ''; // Reset input
}

function handleMediaSelect(event) {
    const files = Array.from(event.target.files);
    addFilesToList(files, true);
    event.target.value = ''; // Reset input
}

function addFilesToList(files, isMedia = false) {
    files.forEach(file => {
        const fileObj = {
            id: Date.now() + Math.random(),
            file: file,
            name: file.name,
            type: file.type,
            size: file.size,
            isMedia: isMedia
        };

        // Create preview for images
        if (file.type.startsWith('image/')) {
            const reader = new FileReader();
            reader.onload = (e) => {
                fileObj.preview = e.target.result;
                renderAttachedFiles();
            };
            reader.readAsDataURL(file);
        }

        attachedFiles.push(fileObj);
    });

    updateFileDisplay();
}

function removeFile(fileId) {
    attachedFiles = attachedFiles.filter(f => f.id !== fileId);
    updateFileDisplay();
}

function clearAllFiles() {
    attachedFiles = [];
    attachedLinks = [];
    updateFileDisplay();
}

function updateFileDisplay() {
    const container = document.getElementById('attachedFiles');
    const list = document.getElementById('attachedFilesList');
    const countBadge = document.getElementById('fileCount');

    const totalItems = attachedFiles.length + attachedLinks.length;

    if (totalItems === 0) {
        container.style.display = 'none';
        countBadge.style.display = 'none';
    } else {
        container.style.display = 'block';
        countBadge.style.display = 'inline';
        countBadge.textContent = `${totalItems} dosya ekli`;
        renderAttachedFiles();
    }
}

function renderAttachedFiles() {
    const list = document.getElementById('attachedFilesList');

    let html = '';

    // Render files
    attachedFiles.forEach(file => {
        if (file.preview) {
            html += `
                <div class="file-item image-file">
                    <img src="${file.preview}" alt="${file.name}">
                    <span class="file-name">${file.name}</span>
                    <button class="remove-file" onclick="removeFile(${file.id})">✕</button>
                </div>
            `;
        } else {
            const icon = getFileIcon(file.type);
            html += `
                <div class="file-item">
                    <span>${icon}</span>
                    <span class="file-name">${file.name}</span>
                    <span style="color: var(--text-muted); font-size: 0.7rem;">${formatFileSize(file.size)}</span>
                    <button class="remove-file" onclick="removeFile(${file.id})">✕</button>
                </div>
            `;
        }
    });

    // Render links
    attachedLinks.forEach((link, index) => {
        html += `
            <div class="link-item">
                <span class="link-icon">🔗</span>
                <span class="link-text">${link.title || link.url}</span>
                <button class="remove-file" onclick="removeLink(${index})">✕</button>
            </div>
        `;
    });

    list.innerHTML = html;
}

function getFileIcon(type) {
    if (type.startsWith('image/')) return '🖼️';
    if (type.startsWith('video/')) return '🎬';
    if (type.startsWith('audio/')) return '🎵';
    if (type.includes('pdf')) return '📕';
    if (type.includes('word') || type.includes('document')) return '📘';
    if (type.includes('excel') || type.includes('spreadsheet')) return '📗';
    if (type.includes('zip') || type.includes('rar') || type.includes('tar')) return '📦';
    if (type.includes('text') || type.includes('json') || type.includes('javascript') || type.includes('python')) return '📄';
    return '📎';
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

// ==================== Drag and Drop ====================
function handleDragOver(event) {
    event.preventDefault();
    event.stopPropagation();
    document.querySelector('.input-container').classList.add('drag-over');
}

function handleDragLeave(event) {
    event.preventDefault();
    event.stopPropagation();
    document.querySelector('.input-container').classList.remove('drag-over');
}

function handleFileDrop(event) {
    event.preventDefault();
    event.stopPropagation();
    document.querySelector('.input-container').classList.remove('drag-over');

    const files = Array.from(event.dataTransfer.files);
    if (files.length > 0) {
        addFilesToList(files);
    }

    // Check for dropped URLs
    const text = event.dataTransfer.getData('text');
    if (text && (text.startsWith('http://') || text.startsWith('https://'))) {
        attachedLinks.push({ url: text, title: '' });
        updateFileDisplay();
    }
}

// ==================== Link Dialog ====================
function showLinkDialog() {
    document.getElementById('linkDialog').style.display = 'flex';
    document.getElementById('linkUrl').focus();
}

function closeLinkDialog(event) {
    if (event && event.target !== event.currentTarget) return;
    document.getElementById('linkDialog').style.display = 'none';
    document.getElementById('linkUrl').value = '';
    document.getElementById('linkTitle').value = '';
}

function addLink() {
    const url = document.getElementById('linkUrl').value.trim();
    const title = document.getElementById('linkTitle').value.trim();

    if (!url) {
        alert('Lütfen bir URL girin');
        return;
    }

    // Validate URL
    try {
        new URL(url);
    } catch {
        alert('Geçerli bir URL girin');
        return;
    }

    attachedLinks.push({ url, title });
    updateFileDisplay();
    closeLinkDialog();
}

function removeLink(index) {
    attachedLinks.splice(index, 1);
    updateFileDisplay();
}

// ==================== Code Mode ====================
function toggleCodeMode() {
    codeModeActive = !codeModeActive;
    const btn = document.getElementById('codeModeBtn');

    if (codeModeActive) {
        btn.classList.add('active');
        messageInput.placeholder = '```python\n# Kodunuzu buraya yazın...\n```';
        messageInput.style.fontFamily = "'JetBrains Mono', 'Fira Code', monospace";
        messageInput.style.fontSize = '0.9rem';
    } else {
        btn.classList.remove('active');
        messageInput.placeholder = 'Mesajınızı yazın veya dosya sürükleyip bırakın...';
        messageInput.style.fontFamily = 'inherit';
        messageInput.style.fontSize = '1rem';
    }
}

// ==================== Enhanced Send Message ====================
// Override the original sendMessage to include attachments
const originalSendMessage = sendMessage;

sendMessage = async function () {
    let message = messageInput.value.trim();

    // Add attached links to message
    if (attachedLinks.length > 0) {
        const linksText = attachedLinks.map(l => `🔗 ${l.title || l.url}: ${l.url}`).join('\n');
        message = message ? `${message}\n\n📎 Eklenen linkler:\n${linksText}` : `📎 Analiz edilecek linkler:\n${linksText}`;
    }

    // Add file info to message
    if (attachedFiles.length > 0) {
        const filesText = attachedFiles.map(f => `📄 ${f.name} (${formatFileSize(f.size)})`).join('\n');
        message = message ? `${message}\n\n📎 Eklenen dosyalar:\n${filesText}` : `📎 Analiz edilecek dosyalar:\n${filesText}`;

        // Note: In a full implementation, you would upload files to server here
        // For now, we just include file names in the message
    }

    if (!message) return;

    // Set message and call original
    messageInput.value = message;

    // Clear attachments after sending
    attachedFiles = [];
    attachedLinks = [];
    updateFileDisplay();

    // Call original send logic
    await originalSendMessage.call(this);
};

// ==================== Keyboard Shortcuts ====================
document.addEventListener('keydown', function (event) {
    // Ctrl+Enter to force send
    if (event.ctrlKey && event.key === 'Enter') {
        event.preventDefault();
        sendMessage();
    }

    // Escape to close dialogs
    if (event.key === 'Escape') {
        closeLinkDialog();
        if (settingsPanel.classList.contains('open')) {
            toggleSettings();
        }
    }

    // Ctrl+N for new chat
    if (event.ctrlKey && event.key === 'n') {
        event.preventDefault();
        createNewChat();
    }
});
