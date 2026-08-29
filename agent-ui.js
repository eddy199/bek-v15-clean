/**
 * BEK-v15-HYBRID — Agent UI Controller (Avec Agent de Réflexion, Meta-Cortex & Curseur Gemini)
 */
(function() {
    'use strict';

    const API_BASE = window.location.origin.includes('localhost') 
        ? 'http://localhost:8765' 
        : window.location.origin;

    const DOM = {
        chatBox: document.getElementById('chat-box'),
        userInput: document.getElementById('user-input'),
        sendBtn: document.getElementById('send-btn'),
        providerSelect: document.getElementById('providerSelect'),
        modelSelect: document.getElementById('modelSelect'),
        skillsCounter: document.getElementById('navSkillsCount'),
        filesCounter: document.getElementById('navFilesCount'),
        menuOptionsBtn: document.getElementById('menuOptionsBtn'),
        dropdownMenu: document.getElementById('dropdownMenu'),
        uploadBtn: document.getElementById('uploadBtn'),
        uploadMenu: document.getElementById('uploadMenu'),
        hiddenFileInput: document.getElementById('hiddenFileInput'),
        hiddenImageInput: document.getElementById('hiddenImageInput'),
        filePreviewBar: document.getElementById('filePreviewBar'),
        convList: document.querySelector('.conv-list'),
        newChatBtn: document.querySelector('.new-chat'),
        refreshCrmBtn: document.getElementById('refreshCrmBtn')
    };

    let currentProvider = 'groq';
    let currentModel = 'openai/gpt-oss-120b';
    let availableModels = {};
    let messageHistory = [];
    let conversations = [];
    let currentConvId = null;
    let isStreaming = false;
    let attachedFiles = [];
    let activeController = null;
    let globalSkills = [];
    let crmChartInstance = null;
    let metaCortexUIInstance = null;

    // ═══════════════════════════════════════════════════════════════
    // META-CORTEX UI & REFLECTION CSS INJECTION
    // ═══════════════════════════════════════════════════════════════
    function injectReflectionCSS() {
        if (document.getElementById('metacortex-ui-css')) return;
        const style = document.createElement('style');
        style.id = 'metacortex-ui-css';
        style.innerHTML = `
            .agent-reflection {
                margin: 10px 0;
                background: var(--bg-card, #1e1e24);
                border: 1px solid var(--border-strong, #333);
                border-radius: 8px;
                overflow: hidden;
            }
            .agent-reflection summary {
                padding: 10px 14px;
                cursor: pointer;
                font-size: 13px;
                font-weight: 600;
                color: var(--text-dim, #aaa);
                display: flex;
                align-items: center;
                gap: 8px;
                list-style: none;
                user-select: none;
            }
            .agent-reflection summary::-webkit-details-marker { display: none; }
            .agent-reflection summary:hover { background: rgba(255,255,255,0.03); }
            .reflection-content {
                padding: 12px 14px;
                font-size: 12.5px;
                color: var(--text-faint, #888);
                border-top: 1px solid var(--border-strong, #333);
                background: rgba(0,0,0,0.15);
                line-height: 1.5;
            }
            .pulse-anim svg {
                animation: pulseIcon 1.5s infinite;
                color: var(--accent-soft, #4bc0c0);
            }
            @keyframes pulseIcon {
                0% { opacity: 0.4; transform: scale(0.95); }
                50% { opacity: 1; transform: scale(1.1); }
                100% { opacity: 0.4; transform: scale(0.95); }
            }
            .gemini-cursor {
                display: inline-block;
                width: 10px;
                height: 18px;
                background-color: var(--accent-soft, #4bc0c0);
                animation: gemini-blink 0.8s infinite;
                vertical-align: middle;
                margin-left: 6px;
                border-radius: 2px;
                box-shadow: 0 0 8px var(--accent-soft, #4bc0c0);
            }
            @keyframes gemini-blink {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.2; }
            }
            .meta-cortex-reflection-panel {
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                border: 1px solid #0f3460;
                border-radius: 12px;
                padding: 16px;
                margin: 12px 0;
                color: #e0e0e0;
                font-family: 'Segoe UI', system-ui, sans-serif;
                box-shadow: 0 4px 20px rgba(15, 52, 96, 0.3);
            }
            .reflection-header {
                display: flex;
                align-items: center;
                gap: 10px;
                margin-bottom: 12px;
                cursor: pointer;
            }
            .reflection-icon { font-size: 20px; }
            .reflection-title { font-weight: 600; font-size: 14px; color: #e94560; }
            .reflection-status { margin-left: auto; font-size: 12px; color: #888; }
            .reflection-progress-bar {
                height: 4px;
                background: #0f3460;
                border-radius: 2px;
                overflow: hidden;
                margin-bottom: 12px;
            }
            .reflection-progress-fill {
                height: 100%;
                background: linear-gradient(90deg, #e94560, #0f3460);
                border-radius: 2px;
                transition: width 0.5s ease;
                width: 0%;
            }
            .reflection-steps { max-height: 200px; overflow-y: auto; margin-bottom: 12px; }
            .reflection-step {
                display: flex;
                align-items: center;
                gap: 8px;
                padding: 6px 0;
                font-size: 13px;
                border-bottom: 1px solid rgba(255,255,255,0.05);
            }
            .step-icon { font-size: 14px; min-width: 20px; }
            .step-message { color: #ccc; }
            .step-detail { margin-left: auto; font-size: 11px; color: #666; }
            .reflection-verdict { margin-top: 8px; }
            .verdict-badge {
                display: inline-flex;
                align-items: center;
                gap: 8px;
                padding: 8px 16px;
                border-radius: 20px;
                font-size: 13px;
                font-weight: 500;
            }
            .verdict-confidence { margin-left: auto; font-size: 11px; opacity: 0.8; }
        `;
        document.head.appendChild(style);
    }

    class MetaCortexUI {
        constructor(chatContainer) {
            this.container = chatContainer;
            this.reflectionPanel = null;
            this.progressBar = null;
        }

        showPanel() {
            if (this.reflectionPanel) return;
            const panel = document.createElement('div');
            panel.className = 'meta-cortex-reflection-panel';
            panel.innerHTML = `
                <div class="reflection-header">
                    <span class="reflection-icon">🔍</span>
                    <span class="reflection-title">Agent de Réflexion Meta-Cortex</span>
                    <span class="reflection-status">Analyse en cours...</span>
                </div>
                <div class="reflection-progress-bar">
                    <div class="reflection-progress-fill" style="width: 10%"></div>
                </div>
                <div class="reflection-steps"></div>
                <div class="reflection-verdict"></div>
            `;
            this.container.appendChild(panel);
            this.reflectionPanel = panel;
            this.progressBar = panel.querySelector('.reflection-progress-fill');
            scrollToBottom();
        }

        addStep(message, detail = '', icon = '📋', progress = 30) {
            if (!this.reflectionPanel) this.showPanel();
            const stepsContainer = this.reflectionPanel.querySelector('.reflection-steps');
            const step = document.createElement('div');
            step.className = 'reflection-step';
            step.innerHTML = `
                <span class="step-icon">${icon}</span>
                <span class="step-message">${escapeHtml(message)}</span>
                <span class="step-detail">${escapeHtml(detail)}</span>
            `;
            stepsContainer.appendChild(step);
            stepsContainer.scrollTop = stepsContainer.scrollHeight;
            if (this.progressBar) this.progressBar.style.width = `${progress}%`;
            scrollToBottom();
        }

        setVerdict(verdict, message, confidence = 0.95) {
            if (!this.reflectionPanel) return;
            const verdictDiv = this.reflectionPanel.querySelector('.reflection-verdict');
            const statusSpan = this.reflectionPanel.querySelector('.reflection-status');

            const colors = { 'GOOD': '#22c55e', 'FIX': '#f59e0b', 'ESCALATE': '#ef4444' };
            const icons = { 'GOOD': '✅', 'FIX': '🔧', 'ESCALATE': '⚠️' };
            const color = colors[verdict] || '#22c55e';

            verdictDiv.innerHTML = `
                <div class="verdict-badge" style="background: ${color}20; color: ${color}; border: 1px solid ${color}">
                    <span>${icons[verdict] || '✅'}</span>
                    <span>${escapeHtml(message)}</span>
                    <span class="verdict-confidence">${Math.round(confidence * 100)}% confiance</span>
                </div>
            `;
            statusSpan.textContent = message;
            statusSpan.style.color = color;
            if (this.progressBar) this.progressBar.style.width = '100%';
            scrollToBottom();
        }
    }

    // Fonction de correction des chaînes Mojibake éventuelles côté client
    function fixMojibake(str) {
        if (!str || typeof str !== 'string') return str;
        try {
            return decodeURIComponent(escape(str));
        } catch (e) {
            return str;
        }
    }

    async function init() {
        injectReflectionCSS();
        metaCortexUIInstance = new MetaCortexUI(DOM.chatBox);
        await loadConfig();
        setupEventListeners();
        setupNavigationTabs();
        setupImagePasteListener();
        loadConversationsFromStorage();
        loadCRMStats();
        
        if (conversations.length > 0) {
            loadConversation(conversations[0].id);
        } else {
            createNewConversation();
        }

        appendSystemMessage('🟢 BEK-v15.2 HYBRID prêt avec Essaim Swarm, Agent de Réflexion & Grounding Neon actifs.');
    }

    async function loadConfig() {
        try {
            const res = await fetch(`${API_BASE}/api/config`);
            if (!res.ok) throw new Error('Config indisponible');
            const data = await res.json();

            availableModels = data.models || {};
            const providersList = data.providers || [];
            globalSkills = data.skills || [];

            if (DOM.providerSelect) {
                DOM.providerSelect.innerHTML = '';
                providersList.forEach(p => {
                    const opt = document.createElement('option');
                    opt.value = p.id;
                    opt.textContent = `${p.name} ${p.configured ? '✅' : '❌'}`;
                    opt.disabled = !p.configured;
                    DOM.providerSelect.appendChild(opt);
                });
            }

            if (DOM.skillsCounter && data.skills_count) {
                DOM.skillsCounter.textContent = data.skills_count;
                populateSkillsView(globalSkills);
            }

            updateModelSelect();
            loadFilesList();
        } catch (e) {
            console.error('Erreur config :', e);
        }
    }

    async function loadFilesList() {
        try {
            const res = await fetch(`${API_BASE}/api/files`);
            const data = await res.json();
            if (DOM.filesCounter) DOM.filesCounter.textContent = data.files.length;
            populateFilesView(data.files || []);
        } catch (e) {}
    }

    async function loadCRMStats() {
        try {
            const res = await fetch(`${API_BASE}/api/crm/stats`);
            const data = await res.json();

            const cElem = document.getElementById('kpi-contacts');
            const coElem = document.getElementById('kpi-companies');
            const oElem = document.getElementById('kpi-opportunities');
            const aElem = document.getElementById('kpi-amount');

            if (cElem) cElem.innerText = data.num_contacts;
            if (coElem) coElem.innerText = data.num_companies;
            if (oElem) oElem.innerText = data.num_opportunities;
            if (aElem) aElem.innerText = Number(data.total_amount || 0).toLocaleString('fr-FR');
        } catch (e) {
            console.error('Erreur chargement CRM stats :', e);
        }
    }

    function populateSkillsView(skills) {
        const viewSkills = document.getElementById('viewSkills');
        if (!viewSkills) return;
        viewSkills.innerHTML = `<h2>Compétences chargées (${skills.length})</h2><div style="margin-top:16px; display:flex; flex-direction:column; gap:12px;">` +
            skills.map(s => `
                <div style="background:var(--bg-card); border:1px solid var(--border); padding:14px; border-radius:8px;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <strong style="color:var(--accent-blue); font-size:14px;">${s.name}</strong>
                        <span style="font-size:11px; background:rgba(255,255,255,0.1); padding:2px 6px; border-radius:4px; font-family:monospace;">${s.command}</span>
                    </div>
                    <p style="color:var(--text-dim); font-size:12.5px; margin-top:6px;">${s.description}</p>
                </div>
            `).join('') + `</div>`;
    }

    function populateFilesView(files) {
        const viewFiles = document.getElementById('viewFiles');
        if (!viewFiles) return;
        viewFiles.innerHTML = `<h2>Fichiers du projet & de la session (${files.length})</h2><div style="margin-top:16px; display:flex; flex-direction:column; gap:8px;">` +
            (files.length === 0 ? '<p style="color:var(--text-dim);">Aucun fichier disponible.</p>' : 
            files.map(f => `
                <div style="background:var(--bg-card); border:1px solid var(--border-color); padding:12px 16px; border-radius:8px; display:flex; justify-content:space-between; align-items:center;">
                    <span>📄 <strong>${f.name}</strong> <span style="color:var(--text-dim); font-size:11px; margin-left:8px;">${(f.size/1024).toFixed(1)} Ko</span></span>
                    <a href="${API_BASE}/api/download/${f.name}" target="_blank" style="background:var(--accent-blue); color:#fff; padding:6px 12px; border-radius:6px; font-size:12px; text-decoration:none;">Télécharger</a>
                </div>
            `).join('')) + `</div>`;
    }

    function updateModelSelect() {
        if (!DOM.providerSelect || !DOM.modelSelect) return;
        currentProvider = DOM.providerSelect.value;
        const models = availableModels[currentProvider] || [];
        
        DOM.modelSelect.innerHTML = '';
        models.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m;
            opt.textContent = m.split('/').pop();
            DOM.modelSelect.appendChild(opt);
        });

        if (models.length > 0) {
            currentModel = models[0];
            DOM.modelSelect.value = currentModel;
        }
    }

    function setupNavigationTabs() {
        const navButtons = document.querySelectorAll('.nav-item');
        navButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                const tabName = btn.getAttribute('data-tab');
                navButtons.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');

                document.querySelectorAll('.main .view').forEach(v => v.classList.remove('active'));
                if (tabName === 'chat') {
                    document.getElementById('viewChat').classList.add('active');
                } else {
                    const viewEl = document.getElementById(`view${tabName.charAt(0).toUpperCase() + tabName.slice(1)}`);
                    if (viewEl) viewEl.classList.add('active');
                }
            });
        });
    }

    function setupEventListeners() {
        if (DOM.providerSelect) DOM.providerSelect.addEventListener('change', updateModelSelect);
        if (DOM.modelSelect) DOM.modelSelect.addEventListener('change', (e) => { currentModel = e.target.value; });

        if (DOM.sendBtn && DOM.userInput) {
            DOM.sendBtn.addEventListener('click', handleSendOrStop);
            DOM.userInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSendOrStop();
                }
            });
        }

        if (DOM.newChatBtn) {
            DOM.newChatBtn.addEventListener('click', () => {
                createNewConversation();
            });
        }

        if (DOM.menuOptionsBtn && DOM.dropdownMenu) {
            DOM.menuOptionsBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                const isVisible = DOM.dropdownMenu.style.display === 'block';
                DOM.dropdownMenu.style.display = isVisible ? 'none' : 'block';
                if (DOM.uploadMenu) DOM.uploadMenu.style.display = 'none';
            });
        }

        document.getElementById('menuClear')?.addEventListener('click', () => {
            if (DOM.chatBox) DOM.chatBox.innerHTML = '';
            messageHistory = [];
            saveCurrentConversation();
            DOM.dropdownMenu.style.display = 'none';
        });

        if (DOM.uploadBtn && DOM.uploadMenu) {
            DOM.uploadBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                const isVisible = DOM.uploadMenu.style.display === 'block';
                DOM.uploadMenu.style.display = isVisible ? 'none' : 'block';
                if (DOM.dropdownMenu) DOM.dropdownMenu.style.display = 'none';
            });
        }

        document.getElementById('btnImportFile')?.addEventListener('click', () => {
            if (DOM.hiddenFileInput) DOM.hiddenFileInput.click();
            if (DOM.uploadMenu) DOM.uploadMenu.style.display = 'none';
        });

        document.getElementById('btnImportImage')?.addEventListener('click', () => {
            if (DOM.hiddenImageInput) DOM.hiddenImageInput.click();
            if (DOM.uploadMenu) DOM.uploadMenu.style.display = 'none';
        });

        DOM.hiddenFileInput?.addEventListener('change', async (e) => {
            for (const file of Array.from(e.target.files)) {
                await uploadFileToServer(file);
            }
        });

        DOM.hiddenImageInput?.addEventListener('change', async (e) => {
            for (const file of Array.from(e.target.files)) {
                await uploadFileToServer(file);
            }
        });

        document.addEventListener('click', () => {
            if (DOM.dropdownMenu) DOM.dropdownMenu.style.display = 'none';
            if (DOM.uploadMenu) DOM.uploadMenu.style.display = 'none';
        });
    }

    function loadConversationsFromStorage() {
        try {
            const saved = localStorage.getItem('bek_conversations');
            if (saved) conversations = JSON.parse(saved);
        } catch (e) {
            conversations = [];
        }
        renderConversationsList();
    }

    function saveConversationsToStorage() {
        try {
            localStorage.setItem('bek_conversations', JSON.stringify(conversations));
        } catch (e) {}
        renderConversationsList();
    }

    function renderConversationsList() {
        if (!DOM.convList) return;
        DOM.convList.innerHTML = '';
        if (conversations.length === 0) {
            DOM.convList.innerHTML = '<div class="conv-empty" style="color:var(--text-dim); padding:10px;">Aucune conversation</div>';
            return;
        }

        conversations.forEach(conv => {
            const item = document.createElement('div');
            item.className = `conv-item ${conv.id === currentConvId ? 'active' : ''}`;
            item.innerHTML = `
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                <span class="conv-title">${escapeHtml(conv.title || 'Nouvelle conversation')}</span>
                <button class="conv-del" title="Supprimer" onclick="event.stopPropagation(); deleteConversation('${conv.id}')">×</button>
            `;
            item.addEventListener('click', () => loadConversation(conv.id));
            DOM.convList.appendChild(item);
        });
    }

    function createNewConversation() {
        const newId = 'conv_' + Date.now();
        const newConv = {
            id: newId,
            title: 'Nouvelle conversation',
            messages: []
        };
        conversations.unshift(newConv);
        saveConversationsToStorage();
        loadConversation(newId);
    }

    function loadConversation(id) {
        currentConvId = id;
        const conv = conversations.find(c => c.id === id);
        if (!conv) return;

        messageHistory = conv.messages || [];
        if (DOM.chatBox) DOM.chatBox.innerHTML = '';

        messageHistory.forEach(m => {
            if (m.role === 'user') {
                appendUserMessage(m.content, false);
            } else if (m.role === 'assistant') {
                const contentDiv = appendAssistantMessage('', false);
                contentDiv.innerHTML = formatMarkdown(m.content);
            }
        });
        renderConversationsList();
    }

    function saveCurrentConversation() {
        const conv = conversations.find(c => c.id === currentConvId);
        if (!conv) return;

        conv.messages = messageHistory;
        if (messageHistory.length > 0) {
            const firstUserMsg = messageHistory.find(m => m.role === 'user');
            if (firstUserMsg) {
                let text = firstUserMsg.content;
                conv.title = text.length > 25 ? text.substring(0, 25) + '...' : text;
            }
        }
        saveConversationsToStorage();
    }

    window.deleteConversation = function(id) {
        conversations = conversations.filter(c => c.id !== id);
        saveConversationsToStorage();
        if (currentConvId === id) {
            if (conversations.length > 0) {
                loadConversation(conversations[0].id);
            } else {
                createNewConversation();
            }
        }
    };

    function setupImagePasteListener() {
        if (!DOM.userInput) return;
        DOM.userInput.addEventListener('paste', async (e) => {
            const items = (e.clipboardData || e.originalEvent.clipboardData).items;
            for (const item of items) {
                if (item.type.indexOf('image') === 0) {
                    e.preventDefault();
                    const blob = item.getAsFile();
                    const file = new File([blob], `capture_${Date.now()}.png`, { type: blob.type });
                    await uploadFileToServer(file);
                }
            }
        });
    }

    async function uploadFileToServer(file) {
        const formData = new FormData();
        formData.append('file', file);

        try {
            const resp = await fetch(`${API_BASE}/api/upload`, {
                method: 'POST',
                body: formData
            });
            const data = await resp.json();
            if (resp.ok) {
                attachedFiles.push(data.filename);
                loadFilesList();
            } else {
                alert(`Erreur upload : ${data.error}`);
            }
        } catch (err) {
            alert(`Erreur réseau`);
        }
    }

    function handleSendOrStop() {
        if (isStreaming) {
            stopGeneration();
        } else {
            sendMessage();
        }
    }

    function stopGeneration() {
        if (activeController) {
            activeController.abort();
            activeController = null;
        }
        isStreaming = false;
        if (DOM.sendBtn) DOM.sendBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>`;
        if (DOM.userInput) {
            DOM.userInput.disabled = false;
            DOM.userInput.focus();
        }
        appendSystemMessage('⏹️ Génération interrompue.');
    }

    async function sendMessage() {
        if (!DOM.userInput || !DOM.sendBtn || !DOM.chatBox) return;
        const text = DOM.userInput.value.trim();
        if (!text && attachedFiles.length === 0) return;

        let fullTextContent = text;
        if (attachedFiles.length > 0) {
            fullTextContent += `\n[Fichiers joints : ${attachedFiles.join(', ')}]`;
        }

        appendUserMessage(fullTextContent, true);
        DOM.userInput.value = '';
        attachedFiles = [];

        isStreaming = true;
        activeController = new AbortController();

        DOM.sendBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16" rx="2"/></svg>`;

        messageHistory.push({ role: 'user', content: fullTextContent });
        saveCurrentConversation();
        if (messageHistory.length > 20) messageHistory = messageHistory.slice(-20);

        const payload = {
            messages: messageHistory,
            provider: currentProvider,
            model: currentModel,
            use_memory: true,
            use_reflection: true
        };

        const assistantDiv = appendAssistantMessage('', true);
        let fullResponse = '';
        
        assistantDiv.innerHTML = '<span class="gemini-cursor"></span>';

        try {
            const resp = await fetch(`${API_BASE}/api/chat`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json; charset=utf-8',
                    'Accept': 'text/event-stream; charset=utf-8'
                },
                body: JSON.stringify(payload),
                signal: activeController.signal
            });

            if (!resp.ok) throw new Error(`Erreur HTTP ${resp.status}`);

            const reader = resp.body.getReader();
            const decoder = new TextDecoder('utf-8', { fatal: false });
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop();

                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;
                    const dataStr = line.slice(6).trim();
                    if (!dataStr || dataStr === '[DONE]') continue;

                    try {
                        const data = JSON.parse(dataStr);
                        if (data.chunk) {
                            fullResponse += fixMojibake(data.chunk);
                            assistantDiv.innerHTML = formatMarkdown(fullResponse) + '<span class="gemini-cursor"></span>';
                            scrollToBottom();
                        }
                    } catch (err) {}
                }
            }

            if (fullResponse) {
                messageHistory.push({ role: 'assistant', content: fullResponse });
                saveCurrentConversation();
            }

        } catch (err) {
            if (err.name !== 'AbortError') {
                assistantDiv.innerHTML = `<div style="color:#ff4a4a; padding:10px;">🔴 Erreur : ${err.message}</div>`;
            }
        } finally {
            isStreaming = false;
            activeController = null;
            assistantDiv.innerHTML = formatMarkdown(fullResponse);
            
            if (DOM.sendBtn) DOM.sendBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>`;
            if (DOM.userInput) {
                DOM.userInput.disabled = false;
                DOM.userInput.focus();
            }
        }
    }

    function escapeHtml(text) {
        return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    function appendUserMessage(text) {
        if (!DOM.chatBox) return;
        const div = document.createElement('div');
        div.className = 'message user-message';
        const bubble = document.createElement('div');
        bubble.className = 'msg-bubble';
        bubble.textContent = text;
        div.appendChild(bubble);
        DOM.chatBox.appendChild(div);
        scrollToBottom();
    }

    function appendAssistantMessage(html) {
        if (!DOM.chatBox) return document.createElement('div');
        const div = document.createElement('div');
        div.className = 'message assistant-message';
        div.innerHTML = `<div class="msg-meta"><span class="model-tag">${currentProvider} • ${currentModel.split('/').pop()}</span></div><div class="msg-bubble content">${html}</div>`;
        DOM.chatBox.appendChild(div);
        scrollToBottom();
        return div.querySelector('.content');
    }

    function appendSystemMessage(text) {
        if (!DOM.chatBox) return;
        const div = document.createElement('div');
        div.className = 'message system-message';
        div.style.cssText = "text-align: center; color: var(--text-dim); font-size: 12px; margin: 10px 0;";
        div.textContent = text;
        DOM.chatBox.appendChild(div);
        scrollToBottom();
    }

    function scrollToBottom() {
        if (DOM.chatBox) DOM.chatBox.scrollTop = DOM.chatBox.scrollHeight;
    }

    function formatMarkdown(text) {
        let safeText = text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');

        safeText = safeText.replace(/```(\w*)?\n([\s\S]*?)```/g, (match, lang, codeContent) => {
            const language = lang || 'code';
            const cleanCode = codeContent
                .replace(/&amp;/g, '&')
                .replace(/&lt;/g, '<')
                .replace(/&gt;/g, '>');

            return `
                <div class="code-container" style="background:#0a0a0c; border:1px solid var(--border-color); border-radius:8px; margin:10px 0; overflow:hidden;">
                    <div style="padding:6px 12px; background:rgba(255,255,255,0.05); color:var(--text-dim); font-size:11px; font-weight:bold;">${language.toUpperCase()}</div>
                    <pre style="padding:12px; margin:0; overflow-x:auto; font-family:'Ubuntu Mono', monospace; font-size:13px; color:#e0e0e0;"><code>${escapeHtml(cleanCode)}</code></pre>
                </div>
            `;
        });

        return safeText
            .replace(/\*\*(.*?)\*\*/g, '<b>$1</b>')
            .replace(/\*(.*?)\*/g, '<i>$1</i>')
            .replace(/`([^`]+)`/g, '<code style="background:rgba(255,255,255,0.1); padding:2px 5px; border-radius:4px; font-family:\'Ubuntu Mono\', monospace;">$1</code>')
            .replace(/\n/g, '<br>');
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
