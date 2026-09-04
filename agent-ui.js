/**
 * BEK-v15-HYBRID — Agent UI Controller (Gestion Fichiers Dynamique, Anti-Cache & Auto-Expand Gemini)
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
        convList: document.getElementById('convList'),
        newChatBtn: document.getElementById('newChatBtn'),
        modelBadge: document.getElementById('modelBadge')
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
    let loadedSubCRMData = null;

    window.__codeSnippetsRegistry = window.__codeSnippetsRegistry || {};

    // --- CHARGEMENT DU MOTEUR DE COLORATION SYNTAXIQUE (HIGHLIGHT.JS) ---
    function loadSyntaxHighlighter() {
        if (!document.getElementById('hljs-style')) {
            const link = document.createElement('link');
            link.id = 'hljs-style';
            link.rel = 'stylesheet';
            link.href = 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-dark.min.css';
            document.head.appendChild(link);
        }
        if (!window.hljs && !document.getElementById('hljs-script')) {
            const script = document.createElement('script');
            script.id = 'hljs-script';
            script.src = 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js';
            script.onload = () => {
                if (window.marked) {
                    const messages = document.querySelectorAll('.msg-bubble');
                    messages.forEach(m => {
                        m.querySelectorAll('pre code').forEach(el => hljs.highlightElement(el));
                    });
                }
            };
            document.head.appendChild(script);
        }
    }

    // --- FONCTIONS CLOUD / CLIPBOARD COPIE STYLE GEMINI ---
    window.copyWholeMessage = async function(btn) {
        if (!btn) return;
        const msgEl = btn.closest('.message');
        if (!msgEl) return;
        const bubble = msgEl.querySelector('.msg-bubble');
        if (!bubble) return;

        const textToCopy = bubble.innerText.trim();
        try {
            await navigator.clipboard.writeText(textToCopy);
            const originalHTML = btn.innerHTML;
            btn.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#4ade80" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg> <span style="color:#4ade80; font-weight:600;">Copié !</span>`;
            btn.style.borderColor = 'rgba(74, 222, 128, 0.6)';
            setTimeout(() => {
                btn.innerHTML = originalHTML;
                btn.style.borderColor = '';
            }, 2000);
        } catch (err) {
            console.error('Erreur lors de la copie du message :', err);
        }
    };

    window.copyCodeSnippet = async function(snippetId, btn) {
        const item = window.__codeSnippetsRegistry[snippetId];
        if (!item || !item.code) return;
        try {
            await navigator.clipboard.writeText(item.code);
            const originalText = btn.innerHTML;
            btn.innerHTML = `<span style="color:#4ade80; font-weight:600;">✓ Copié !</span>`;
            btn.style.borderColor = '#4ade80';
            setTimeout(() => {
                btn.innerHTML = originalText;
                btn.style.borderColor = '';
            }, 2000);
        } catch (err) {
            console.error('Erreur copie code :', err);
        }
    };

    window.downloadCodeSnippet = function(snippetId) {
        const item = window.__codeSnippetsRegistry[snippetId];
        if (!item || !item.code) return;
        const extMap = {
            python: 'py', py: 'py', javascript: 'js', js: 'js',
            typescript: 'ts', ts: 'ts', html: 'html', css: 'css',
            json: 'json', markdown: 'md', md: 'md', sh: 'sh',
            bash: 'sh', sql: 'sql', text: 'txt'
        };
        const ext = extMap[item.lang] || 'txt';
        const blob = new Blob([item.code], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `code_${snippetId}.${ext}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };

    function injectEnhancedCSS() {
        if (document.getElementById('metacortex-ui-css')) return;
        const style = document.createElement('style');
        style.id = 'metacortex-ui-css';
        style.innerHTML = `
            #chat-box, .message, .msg-bubble, pre, code {
                user-select: text !important;
                -webkit-user-select: text !important;
            }
            .gemini-cursor {
                display: inline-block;
                width: 8px;
                height: 16px;
                background-color: var(--accent, #4f8ef7);
                animation: gemini-blink 0.8s infinite;
                vertical-align: middle;
                margin-left: 6px;
                border-radius: 2px;
                box-shadow: 0 0 8px var(--accent-glow);
            }
            @keyframes gemini-blink {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.2; }
            }
        `;
        document.head.appendChild(style);
    }

    async function init() {
        loadSyntaxHighlighter();
        injectEnhancedCSS();
        await loadConfig();
        setupEventListeners();
        setupNavigationTabs();
        setupImagePasteListener();
        loadConversationsFromStorage();
        
        if (conversations.length > 0) {
            loadConversation(conversations[0].id);
        } else {
            createNewConversation();
        }
        appendSystemMessage('🟢 BEK-v15.2 HYBRID opérationnel avec toutes les briques actives (Uploads 300Mo, Pinecone, Neon & Actions).');
    }

    async function loadConfig() {
        try {
            const res = await fetch(`${API_BASE}/api/config?t=${Date.now()}`);
            if (!res.ok) throw new Error("API Config non disponible");
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
                    DOM.providerSelect.appendChild(opt);
                });
            }

            if (DOM.skillsCounter) DOM.skillsCounter.textContent = data.skills_count || globalSkills.length;
            populateSkillsView(globalSkills);
            updateModelSelect();
            await loadFilesList();
        } catch (e) {
            console.warn('Erreur config :', e);
        }
    }

    // --- RECHARGEMENT DYNAMIQUE DES FICHIERS ---
    window.loadFilesList = async function() {
        try {
            const res = await fetch(`${API_BASE}/api/files?t=${Date.now()}`);
            if (!res.ok) return;
            const data = await res.json();
            const files = data.files || [];
            if (DOM.filesCounter) DOM.filesCounter.textContent = files.length;
            populateFilesView(files);
        } catch (e) {
            console.error("Erreur chargement fichiers :", e);
        }
    };

    function populateFilesView(files) {
        const view = document.getElementById('viewFiles');
        if (!view) return;
        view.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
                <h2 style="margin:0;">Fichiers de session (${files.length})</h2>
                <div style="display:flex; gap:8px;">
                    <button id="btnRefreshFiles" onclick="loadFilesList()" style="background:rgba(255,255,255,0.08); border:1px solid var(--border-color); color:var(--text-main); padding:6px 14px; border-radius:6px; font-size:12px; cursor:pointer; font-weight:600;">🔄 Actualiser</button>
                    ${files.length > 0 ? `<button onclick="deleteAllProjectFiles()" style="background:rgba(239,68,68,0.15); border:1px solid rgba(239,68,68,0.4); color:#ef4444; padding:6px 14px; border-radius:6px; font-size:12px; cursor:pointer; font-weight:bold;">🗑️ Tout supprimer</button>` : ''}
                </div>
            </div>
            <div style="display:flex; flex-direction:column; gap:8px;">` +
            (files.length === 0 ? '<p style="color:var(--text-dim); text-align:center; padding:30px;">Aucun fichier déposé ou généré.</p>' : 
            files.map(f => `
                <div style="background:var(--bg-card); border:1px solid var(--border-color); padding:12px 16px; border-radius:8px; display:flex; justify-content:space-between; align-items:center;">
                    <span>📄 <strong>${escapeHtml(f.name)}</strong> <span style="color:var(--text-dim); font-size:11px; margin-left:8px;">(${(f.size/1024).toFixed(1)} Ko - ${escapeHtml(f.folder)})</span></span>
                    <div style="display:flex; gap:8px;">
                        <a href="${API_BASE}/api/download/${encodeURIComponent(f.name)}" target="_blank" style="background:var(--accent-blue); color:#fff; padding:6px 12px; border-radius:6px; font-size:12px; text-decoration:none;">Télécharger</a>
                        <button onclick="deleteProjectFile('${escapeHtml(f.name)}')" style="background:rgba(239,68,68,0.2); color:#ef4444; border:1px solid rgba(239,68,68,0.4); padding:6px 12px; border-radius:6px; font-size:12px; cursor:pointer;">Supprimer</button>
                    </div>
                </div>
            `).join('')) + `</div>`;
    }

    window.deleteProjectFile = async function(filename) {
        if (!confirm(`Confirmer la suppression définitive de : ${filename} ?`)) return;
        try {
            const res = await fetch(`${API_BASE}/api/files/${encodeURIComponent(filename)}`, { method: 'DELETE' });
            const json = await res.json();
            if (res.ok) {
                await loadFilesList();
            } else {
                alert(json.error || "Erreur lors de la suppression");
            }
        } catch (e) {
            alert("Erreur réseau lors de la suppression");
        }
    };

    window.deleteAllProjectFiles = async function() {
        if (!confirm("Voulez-vous vraiment TOUT supprimer dans uploads et generated ?")) return;
        try {
            const res = await fetch(`${API_BASE}/api/files/delete-all`, { method: 'POST' });
            const json = await res.json();
            if (res.ok) {
                await loadFilesList();
            } else {
                alert(json.error || "Erreur de purge");
            }
        } catch (e) {
            alert("Erreur réseau");
        }
    };

    function populateSkillsView(skills) {
        const view = document.getElementById('viewSkills');
        if (!view) return;
        view.innerHTML = `<h2>Compétences Actives (${skills.length})</h2><div style="margin-top:16px; display:grid; grid-template-columns:repeat(auto-fill, minmax(280px, 1fr)); gap:12px;">` +
            skills.map(s => `
                <div style="background:var(--bg-card); border:1px solid var(--border-color); padding:14px; border-radius:8px; display:flex; flex-direction:column; justify-content:space-between;">
                    <div>
                        <strong style="color:var(--text-main); font-size:14px;">${escapeHtml(s.name)}</strong>
                        <p style="color:var(--text-dim); font-size:12px; margin: 6px 0 10px;">${escapeHtml(s.description || 'Skill autonome')}</p>
                    </div>
                    <div style="margin-top: 6px;">
                        <button onclick="insertPromptToChat('${s.command.startsWith('/') ? s.command : '/' + s.command}')" style="cursor:pointer; background:rgba(92,156,230,0.15); border:1px solid rgba(92,156,230,0.4); color:var(--accent-blue); padding:4px 10px; border-radius:6px; font-family:'Ubuntu Mono', monospace; font-size:12px; font-weight:bold; width:100%; text-align:left;">
                            ${s.command.startsWith('/') ? s.command : '/' + s.command} ➜
                        </button>
                    </div>
                </div>
            `).join('') + `</div>`;
    }

    window.insertPromptToChat = function(cmd) {
        if (DOM.userInput) {
            DOM.userInput.value = cmd + ' ';
            DOM.userInput.focus();
            const chatNav = document.querySelector('[data-tab="chat"]');
            if (chatNav) chatNav.click();
        }
    };

    async function loadMemoryView() {
        const view = document.getElementById('viewMemory');
        if (!view) return;
        try {
            const res = await fetch(`${API_BASE}/api/memory?t=${Date.now()}`);
            if (!res.ok) throw new Error("API manquante");
            const data = await res.json();
            let pineconeColor = data.pinecone_status.includes('Connecté') ? '#4ade80' : '#f5a623';
            
            view.innerHTML = `
                <h2>Mémoire Long Terme & Index Vectoriel</h2>
                <div style="margin-top:16px; display:flex; flex-direction:column; gap:12px;">
                    <div class="matrix-widget">
                        <h3>Pinecone Vector Database : <span style="color:${pineconeColor};">${data.pinecone_status}</span></h3>
                        <p style="color:var(--text-dim); font-size:13px; margin-top:8px;">Indexation vectorielle des conversations et règles d'or synchronisée en temps réel.</p>
                        <div style="margin-top:12px; font-family:monospace; font-size:12px; color:var(--accent-blue);">
                            - Entités Neon DB totales : ${data.neon_state_entries}<br>
                            &nbsp;&nbsp;↳ <em>${data.details_crm}</em><br>
                            &nbsp;&nbsp;↳ <em>${data.details_opps}</em><br>
                            - Règles BEK synchronisées : ${data.system_rules_synced ? 'OUI' : 'NON'}
                        </div>
                    </div>
                </div>
            `;
        } catch (e) {
            view.innerHTML = `<p style="color:#ff4a4a">Erreur de chargement mémoire.</p>`;
        }
    }

    async function loadConnectorsView() {
        const view = document.getElementById('viewConnectors');
        if (!view) return;
        try {
            const res = await fetch(`${API_BASE}/api/connectors?t=${Date.now()}`);
            if (!res.ok) throw new Error("API manquante");
            const data = await res.json();
            view.innerHTML = `<h2>Connecteurs Système & Serveurs</h2><div style="margin-top:16px; display:flex; flex-direction:column; gap:10px;">` +
                data.connectors.map(c => {
                    let statusColor = c.status.includes('Actif') || c.status.includes('Prêt') ? '#4ade80' : '#f5a623';
                    if (c.status.includes('Erreur')) statusColor = '#ff4a4a';
                    return `
                    <div style="background:var(--bg-card); border:1px solid var(--border-color); padding:14px; border-radius:8px; display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <strong>${escapeHtml(c.name)}</strong>
                            <div style="font-size:11px; color:var(--text-dim); margin-top:2px;">Type : ${escapeHtml(c.type)}</div>
                        </div>
                        <div style="display:flex; align-items:center; gap:10px;">
                            <span style="font-size:11px; font-family:monospace; color:var(--text-dim);">${c.latency_ms} ms</span>
                            <span style="background:rgba(255,255,255,0.05); color:${statusColor}; padding:3px 8px; border-radius:4px; font-size:11px; font-weight:bold;">${escapeHtml(c.status)}</span>
                        </div>
                    </div>
                `}).join('') + `</div>`;
        } catch (e) {
            view.innerHTML = `<p style="color:#ff4a4a">Erreur connecteurs.</p>`;
        }
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
        if (DOM.modelBadge) {
            DOM.modelBadge.innerText = `● ${currentProvider.toUpperCase()} / ${currentModel.split('/').pop()}`;
        }
    }

    function setupNavigationTabs() {
        const navButtons = document.querySelectorAll('.nav-item');
        navButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                const tabName = btn.getAttribute('data-tab');
                navButtons.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');

                document.querySelectorAll('.main .view').forEach(v => {
                    v.classList.remove('active');
                    v.style.display = 'none';
                });

                if (tabName === 'chat') {
                    const view = document.getElementById('viewChat');
                    view.classList.add('active');
                    view.style.display = 'flex';
                } else if (tabName === 'matrix-bek') {
                    const view = document.getElementById('viewMatrixBek');
                    view.classList.add('active');
                    view.style.display = 'block';
                    loadSubCRMsUI();
                    loadOpportunitiesUI();
                } else {
                    const viewEl = document.getElementById(`view${tabName.charAt(0).toUpperCase() + tabName.slice(1)}`);
                    if (viewEl) {
                        viewEl.classList.add('active');
                        viewEl.style.display = 'block';
                        if (tabName === 'memory') loadMemoryView();
                        if (tabName === 'connectors') loadConnectorsView();
                        if (tabName === 'files') loadFilesList();
                    }
                }
            });
        });
    }

    function setupEventListeners() {
        if (DOM.providerSelect) DOM.providerSelect.addEventListener('change', updateModelSelect);
        if (DOM.modelSelect) DOM.modelSelect.addEventListener('change', (e) => { 
            currentModel = e.target.value; 
            if (DOM.modelBadge) DOM.modelBadge.innerText = `● ${currentProvider.toUpperCase()} / ${currentModel.split('/').pop()}`;
        });

        // --- GESTION DU REDIMENSIONNEMENT DYNAMIQUE DU TEXTAREA (AUTO-EXPAND STYLE GEMINI) ---
        if (DOM.userInput) {
            DOM.userInput.addEventListener('input', function() {
                this.style.height = '24px';
                const newHeight = Math.min(this.scrollHeight, 180);
                this.style.height = newHeight + 'px';
                this.style.overflowY = this.scrollHeight > 180 ? 'auto' : 'hidden';
            });
        }

        if (DOM.sendBtn && DOM.userInput) {
            DOM.sendBtn.addEventListener('click', handleSendOrStop);
            DOM.userInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSendOrStop();
                }
            });
        }

        if (DOM.newChatBtn) DOM.newChatBtn.addEventListener('click', createNewConversation);

        if (DOM.menuOptionsBtn && DOM.dropdownMenu) {
            DOM.menuOptionsBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                DOM.dropdownMenu.style.display = DOM.dropdownMenu.style.display === 'block' ? 'none' : 'block';
            });
        }

        document.getElementById('menuClear')?.addEventListener('click', () => {
            if (DOM.chatBox) DOM.chatBox.innerHTML = '';
            messageHistory = [];
            saveCurrentConversation();
            DOM.dropdownMenu.style.display = 'none';
        });

        document.getElementById('menuExportPdf')?.addEventListener('click', () => {
            DOM.dropdownMenu.style.display = 'none';
            window.print();
        });

        document.getElementById('menuShare')?.addEventListener('click', () => {
            DOM.dropdownMenu.style.display = 'none';
            navigator.clipboard.writeText(JSON.stringify(messageHistory, null, 2));
            alert("Historique copié !");
        });

        if (DOM.uploadBtn && DOM.uploadMenu) {
            DOM.uploadBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                DOM.uploadMenu.style.display = DOM.uploadMenu.style.display === 'block' ? 'none' : 'block';
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
            const resp = await fetch(`${API_BASE}/api/upload?t=${Date.now()}`, { method: 'POST', body: formData });
            const data = await resp.json();
            if (resp.ok) {
                attachedFiles.push(data.filename);
                renderAttachedFilesPreview();
                await loadFilesList();
            } else {
                alert(`Erreur upload : ${data.error}`);
            }
        } catch (err) {
            alert("Erreur réseau lors de l'upload.");
        }
    }

    function renderAttachedFilesPreview() {
        if (!DOM.filePreviewBar) return;
        if (attachedFiles.length === 0) {
            DOM.filePreviewBar.style.display = 'none';
            DOM.filePreviewBar.innerHTML = '';
            return;
        }
        DOM.filePreviewBar.style.display = 'flex';
        DOM.filePreviewBar.innerHTML = attachedFiles.map((f, i) => `
            <span style="background:rgba(92,156,230,0.2); color:var(--accent-blue); padding:4px 8px; border-radius:6px; font-size:11px; display:flex; align-items:center; gap:6px;">
                📎 ${escapeHtml(f)} <button onclick="removeAttachedFile(${i})" style="color:#ff4a4a; font-weight:bold;">&times;</button>
            </span>
        `).join('');
    }

    window.removeAttachedFile = function(index) {
        attachedFiles.splice(index, 1);
        renderAttachedFilesPreview();
    };

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
    }

    async function sendMessage() {
        if (!DOM.userInput || !DOM.sendBtn || !DOM.chatBox) return;
        const text = DOM.userInput.value.trim();
        if (!text && attachedFiles.length === 0) return;

        let fullTextContent = text;
        if (attachedFiles.length > 0) {
            fullTextContent += `\n[Fichiers joints : ${attachedFiles.join(', ')}]`;
        }

        appendUserMessage(fullTextContent);
        
        // Réinitialisation de la hauteur de la boîte de saisie à sa taille compacte initiale
        DOM.userInput.value = '';
        DOM.userInput.style.height = '24px';
        DOM.userInput.style.overflowY = 'hidden';
        
        attachedFiles = [];
        renderAttachedFilesPreview();

        isStreaming = true;
        activeController = new AbortController();
        DOM.sendBtn.innerHTML = `<span style="font-weight:bold;">■</span>`;

        messageHistory.push({ role: 'user', content: fullTextContent });
        saveCurrentConversation();

        const assistantDiv = appendAssistantMessage('');
        assistantDiv.innerHTML = '<span class="gemini-cursor"></span>';
        let fullResponse = '';

        try {
            const resp = await fetch(`${API_BASE}/api/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json; charset=utf-8' },
                body: JSON.stringify({
                    messages: messageHistory,
                    provider: currentProvider,
                    model: currentModel,
                    use_memory: true,
                    use_reflection: true
                }),
                signal: activeController.signal
            });

            const reader = resp.body.getReader();
            const decoder = new TextDecoder('utf-8');
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
                            fullResponse += data.chunk;
                            assistantDiv.innerHTML = formatMarkdown(fullResponse) + '<span class="gemini-cursor"></span>';
                            DOM.chatBox.scrollTop = DOM.chatBox.scrollHeight;
                        }
                    } catch (err) {}
                }
            }

            if (fullResponse) {
                messageHistory.push({ role: 'assistant', content: fullResponse });
                saveCurrentConversation();
                if (fullResponse.includes('[Action Exécutée')) {
                    await loadFilesList();
                    loadSubCRMsUI();
                    loadOpportunitiesUI();
                }
            }
        } catch (err) {
            if (err.name !== 'AbortError') {
                assistantDiv.innerHTML = `<span style="color:#ff4a4a;">Erreur : ${err.message}</span>`;
            }
        } finally {
            isStreaming = false;
            activeController = null;
            assistantDiv.innerHTML = formatMarkdown(fullResponse);
            DOM.sendBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>`;
        }
    }

    function appendUserMessage(text) {
        if (!DOM.chatBox) return;
        const div = document.createElement('div');
        div.className = 'message user'; 
        div.innerHTML = `
            <div class="msg-meta"><span class="name">Vous</span></div>
            <div class="msg-bubble">${escapeHtml(text).replace(/\n/g, '<br>')}</div>
            <div class="msg-actions">
                <button onclick="copyWholeMessage(this)" title="Copier ce message">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg> Copier
                </button>
            </div>
        `;
        DOM.chatBox.appendChild(div);
        DOM.chatBox.scrollTop = DOM.chatBox.scrollHeight;
    }

    function appendAssistantMessage(html) {
        if (!DOM.chatBox) return document.createElement('div');
        const div = document.createElement('div');
        div.className = 'message assistant';
        div.innerHTML = `
            <div class="msg-meta">
                <span class="name">BEK-v15 Hybrid</span>
                <span class="model-tag">${currentProvider} • ${currentModel.split('/').pop()}</span>
            </div>
            <div class="msg-bubble content">${html}</div>
            <div class="msg-actions">
                <button onclick="copyWholeMessage(this)" title="Copier la réponse complète">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg> Copier
                </button>
            </div>
        `;
        DOM.chatBox.appendChild(div);
        DOM.chatBox.scrollTop = DOM.chatBox.scrollHeight;
        return div.querySelector('.content');
    }

    function appendSystemMessage(text) {
        if (!DOM.chatBox) return;
        const div = document.createElement('div');
        div.style.cssText = "text-align:center; color:var(--text-dim); font-size:12px; margin:12px 0;";
        div.textContent = text;
        DOM.chatBox.appendChild(div);
        DOM.chatBox.scrollTop = DOM.chatBox.scrollHeight;
    }

    function formatMarkdown(text) {
        if (typeof marked !== 'undefined') {
            const renderer = new marked.Renderer();
            renderer.code = function(codeObj, language) {
                let actualCode = "";
                let actualLang = language || 'text';
                if (typeof codeObj === 'object' && codeObj !== null) {
                    actualCode = codeObj.text || "";
                    actualLang = codeObj.lang || language || 'text';
                } else {
                    actualCode = codeObj || "";
                }
                const cleanLang = (actualLang).trim().toLowerCase();
                const snippetId = 'snip_' + Math.random().toString(36).substring(2, 9);
                window.__codeSnippetsRegistry[snippetId] = { code: actualCode, lang: cleanLang };

                let highlightedCode = escapeHtml(actualCode);
                if (typeof hljs !== 'undefined') {
                    try {
                        if (cleanLang && hljs.getLanguage(cleanLang)) {
                            highlightedCode = hljs.highlight(actualCode, { language: cleanLang }).value;
                        } else {
                            highlightedCode = hljs.highlightAuto(actualCode).value;
                        }
                    } catch (e) {
                        highlightedCode = escapeHtml(actualCode);
                    }
                }

                return `
                <div class="code-container">
                    <div class="code-header">
                        <span class="code-lang-name">${cleanLang.toUpperCase()}</span>
                        <div class="code-actions-group">
                            <button class="code-action-btn" title="Télécharger" onclick="downloadCodeSnippet('${snippetId}')">Télécharger</button>
                            <button class="code-action-btn" title="Copier" onclick="copyCodeSnippet('${snippetId}', this)">Copier</button>
                        </div>
                    </div>
                    <pre><code class="hljs language-${cleanLang}">${highlightedCode}</code></pre>
                </div>`;
            };
            try {
                return marked.parse(text, { renderer: renderer, gfm: true, breaks: true });
            } catch (e) {
                return escapeHtml(text).replace(/\n/g, '<br>');
            }
        }
        return escapeHtml(text).replace(/\n/g, '<br>');
    }

    function escapeHtml(text) {
        if (text === null || text === undefined) return "";
        return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    function loadConversationsFromStorage() {
        try {
            const saved = localStorage.getItem('bek_conversations');
            if (saved) conversations = JSON.parse(saved);
        } catch (e) { conversations = []; }
        renderConversationsList();
    }

    function saveConversationsToStorage() {
        try { localStorage.setItem('bek_conversations', JSON.stringify(conversations)); } catch (e) {}
        renderConversationsList();
    }

    function renderConversationsList() {
        if (!DOM.convList) return;
        DOM.convList.innerHTML = conversations.map(c => `
            <div class="conv-item ${c.id === currentConvId ? 'active' : ''}" onclick="loadConversation('${c.id}')" style="display:flex; justify-content:space-between; align-items:center; padding:8px 10px; border-radius:6px; cursor:pointer; font-size:12.5px; margin-bottom:2px;">
                <span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap; flex:1;">${escapeHtml(c.title)}</span>
                <button onclick="event.stopPropagation(); deleteConversation('${c.id}')" style="color:var(--text-dim);">&times;</button>
            </div>
        `).join('');
    }

    function createNewConversation() {
        const id = 'conv_' + Date.now();
        conversations.unshift({ id, title: 'Nouvelle conversation', messages: [] });
        saveConversationsToStorage();
        loadConversation(id);
    }

    window.loadConversation = function(id) {
        currentConvId = id;
        const conv = conversations.find(c => c.id === id);
        if (!conv) return;
        messageHistory = conv.messages || [];
        if (DOM.chatBox) DOM.chatBox.innerHTML = '';
        messageHistory.forEach(m => {
            if (m.role === 'user') appendUserMessage(m.content);
            else if (m.role === 'assistant') appendAssistantMessage(formatMarkdown(m.content));
        });
        renderConversationsList();
    };

    window.deleteConversation = function(id) {
        conversations = conversations.filter(c => c.id !== id);
        saveConversationsToStorage();
        if (conversations.length > 0) loadConversation(conversations[0].id);
        else createNewConversation();
    };

    function saveCurrentConversation() {
        const conv = conversations.find(c => c.id === currentConvId);
        if (!conv) return;
        conv.messages = messageHistory;
        if (messageHistory.length > 0) {
            const first = messageHistory.find(m => m.role === 'user');
            if (first) conv.title = first.content.substring(0, 24) + '...';
        }
        saveConversationsToStorage();
    }

    window.loadSubCRMsUI = async function() {
        const container = document.getElementById('subCrmsListContainer');
        if (!container) return;
        try {
            const res = await fetch(`${API_BASE}/api/matrix/sub_crms?t=${Date.now()}`);
            const json = await res.json();
            container.innerHTML = (json.data || []).map(item => `
                <div style="background:rgba(0,0,0,0.3); border:1px solid var(--border-color); border-radius:8px; padding:12px; display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <div style="font-weight:600; color:#fff; font-size:13.5px;">${escapeHtml(item.niche_name)}</div>
                        <div style="font-size:11px; color:var(--text-dim); font-family:monospace;">ID: ${escapeHtml(item.id)}</div>
                    </div>
                    <button onclick="openSubCRMModal('${item.id}', '${escapeHtml(item.niche_name)}')" style="background:rgba(92,156,230,0.2); color:var(--accent-blue); padding:6px 12px; border-radius:6px; font-size:12px; cursor:pointer;">Ouvrir ➜</button>
                </div>
            `).join('') || '<div style="color:var(--text-dim); text-align:center; padding:10px;">Aucun sous-CRM instancié.</div>';
        } catch (e) {}
    };

    window.loadOpportunitiesUI = async function() {
        const container = document.getElementById('opportunitiesListContainer');
        if (!container) return;
        try {
            const res = await fetch(`${API_BASE}/api/crm/opportunities?t=${Date.now()}`);
            const json = await res.json();
            container.innerHTML = (json.data || []).map(opp => `
                <div style="background:rgba(0,0,0,0.25); border:1px solid var(--border-color); border-radius:6px; padding:10px; display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <div style="color:#fff; font-size:13px;">${escapeHtml(opp.name)}</div>
                        <span style="font-size:10px; background:rgba(255,255,255,0.08); padding:2px 6px; border-radius:4px; color:var(--text-dim);">${escapeHtml(opp.stage)}</span>
                    </div>
                    <div style="display:flex; align-items:center; gap:8px;">
                        <div style="font-weight:bold; color:#4ade80; font-size:13px;">${Number(opp.amount).toLocaleString('fr-FR')} ${escapeHtml(opp.currency)}</div>
                        <button onclick="deleteOpportunityRecord('${opp.id}')" style="color:#ef4444; padding:2px 6px; font-size:11px; cursor:pointer;">&times;</button>
                    </div>
                </div>
            `).join('') || '<div style="color:var(--text-dim); text-align:center; padding:10px;">Aucune opportunité.</div>';
        } catch (e) {}
    };

    window.deleteOpportunityRecord = async function(id) {
        if (!confirm("Supprimer cette opportunité du CRM ?")) return;
        await fetch(`${API_BASE}/api/crm/execute`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sql: `DELETE FROM opportunities WHERE id = ${id};` })
        });
        loadOpportunitiesUI();
    };

    document.addEventListener('DOMContentLoaded', init);
})();