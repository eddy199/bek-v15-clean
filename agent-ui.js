/**
 * BEK-v15-HYBRID — Agent UI Controller (VERSION FINALE C6.3.3)
 * ============================================================
 * Base : ta version GitHub fonctionnelle (v16.2)
 * Fix v6.3.1 : Remplace formatMarkdown par textContent pour préserver les espaces
 * Fix v6.3.2 : RENDU MARKDOWN FINAL (images/vidéos/code/tableaux)
 * Fix v6.3.3 : ★ INJECTION AUTOMATIQUE DES MÉDIAS GÉNÉRÉS
 *              - Détecte les nouveaux fichiers créés pendant la requête
 *              - Les injecte dans la réponse même si le LLM oublie le markdown
 * ============================================================
 */
(function() {
    'use strict';

    const API_BASE = window.location.origin;

    const DOM = {
        chatBox: document.getElementById('chat-box'),
        userInput: document.getElementById('user-input'),
        sendBtn: document.getElementById('send-btn'),
        providerSelect: document.getElementById('providerSelect'),
        modelSelect: document.getElementById('modelSelect'),
        skillsCounter: document.getElementById('navSkillsCount'),
        filesCounter: document.getElementById('navFilesCount'),
        reflexCounter: document.getElementById('navReflexCount'),
        menuOptionsBtn: document.getElementById('menuOptionsBtn'),
        dropdownMenu: document.getElementById('dropdownMenu'),
        uploadBtn: document.getElementById('uploadBtn'),
        uploadMenu: document.getElementById('uploadMenu'),
        btnImportFile: document.getElementById('btnImportFile'),
        btnImportImage: document.getElementById('btnImportImage'),
        hiddenFileInput: document.getElementById('hiddenFileInput'),
        hiddenImageInput: document.getElementById('hiddenImageInput'),
        micBtn: document.getElementById('micBtn'),
        filePreviewBar: document.getElementById('filePreviewBar'),
        convList: document.getElementById('convList'),
        newChatBtn: document.getElementById('newChatBtn'),
        modelBadge: document.getElementById('modelBadge'),
        lightbox: document.getElementById('imageLightbox'),
        lightboxImg: document.getElementById('lightboxImg')
    };

    let currentProvider = 'kimi';
    let currentModel = 'kimi-k3';
    let availableModels = {};
    let messageHistory = [];
    let conversations = [];
    let currentConvId = null;
    let isStreaming = false;
    let attachedFiles = [];
    let pendingUploads = {};
    let activeController = null;
    let globalSkills = [];

    // ─── Reflex state ───
    let reflexFilter = 'staging';
    let reflexProposals = [];

    window.__codeSnippetsRegistry = window.__codeSnippetsRegistry || {};

    // ═══════════════════════════════════════════════════════════════
    // DÉTECTION FICHIERS VIDÉO / AUDIO
    // ═══════════════════════════════════════════════════════════════
    function isVideoUrl(url) {
        if (!url) return false;
        return /\.(mp4|webm|mov|avi|mkv|ogv|m4v)(\?.*)?$/i.test(url);
    }

    function isAudioUrl(url) {
        if (!url) return false;
        return /\.(mp3|wav|ogg|flac|m4a|aac)(\?.*)?$/i.test(url);
    }

    function isImageUrl(url) {
        if (!url) return false;
        return /\.(png|jpg|jpeg|gif|webp|bmp|svg)(\?.*)?$/i.test(url);
    }

    // ═══════════════════════════════════════════════════════════════
    // MERMAID
    // ═══════════════════════════════════════════════════════════════
    function sanitizeMermaid(code) {
        if (!code) return code;
        let out = String(code);

        out = out.replace(/([A-Za-z_][A-Za-z0-9_]*)\[([^\]"\n]+)\]/g, (m, id, label) => {
            const t = label.trim();
            if (t.startsWith('"') && t.endsWith('"')) return m;
            return `${id}["${t.replace(/"/g, "'")}"]`;
        });

        out = out.replace(/([A-Za-z_][A-Za-z0-9_]*)\(([^\)"\n]+)\)/g, (m, id, label) => {
            const t = label.trim();
            if (t.startsWith('"') && t.endsWith('"')) return m;
            if (/[-=]{2,}|-->|==>/.test(t)) return m;
            return `${id}("${t.replace(/"/g, "'")}")`;
        });

        out = out.replace(/([A-Za-z_][A-Za-z0-9_]*)\{([^\}"\n]+)\}/g, (m, id, label) => {
            const t = label.trim();
            if (t.startsWith('"') && t.endsWith('"')) return m;
            return `${id}{"${t.replace(/"/g, "'")}"}`;
        });

        return out;
    }

    function initMermaid() {
        if (!window.mermaid) {
            console.warn('[Mermaid] window.mermaid non chargé');
            return;
        }
        if (window.__mermaidReady) return;
        try {
            mermaid.initialize({
                startOnLoad: false,
                theme: 'dark',
                securityLevel: 'loose',
                themeVariables: {
                    primaryColor: '#1e2a3a',
                    primaryTextColor: '#e2e8f0',
                    primaryBorderColor: '#4f8ef7',
                    lineColor: '#4f8ef7',
                    secondaryColor: '#14181d',
                    tertiaryColor: '#0b0d0f',
                    background: '#0b0d0f',
                    mainBkg: '#14181d',
                    nodeBorder: '#4f8ef7',
                    clusterBkg: '#101317',
                    clusterBorder: '#2a323d',
                    titleColor: '#f8fafc',
                    edgeLabelBackground: '#1a1f26',
                    fontFamily: 'Ubuntu, Inter, sans-serif'
                }
            });
            window.__mermaidReady = true;
            console.log('[Mermaid] initialisé');
        } catch (e) {
            console.error('[Mermaid] init failed:', e);
        }
    }

    function renderMermaidIn(container) {
        if (!container) return;
        if (!window.mermaid) return;
        initMermaid();

        const blocks = container.querySelectorAll('pre code.language-mermaid, pre code.lang-mermaid');
        if (blocks.length === 0) return;

        blocks.forEach((el, idx) => {
            const graph = (el.textContent || '').trim();
            const sanitized = sanitizeMermaid(graph);

            const wrapper = document.createElement('div');
            wrapper.className = 'mermaid-wrapper';
            const target = document.createElement('div');
            target.className = 'mermaid';
            target.id = 'mermaid-' + Date.now() + '-' + idx;
            target.textContent = sanitized;
            wrapper.appendChild(target);

            const codeContainer = el.closest('.code-container') || el.parentElement;
            codeContainer.replaceWith(wrapper);

            try {
                const result = mermaid.run({ nodes: [target] });
                if (result && typeof result.catch === 'function') {
                    result.catch(err => {
                        console.error('[Mermaid] run error bloc ' + idx + ':', err);
                        wrapper.innerHTML =
                            '<div style="color:#ff6b6b; padding:12px; font-size:12px;">⚠️ Mermaid : erreur de rendu</div>' +
                            '<pre style="background:#1a1f26; padding:12px; border-radius:6px; font-size:11px; overflow-x:auto;"><code>' +
                            escapeHtml(graph) + '</code></pre>';
                    });
                }
            } catch (e) {
                console.error('[Mermaid] exception bloc ' + idx + ':', e);
            }
        });
    }

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
                    document.querySelectorAll('.msg-bubble').forEach(m => {
                        m.querySelectorAll('pre code').forEach(el => {
                            if (!el.classList.contains('language-mermaid') && !el.classList.contains('lang-mermaid')) {
                                hljs.highlightElement(el);
                            }
                        });
                    });
                }
            };
            document.head.appendChild(script);
        }
        initMermaid();
    }

    // ═══════════════════════════════════════════════════════════════
    // COPIE / TÉLÉCHARGEMENT
    // ═══════════════════════════════════════════════════════════════
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
            console.error('Erreur :', err);
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
            .msg-bubble {
                white-space: pre-wrap !important;
                word-wrap: break-word !important;
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
                box-shadow: 0 0 8px var(--accent-glow, rgba(79,142,247,0.5));
            }
            @keyframes gemini-blink {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.2; }
            }
            @keyframes pulse-mic {
                0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
                70% { box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); }
                100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
            }
            .recording-active {
                color: #ef4444 !important;
                background: rgba(239, 68, 68, 0.2) !important;
                border-color: #ef4444 !important;
                animation: pulse-mic 1.5s infinite !important;
            }
            .msg-actions {
                display: flex;
                gap: 6px;
                margin-top: 8px;
                opacity: 0.6;
                transition: opacity 0.2s;
            }
            .message:hover .msg-actions {
                opacity: 1;
            }
            .msg-actions button {
                background: transparent;
                border: 1px solid var(--border-color, #3e3e42);
                color: var(--text-dim, #a0a0a5);
                padding: 4px 10px;
                border-radius: 6px;
                font-size: 11px;
                cursor: pointer;
                display: inline-flex;
                align-items: center;
                gap: 5px;
                transition: 0.15s;
            }
            .msg-actions button:hover {
                background: rgba(92, 156, 230, 0.1);
                border-color: var(--accent-blue, #5c9ce6);
                color: var(--accent-blue, #5c9ce6);
            }
            .code-container {
                background: #0d1117;
                border: 1px solid #30363d;
                border-radius: 8px;
                margin: 12px 0;
                overflow: hidden;
            }
            .code-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 8px 14px;
                background: #161b22;
                border-bottom: 1px solid #30363d;
            }
            .code-lang-name {
                font-family: 'Ubuntu Mono', monospace;
                font-size: 11px;
                color: #8b949e;
                text-transform: uppercase;
                letter-spacing: 0.06em;
                font-weight: 600;
            }
            .code-actions-group {
                display: flex;
                gap: 6px;
            }
            .code-action-btn {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid #30363d;
                color: #c9d1d9;
                padding: 4px 10px;
                border-radius: 5px;
                font-size: 11px;
                cursor: pointer;
                transition: 0.15s;
            }
            .code-action-btn:hover {
                background: rgba(92, 156, 230, 0.15);
                border-color: #5c9ce6;
                color: #5c9ce6;
            }
            .code-container pre {
                margin: 0;
                padding: 14px 16px;
                overflow-x: auto;
                background: transparent;
            }
            .code-container pre code {
                font-family: 'Ubuntu Mono', monospace;
                font-size: 13px;
                line-height: 1.5;
                background: transparent !important;
                padding: 0 !important;
            }
            .file-attachment-card {
                display: flex;
                align-items: center;
                gap: 14px;
                background: rgba(30, 41, 59, 0.6);
                border: 1px solid var(--border-color, #3e3e42);
                border-radius: 10px;
                padding: 12px 16px;
                margin: 10px 0;
            }
            .file-attachment-icon {
                font-size: 28px;
            }
            .file-attachment-info {
                flex: 1;
            }
            .file-attachment-name {
                font-weight: 600;
                color: #f8fafc;
                font-size: 13px;
            }
            .file-attachment-desc {
                font-size: 11px;
                color: #94a3b8;
                margin-top: 2px;
            }
            .file-attachment-btn {
                background: var(--accent-blue, #5c9ce6);
                color: #fff;
                padding: 6px 14px;
                border-radius: 6px;
                font-size: 12px;
                text-decoration: none;
                font-weight: 600;
            }
            @keyframes pulseFade {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.7; }
            }
            .spinner-mini {
                width: 16px;
                height: 16px;
                border: 2px solid rgba(92, 156, 230, 0.3);
                border-top-color: var(--accent-blue, #5c9ce6);
                border-radius: 50%;
                animation: spin 0.8s linear infinite;
            }
            @keyframes spin {
                to { transform: rotate(360deg); }
            }
            .file-preview-close {
                background: rgba(0,0,0,0.6);
                color: #fff;
                border: none;
                border-radius: 50%;
                width: 20px;
                height: 20px;
                cursor: pointer;
                font-size: 12px;
                line-height: 1;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .file-preview-close:hover {
                background: #ef4444;
            }
            /* Styles vidéo dans le chat */
            .msg-bubble video {
                max-width: 100% !important;
                max-height: 480px !important;
                border-radius: 12px;
                margin: 16px 0 !important;
                display: block;
                background: #000;
                box-shadow: 0 4px 20px rgba(0,0,0,0.35);
            }
            .msg-bubble audio {
                width: 100%;
                max-width: 480px;
                margin: 16px 0 !important;
                display: block;
            }
            /* Images dans le chat */
            .msg-bubble img {
                max-width: min(560px, 100%) !important;
                max-height: 560px !important;
                width: auto !important;
                height: auto !important;
                object-fit: contain !important;
                border-radius: 12px;
                margin: 16px 0 !important;
                cursor: zoom-in;
                box-shadow: 0 4px 20px rgba(0,0,0,0.3);
                display: block;
                transition: transform 0.2s ease, box-shadow 0.2s ease;
            }
            .msg-bubble img:hover {
                transform: scale(1.01);
                box-shadow: 0 6px 24px rgba(0,0,0,0.4);
            }
        `;
        document.head.appendChild(style);
    }

    // ═══════════════════════════════════════════════════════════════
    // INIT
    // ═══════════════════════════════════════════════════════════════
    async function init() {
        loadSyntaxHighlighter();
        injectEnhancedCSS();
        await loadConfig();
        setupEventListeners();
        setupNavigationTabs();
        setupImagePasteListener();
        loadConversationsFromStorage();
        await refreshReflexBadge();

        if (conversations.length > 0) {
            loadConversation(conversations[0].id);
        } else {
            createNewConversation();
        }
        appendSystemMessage('🟢 BEK-v16.1 HYBRID opérationnel — Reflex Loop intégré.');
    }

    async function loadConfig() {
        try {
            const res = await fetch(`${API_BASE}/api/config?t=${Date.now()}`);
            if (!res.ok) throw new Error("API Config non disponible");
            const data = await res.json();
            availableModels = data.models || {};

            if (!availableModels['kimi']) availableModels['kimi'] = ['kimi-k3', 'kimi-k3-swarm', 'kimi-k3-instant', 'kimi-k2.7-code', 'kimi-k2.6', 'kimi-k2-0905', 'moonshot-v1-128k', 'moonshot-v1-32k', 'moonshot-v1-8k'];
            if (!availableModels['aisa']) availableModels['aisa'] = ['qwen-flash', 'qwen-mt-flash', 'qwen-mt-lite'];
            if (!availableModels['b_ai']) availableModels['b_ai'] = ['glm-5.3-flash', 'qwen3.8-flash', 'mimo-v2.5', 'hy3'];
            if (!availableModels['mistral']) availableModels['mistral'] = ['mistral-medium-3.5', 'mistral-small-4', 'mistral-large-3', 'ministral-3-8b', 'codestral', 'ministral-3-3b', 'ministral-3-14b'];
            if (!availableModels['cohere']) availableModels['cohere'] = ['cohere-command-a-plus', 'cohere-command-a', 'cohere-command-r-plus', 'cohere-command-r', 'cohere-command-r7b', 'cohere-aya-expanse-32b'];
            if (!availableModels['aionlabs']) availableModels['aionlabs'] = ['aion-2.0', 'aion-rp-llama-3.1-8b', 'aion-3.0', 'aion-3.0-mini'];
            if (!availableModels['zhipu']) availableModels['zhipu'] = ['glm-4.7-flash', 'glm-4.5-flash', 'glm-4.6v-flash'];
            if (!availableModels['siliconflow']) availableModels['siliconflow'] = ['siliconflow-qwen3-8b'];
            if (!availableModels['ovh_anonymous']) availableModels['ovh_anonymous'] = ["ovh-qwen-3.5-397b", "ovh-gpt-oss-120b", "ovh-gpt-oss-20b", "ovh-llama-3.3-70b", "ovh-qwen-3.6-27b", "ovh-qwen-3.5-9b", "ovh-qwen-3-32b", "ovh-qwen-coder-30b", "ovh-qwen-vl-72b", "ovh-mistral-small-3.2", "ovh-mistral-nemo", "ovh-mistral-7b"];
            if (!availableModels['kilo_anonymous']) availableModels['kilo_anonymous'] = ["kilo-nemotron-3-ultra-550b", "kilo-step-3.7-flash", "kilo-nemotron-3-super-120b", "kilo-nemotron-3-nano-omni", "kilo-laguna-s", "kilo-laguna-xs", "kilo-north-mini-code", "kilo-openrouter-free", "kilo-hy3", "kilo-nemotron-lightning", "kilo-lfm-2.5"];
            if (!availableModels['llm7_anonymous']) availableModels['llm7_anonymous'] = ["llm7-gpt-oss-20b", "llm7-mistral-nemo", "llm7-minimax-m2.7"];
            if (!availableModels['agnes']) availableModels['agnes'] = ["agnes-v2.0", "agnes-v2.5-flash"];

            let providersList = data.providers || [];
            if (!providersList.some(p => p.id === 'agnes')) {
                providersList.unshift({id: 'agnes', name: 'Agnes AI (Video)', configured: true});
            }

            const requiredProviders = [
                {id: 'agnes', name: 'Agnes AI (Video)', configured: true},
                {id: 'kimi', name: 'Moonshot Kimi AI', configured: true},
                {id: 'aisa', name: 'AIsa (Unified)', configured: true},
                {id: 'b_ai', name: 'B.ai', configured: true},
                {id: 'groq', name: 'Groq', configured: true},
                {id: 'nvidia', name: 'NVIDIA NIM', configured: true},
                {id: 'gemini', name: 'Google Gemini', configured: true},
                {id: 'openrouter', name: 'OpenRouter', configured: true},
                {id: 'mistral', name: 'Mistral AI', configured: true},
                {id: 'cohere', name: 'Cohere', configured: true},
                {id: 'aionlabs', name: 'Aion Labs', configured: true},
                {id: 'zhipu', name: 'Zhipu AI', configured: true},
                {id: 'siliconflow', name: 'SiliconFlow', configured: true},
                {id: 'ovh_anonymous', name: 'OVHcloud (Anonyme)', configured: true},
                {id: 'kilo_anonymous', name: 'Kilo Code (Anonyme)', configured: true},
                {id: 'llm7_anonymous', name: 'LLM7.io (Anonyme)', configured: true}
            ];

            requiredProviders.forEach(rp => {
                if (!providersList.some(p => p.id === rp.id)) {
                    providersList.push(rp);
                }
            });

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
            DOM.providerSelect.value = 'kimi';
            updateModelSelect();
            await loadFilesList();
        } catch (e) {
            console.warn('Erreur config :', e);
        }
    }

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
            if (res.ok) await loadFilesList();
            else alert(`Erreur : HTTP ${res.status}`);
        } catch (e) {
            alert(`Erreur réseau : ${e}`);
        }
    };

    window.deleteAllProjectFiles = async function() {
        if (!confirm("Voulez-vous vraiment TOUT supprimer dans la session (uploads et fichiers générés) ?")) return;
        try {
            const res = await fetch(`${API_BASE}/api/files/delete-all`, { method: 'POST' });
            if (res.ok) {
                await loadFilesList();
            } else {
                alert(`Erreur : HTTP ${res.status}`);
            }
        } catch (e) {
            alert(`Erreur réseau : ${e}`);
        }
    };

    function populateSkillsView(skills) {
        const view = document.getElementById('viewSkills');
        if (!view) return;
        view.innerHTML = `
            <h2>Compétences Actives (${skills.length})</h2>
            <p style="color:var(--text-dim); font-size:12.5px; margin-bottom:18px; background:rgba(255,255,255,0.05); padding:10px 14px; border-radius:8px;">
                💡 <strong>Note :</strong> Les noms et descriptions des modules proviennent de la base de données open-source mondiale.
            </p>
            <div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(280px, 1fr)); gap:12px;">` +
            skills.map(s => {
                const cmd = s.command || s.name || '';
                const fullCmd = cmd.startsWith('/') ? cmd : '/' + cmd;
                return `
                <div style="background:var(--bg-card); border:1px solid var(--border-color); padding:14px; border-radius:8px; display:flex; flex-direction:column; justify-content:space-between;">
                    <div>
                        <strong style="color:var(--text-main); font-size:14px;">${escapeHtml(s.name)}</strong>
                        <p style="color:var(--text-dim); font-size:12px; margin: 6px 0 10px;">
                            <span style="background:rgba(255,255,255,0.1); padding:2px 4px; border-radius:4px; font-size:9px; margin-right:4px;">EN</span>
                            ${escapeHtml(s.description || 'Module externe (Description non disponible)')}
                        </p>
                    </div>
                    <div style="margin-top: 6px;">
                        <button onclick="insertPromptToChat('${escapeHtml(fullCmd)}')" style="cursor:pointer; background:rgba(92,156,230,0.15); border:1px solid rgba(92,156,230,0.4); color:var(--accent-blue); padding:6px 10px; border-radius:6px; font-family:'Ubuntu Mono', monospace; font-size:12px; font-weight:bold; width:100%; text-align:left; transition:0.2s;">
                            Exécuter : ${escapeHtml(fullCmd)} ➜
                        </button>
                    </div>
                </div>
            `}).join('') + `</div>`;
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
        view.innerHTML = '<p style="color:var(--text-dim);">Chargement…</p>';
        try {
            const res = await fetch(`${API_BASE}/api/memory?t=${Date.now()}`);
            if (!res.ok) throw new Error("API manquante");
            const data = await res.json();
            const pineconeColor = (data.pinecone_status || '').includes('Connecté') ? '#4ade80' : '#f5a623';

            const memories = data.memory || data.memories || [];
            let memoriesHtml = '';
            if (memories.length > 0) {
                memoriesHtml = memories.slice(0, 10).map(m => `
                    <div style="background:var(--bg-card); border:1px solid var(--border-color); border-radius:8px; padding:12px 16px; margin-bottom:8px;">
                        <div style="font-size:13px; color:#e2e8f0; margin-bottom:6px;">${escapeHtml(m.content || '')}</div>
                        <div style="font-size:11px; color:var(--text-dim); font-family:monospace;">${escapeHtml(m.timestamp || '')}</div>
                    </div>
                `).join('');
            } else {
                memoriesHtml = '<p style="color:var(--text-dim); text-align:center; padding:20px;">Aucun souvenir vectoriel pour l\'instant.</p>';
            }

            view.innerHTML = `
                <h2>Mémoire Long Terme & Index Vectoriel</h2>
                <div style="margin-top:16px; display:flex; flex-direction:column; gap:16px;">
                    <div class="matrix-widget">
                        <h3 style="margin:0;">Pinecone Vector Database :
                            <span style="color:${pineconeColor};">${escapeHtml(data.pinecone_status || '—')}</span>
                        </h3>
                        <p style="color:var(--text-dim); font-size:13px; margin-top:8px;">
                            Indexation vectorielle des conversations et règles d'or synchronisée en temps réel.
                        </p>
                        <div style="margin-top:12px; font-family:monospace; font-size:12px; color:var(--accent-blue);">
                            - Entités Neon DB totales : ${data.neon_state_entries ?? '—'}<br>
                            - Règles BEK synchronisées : ${data.system_rules_synced ? 'OUI' : 'NON'}
                        </div>
                    </div>
                    <div class="matrix-widget">
                        <h3 style="margin:0 0 12px 0;">Souvenirs Récents</h3>
                        ${memoriesHtml}
                    </div>
                </div>
            `;
        } catch (e) {
            view.innerHTML = `<p style="color:#ff4a4a">Erreur de chargement mémoire : ${escapeHtml(String(e))}</p>`;
        }
    }

    async function loadConnectorsView() {
        const view = document.getElementById('viewConnectors');
        if (!view) return;
        view.innerHTML = '<p style="color:var(--text-dim);">Chargement…</p>';
        try {
            const res = await fetch(`${API_BASE}/api/connectors?t=${Date.now()}`);
            if (!res.ok) throw new Error("API manquante");
            const data = await res.json();
            view.innerHTML = `<h2>Connecteurs Système & Serveurs</h2>
                <div style="margin-top:16px; display:flex; flex-direction:column; gap:10px;">` +
                (data.connectors || []).map(c => {
                    let statusColor = '#4ade80';
                    const s = (c.status || '').toLowerCase();
                    if (s.includes('erreur') || s.includes('error')) statusColor = '#ff4a4a';
                    else if (s.includes('non configur') || s.includes('inconnu')) statusColor = '#f5a623';
                    return `
                    <div style="background:var(--bg-card); border:1px solid var(--border-color); padding:14px; border-radius:8px; display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <strong>${escapeHtml(c.name || '—')}</strong>
                            <div style="font-size:11px; color:var(--text-dim); margin-top:2px;">Type : ${escapeHtml(c.type || '—')}</div>
                        </div>
                        <div style="display:flex; align-items:center; gap:10px;">
                            <span style="font-size:11px; font-family:monospace; color:var(--text-dim);">${c.latency_ms ?? 0} ms</span>
                            <span style="background:rgba(255,255,255,0.05); color:${statusColor}; padding:3px 8px; border-radius:4px; font-size:11px; font-weight:bold;">${escapeHtml(c.status || '—')}</span>
                        </div>
                    </div>`;
                }).join('') + `</div>`;
        } catch (e) {
            view.innerHTML = `<p style="color:#ff4a4a">Erreur connecteurs : ${escapeHtml(String(e))}</p>`;
        }
    }

    // ═══════════════════════════════════════════════════════════════
    // REFLEX UI
    // ═══════════════════════════════════════════════════════════════
    async function refreshReflexBadge() {
        try {
            const res = await fetch(`${API_BASE}/api/reflex/stats?t=${Date.now()}`);
            if (!res.ok) return;
            const data = await res.json();
            if (DOM.reflexCounter) {
                DOM.reflexCounter.textContent = data.staging || 0;
                DOM.reflexCounter.style.color = (data.staging || 0) > 0 ? '#f5a623' : '';
            }
        } catch (e) {
            // silent
        }
    }

    window.setReflexFilter = function(filter) {
        reflexFilter = filter;
        document.querySelectorAll('[data-reflex-filter]').forEach(btn => {
            btn.classList.toggle('active', btn.getAttribute('data-reflex-filter') === filter);
        });
        renderReflexProposals();
    };

    window.runReflexCycle = async function() {
        const btn = event?.target;
        if (btn) {
            btn.disabled = true;
            btn.textContent = '⏳ Cycle en cours…';
        }
        try {
            const res = await fetch(`${API_BASE}/api/reflex/run-cycle?hours=24&with_critic=false&with_forge=true&forge_dry_run=true`, {
                method: 'POST',
            });
            const data = await res.json();
            if (!res.ok) {
                alert(`Erreur : ${data.detail || data.message || res.status}`);
                return;
            }
            alert(`✅ Cycle terminé\n\nPropositions créées : ${data.forge?.proposed ?? 0}\nRapport : ${data.report_id || '—'}`);
            await loadReflexUI();
        } catch (e) {
            alert(`Erreur réseau : ${e}`);
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.textContent = '▶️ Lancer un cycle';
            }
        }
    };

    window.loadReflexUI = async function() {
        const container = document.getElementById('reflexProposalsContainer');
        if (container) container.innerHTML = '<div class="reflex-empty">Chargement…</div>';

        try {
            const res = await fetch(`${API_BASE}/api/reflex/stats?t=${Date.now()}`);
            if (res.ok) {
                const stats = await res.json();
                const setTxt = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val ?? '—'; };
                setTxt('reflexStatTotal', stats.total ?? 0);
                setTxt('reflexStatStaging', stats.staging ?? 0);
                setTxt('reflexStatApproved', stats.approved ?? 0);
                setTxt('reflexStatRejected', stats.rejected ?? 0);
            }
        } catch (e) {
            console.warn('[Reflex] stats échec :', e);
        }

        try {
            let url = `${API_BASE}/api/reflex/history?limit=200&t=${Date.now()}`;
            if (reflexFilter) url += `&status=${encodeURIComponent(reflexFilter)}`;
            const res = await fetch(url);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            reflexProposals = data.proposals || [];
            renderReflexProposals();
            await refreshReflexBadge();
        } catch (e) {
            if (container) {
                container.innerHTML = `<div class="reflex-empty" style="color:#ef4444;">
                    Erreur de chargement : ${escapeHtml(String(e))}
                </div>`;
            }
        }
    };

    function renderReflexProposals() {
        const container = document.getElementById('reflexProposalsContainer');
        if (!container) return;

        const filtered = reflexFilter
            ? reflexProposals.filter(p => p.status === reflexFilter)
            : reflexProposals;

        if (filtered.length === 0) {
            container.innerHTML = '<div class="reflex-empty">Aucune proposition pour ce filtre.</div>';
            return;
        }

        container.innerHTML = filtered.map(p => {
            const content = p.content_parsed || {};
            const extra = p.extra_parsed || {};
            const sig = content.trigger || {};
            const ruleType = content.rule_type || p.rule_type || 'unknown';
            const confidence = typeof p.confidence === 'number'
                ? (p.confidence * 100).toFixed(0) + '%'
                : '—';
            const description = (content.action && content.action.description) || '—';
            const status = p.status || 'unknown';

            const ruleClass = `reflex-rule-${ruleType}`;

            const actionButtons = status === 'staging' ? `
                <div class="reflex-actions">
                    <button class="reflex-btn-approve" onclick="approveReflexProposal('${escapeHtml(p.proposal_id)}')">✅ Approuver</button>
                    <button class="reflex-btn-reject" onclick="rejectReflexProposal('${escapeHtml(p.proposal_id)}')">❌ Rejeter</button>
                    <button class="reflex-btn-inspect" onclick="inspectReflexProposal('${escapeHtml(p.proposal_id)}')">🔍 Inspecter</button>
                </div>
            ` : `
                <div class="reflex-actions">
                    <button class="reflex-btn-inspect" onclick="inspectReflexProposal('${escapeHtml(p.proposal_id)}')">🔍 Inspecter</button>
                </div>
            `;

            return `
                <div class="reflex-proposal">
                    <div class="reflex-proposal-header">
                        <div>
                            <div class="reflex-proposal-title">
                                <span class="${ruleClass} reflex-rule-type">${escapeHtml(ruleType)}</span>
                                ${escapeHtml(sig.action || 'unknown')}/${escapeHtml(sig.error_type || '-')}
                            </div>
                            <div class="reflex-proposal-id">${escapeHtml(p.proposal_id)}</div>
                        </div>
                        <div style="text-align:right;">
                            <div class="reflex-confidence">Confiance : <strong>${confidence}</strong></div>
                            <div class="reflex-confidence">Statut : <strong>${escapeHtml(status)}</strong></div>
                        </div>
                    </div>

                    <div class="reflex-meta-row">
                        <span>Occurrences : <strong>${sig.min_occurrences ?? '—'}</strong></span>
                        <span>Critique source : <strong>${escapeHtml(extra.critique_category || '—')}</strong> / <strong>${escapeHtml(extra.critique_severity || '—')}</strong></span>
                    </div>

                    <div class="reflex-description">
                        ${escapeHtml(description)}
                    </div>

                    ${actionButtons}
                </div>
            `;
        }).join('');
    }

    window.approveReflexProposal = async function(proposalId) {
        if (!confirm(`Approuver la proposition ${proposalId} ?`)) return;
        try {
            const res = await fetch(`${API_BASE}/api/reflex/approve/${encodeURIComponent(proposalId)}`, {
                method: 'POST',
            });
            const data = await res.json();
            if (!res.ok) {
                alert(`Erreur : ${data.detail || data.message || res.status}`);
                return;
            }
            await loadReflexUI();
        } catch (e) {
            alert(`Erreur réseau : ${e}`);
        }
    };

    window.rejectReflexProposal = async function(proposalId) {
        if (!confirm(`Rejeter la proposition ${proposalId} ?`)) return;
        try {
            const res = await fetch(`${API_BASE}/api/reflex/reject/${encodeURIComponent(proposalId)}`, {
                method: 'POST',
            });
            const data = await res.json();
            if (!res.ok) {
                alert(`Erreur : ${data.detail || data.message || res.status}`);
                return;
            }
            await loadReflexUI();
        } catch (e) {
            alert(`Erreur réseau : ${e}`);
        }
    };

    window.inspectReflexProposal = async function(proposalId) {
        try {
            const res = await fetch(`${API_BASE}/api/reflex/inspect/${encodeURIComponent(proposalId)}`);
            if (!res.ok) {
                alert(`Erreur : HTTP ${res.status}`);
                return;
            }
            const data = await res.json();
            const content = data.proposal?.content_parsed || data.proposal || {};
            const txt = JSON.stringify(content, null, 2);
            alert(`Proposition ${proposalId} :\n\n${txt}`);
        } catch (e) {
            alert(`Erreur réseau : ${e}`);
        }
    };

    // ═══════════════════════════════════════════════════════════════
    // MODELS + NAV + EVENTS
    // ═══════════════════════════════════════════════════════════════
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
                    if (window.loadSubCRMsUI) window.loadSubCRMsUI();
                    if (window.loadOpportunitiesUI) window.loadOpportunitiesUI();
                } else if (tabName === 'reflex') {
                    const view = document.getElementById('viewReflex');
                    view.classList.add('active');
                    view.style.display = 'block';
                    loadReflexUI();
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

        if (DOM.userInput) {
            DOM.userInput.addEventListener('input', function() {
                this.style.height = '24px';
                const newHeight = Math.min(this.scrollHeight, 180);
                this.style.height = newHeight + 'px';
                this.style.overflowY = this.scrollHeight > 180 ? 'auto' : 'hidden';
            });
            DOM.userInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSendOrStop();
                }
            });
        }

        if (DOM.sendBtn) DOM.sendBtn.addEventListener('click', handleSendOrStop);
        if (DOM.newChatBtn) DOM.newChatBtn.addEventListener('click', createNewConversation);

        if (DOM.menuOptionsBtn && DOM.dropdownMenu) {
            DOM.menuOptionsBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                DOM.dropdownMenu.style.display = DOM.dropdownMenu.style.display === 'block' ? 'none' : 'block';
            });
        }

        if (DOM.uploadBtn && DOM.uploadMenu) {
            DOM.uploadBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                DOM.uploadMenu.style.display = (DOM.uploadMenu.style.display === 'block') ? 'none' : 'block';
            });
        }

        if (DOM.btnImportFile) {
            DOM.btnImportFile.addEventListener('click', (e) => {
                e.stopPropagation();
                if (DOM.hiddenFileInput) DOM.hiddenFileInput.click();
                if (DOM.uploadMenu) DOM.uploadMenu.style.display = 'none';
            });
        }

        if (DOM.btnImportImage) {
            DOM.btnImportImage.addEventListener('click', (e) => {
                e.stopPropagation();
                if (DOM.hiddenImageInput) DOM.hiddenImageInput.click();
                if (DOM.uploadMenu) DOM.uploadMenu.style.display = 'none';
            });
        }

        DOM.hiddenFileInput?.addEventListener('change', async (e) => {
            for (const file of Array.from(e.target.files)) await uploadFileToServer(file);
        });

        DOM.hiddenImageInput?.addEventListener('change', async (e) => {
            for (const file of Array.from(e.target.files)) await uploadFileToServer(file);
        });

        if (DOM.micBtn && DOM.userInput) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

            if (SpeechRecognition) {
                const recognition = new SpeechRecognition();
                recognition.lang = 'fr-FR';
                recognition.interimResults = true;
                recognition.continuous = false;

                let isRecording = false;

                const resetMicUI = () => {
                    isRecording = false;
                    DOM.micBtn.classList.remove('recording-active');
                    DOM.micBtn.style.color = '';
                    DOM.micBtn.style.backgroundColor = '';
                    DOM.micBtn.style.border = '';
                    DOM.userInput.placeholder = "Écrivez votre message, parlez au micro, ou joignez un fichier/ZIP jusqu'à 300 Mo...";
                };

                DOM.micBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    if (isRecording) { recognition.stop(); return; }
                    try { recognition.start(); } catch (err) { resetMicUI(); }
                });

                recognition.onstart = () => {
                    isRecording = true;
                    DOM.micBtn.classList.add('recording-active');
                    DOM.micBtn.style.color = '#ef4444';
                    DOM.micBtn.style.backgroundColor = 'rgba(239, 68, 68, 0.2)';
                    DOM.micBtn.style.border = '1px solid #ef4444';
                    DOM.userInput.placeholder = "🎤 Écoute en cours... Parlez maintenant";
                };

                recognition.onresult = (event) => {
                    let finalTranscript = '';
                    for (let i = event.resultIndex; i < event.results.length; ++i) {
                        if (event.results[i].isFinal) finalTranscript += event.results[i][0].transcript;
                    }
                    if (finalTranscript) {
                        const currentVal = DOM.userInput.value;
                        DOM.userInput.value = currentVal + (currentVal && !currentVal.endsWith(' ') ? ' ' : '') + finalTranscript + ' ';
                        DOM.userInput.style.height = 'auto';
                        DOM.userInput.style.height = Math.min(DOM.userInput.scrollHeight, 180) + 'px';
                    }
                };

                recognition.onerror = () => { resetMicUI(); };
                recognition.onend = () => { resetMicUI(); };
            } else {
                DOM.micBtn.style.display = 'none';
            }
        }

        // Lightbox via délégation d'événements (images)
        if (DOM.chatBox && DOM.lightbox && DOM.lightboxImg) {
            DOM.chatBox.addEventListener('click', (e) => {
                const img = e.target.closest('img');
                if (img && img.closest('.msg-bubble')) {
                    DOM.lightboxImg.src = img.src;
                    DOM.lightbox.classList.add('active');
                }
            });
            DOM.lightbox.addEventListener('click', () => {
                DOM.lightbox.classList.remove('active');
                setTimeout(() => { DOM.lightboxImg.src = ''; }, 300);
            });
        }

        document.addEventListener('click', () => {
            if (DOM.dropdownMenu) DOM.dropdownMenu.style.display = 'none';
            if (DOM.uploadMenu) DOM.uploadMenu.style.display = 'none';
        });

        document.getElementById('menuClear')?.addEventListener('click', () => {
            if (DOM.chatBox) DOM.chatBox.innerHTML = '';
            messageHistory = [];
            saveCurrentConversation();
            if (DOM.dropdownMenu) DOM.dropdownMenu.style.display = 'none';
        });

        document.getElementById('menuExportPdf')?.addEventListener('click', () => {
            if (DOM.dropdownMenu) DOM.dropdownMenu.style.display = 'none';
            window.print();
        });

        document.getElementById('menuShare')?.addEventListener('click', () => {
            if (DOM.dropdownMenu) DOM.dropdownMenu.style.display = 'none';
            navigator.clipboard.writeText(JSON.stringify(messageHistory, null, 2));
            alert("Historique copié !");
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
        const tempId = `upload_${Date.now()}_${Math.random().toString(36).slice(2)}`;
        pendingUploads[tempId] = {
            name: file.name,
            size: file.size,
            status: 'uploading',
            progress: 0,
        };
        renderAttachedFilesPreview();

        const formData = new FormData();
        formData.append('file', file);
        try {
            const resp = await fetch(`${API_BASE}/api/upload?t=${Date.now()}`, {
                method: 'POST',
                body: formData,
            });
            const data = await resp.json();
            if (resp.ok) {
                delete pendingUploads[tempId];
                attachedFiles.push({
                    filename: data.filename,
                    size: file.size,
                    type: file.type,
                    status: 'done',
                });
                renderAttachedFilesPreview();
                if (window.loadFilesList) await window.loadFilesList();
            } else {
                pendingUploads[tempId].status = 'error';
                pendingUploads[tempId].error = data.error || 'Erreur inconnue';
                renderAttachedFilesPreview();
                setTimeout(() => {
                    delete pendingUploads[tempId];
                    renderAttachedFilesPreview();
                }, 4000);
            }
        } catch (err) {
            pendingUploads[tempId].status = 'error';
            pendingUploads[tempId].error = 'Erreur réseau';
            renderAttachedFilesPreview();
            setTimeout(() => {
                delete pendingUploads[tempId];
                renderAttachedFilesPreview();
            }, 4000);
        }
    }

    function getFileIcon(filename, mimeType) {
        const ext = (filename.split('.').pop() || '').toLowerCase();
        if (mimeType?.startsWith('image/') || ['png','jpg','jpeg','gif','webp','bmp','svg'].includes(ext)) return '🖼️';
        if (mimeType?.startsWith('video/') || ['mp4','webm','mov','avi','mkv'].includes(ext)) return '🎬';
        if (mimeType?.startsWith('audio/') || ['mp3','wav','ogg','flac','m4a'].includes(ext)) return '🎵';
        if (ext === 'pdf') return '📕';
        if (['zip','rar','7z','tar','gz'].includes(ext)) return '🗜️';
        if (['exe','msi','bat','sh','cmd'].includes(ext)) return '⚙️';
        if (['doc','docx','odt'].includes(ext)) return '📝';
        if (['xls','xlsx','ods','csv'].includes(ext)) return '📊';
        if (['ppt','pptx','odp'].includes(ext)) return '📽️';
        if (['txt','md','log'].includes(ext)) return '📄';
        if (['json','xml','yaml','yml','toml','ini'].includes(ext)) return '🔧';
        if (['js','ts','py','java','c','cpp','rs','go','rb','php','html','css','sql'].includes(ext)) return '💻';
        return '📎';
    }

    function formatFileSize(bytes) {
        if (!bytes || bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
    }

    function renderAttachedFilesPreview() {
        if (!DOM.filePreviewBar) return;

        const pendingCount = Object.keys(pendingUploads).length;
        const totalCount = attachedFiles.length + pendingCount;

        if (totalCount === 0) {
            DOM.filePreviewBar.style.display = 'none';
            DOM.filePreviewBar.innerHTML = '';
            return;
        }

        DOM.filePreviewBar.style.display = 'flex';
        DOM.filePreviewBar.style.flexWrap = 'wrap';
        DOM.filePreviewBar.style.gap = '10px';
        DOM.filePreviewBar.style.padding = '10px 0';

        let html = '';

        for (const [tempId, info] of Object.entries(pendingUploads)) {
            const isError = info.status === 'error';
            const borderColor = isError ? '#ef4444' : 'var(--accent-blue)';
            html += `
                <div class="file-preview-item" style="
                    position:relative; min-width:200px; max-width:280px;
                    padding:12px 14px; border-radius:12px;
                    border:1px solid ${borderColor};
                    background:rgba(30,41,59,0.6);
                    display:flex; align-items:center; gap:12px;
                    box-shadow:0 4px 10px rgba(0,0,0,0.3);
                    animation: pulseFade 1.5s ease-in-out infinite;
                ">
                    <div style="font-size:24px;">${isError ? '⚠️' : '⏳'}</div>
                    <div style="flex:1; overflow:hidden;">
                        <div style="font-size:12px; font-weight:600; color:#f8fafc; text-overflow:ellipsis; white-space:nowrap; overflow:hidden;">
                            ${escapeHtml(info.name)}
                        </div>
                        <div style="font-size:11px; color:${isError ? '#ef4444' : '#94a3b8'}; margin-top:2px;">
                            ${isError ? escapeHtml(info.error || 'Erreur') : `Upload en cours… ${formatFileSize(info.size)}`}
                        </div>
                    </div>
                    ${!isError ? `<div class="spinner-mini"></div>` : ''}
                </div>
            `;
        }

        html += attachedFiles.map((f, i) => {
            const filename = typeof f === 'string' ? f : f.filename;
            const size = typeof f === 'object' ? f.size : 0;
            const type = typeof f === 'object' ? f.type : '';
            const icon = getFileIcon(filename, type);
            const isImg = filename.match(/\.(png|jpe?g|gif|webp|bmp|svg)$/i);
            const isVideo = filename.match(/\.(mp4|webm|mov|avi|mkv)$/i);

            if (isImg) {
                return `
                    <div class="file-preview-item" style="
                        position:relative; width:80px; height:80px;
                        border-radius:12px; border:1px solid var(--border-color);
                        overflow:hidden; box-shadow:0 4px 10px rgba(0,0,0,0.3);
                    ">
                        <img src="${API_BASE}/api/download/${encodeURIComponent(filename)}"
                             style="width:100%; height:100%; object-fit:cover;"
                             alt="${escapeHtml(filename)}">
                        <button onclick="removeAttachedFile(${i})" class="file-preview-close"
                                style="position:absolute; top:4px; right:4px;">✕</button>
                    </div>
                `;
            }

            if (isVideo) {
                return `
                    <div class="file-preview-item" style="
                        position:relative; width:160px; height:90px;
                        border-radius:12px; border:1px solid var(--border-color);
                        overflow:hidden; box-shadow:0 4px 10px rgba(0,0,0,0.3);
                        background:#000;
                    ">
                        <video src="${API_BASE}/api/download/${encodeURIComponent(filename)}"
                               style="width:100%; height:100%; object-fit:cover;" muted></video>
                        <div style="position:absolute; bottom:0; left:0; right:0; padding:2px 6px;
                                    background:linear-gradient(transparent, rgba(0,0,0,0.8));
                                    color:#fff; font-size:10px; text-overflow:ellipsis;
                                    white-space:nowrap; overflow:hidden;">
                            🎬 ${escapeHtml(filename)}
                        </div>
                        <button onclick="removeAttachedFile(${i})" class="file-preview-close"
                                style="position:absolute; top:4px; right:4px;">✕</button>
                    </div>
                `;
            }

            return `
                <div class="file-preview-item" style="
                    position:relative; min-width:180px; max-width:280px;
                    padding:10px 12px; border-radius:12px;
                    border:1px solid var(--border-color);
                    background:rgba(30,41,59,0.6);
                    display:flex; align-items:center; gap:10px;
                    box-shadow:0 4px 10px rgba(0,0,0,0.3);
                ">
                    <div style="font-size:24px;">${icon}</div>
                    <div style="flex:1; overflow:hidden;">
                        <div style="font-size:12px; font-weight:600; color:#f8fafc;
                                    text-overflow:ellipsis; white-space:nowrap; overflow:hidden;">
                            ${escapeHtml(filename)}
                        </div>
                        <div style="font-size:11px; color:#94a3b8; margin-top:2px;">
                            ${size ? formatFileSize(size) : 'Prêt'}
                        </div>
                    </div>
                    <button onclick="removeAttachedFile(${i})" class="file-preview-close"
                            style="position:relative; top:auto; right:auto;">✕</button>
                </div>
            `;
        }).join('');

        DOM.filePreviewBar.innerHTML = html;
    }

    window.removeAttachedFile = function(index) {
        attachedFiles.splice(index, 1);
        renderAttachedFilesPreview();
    };

    function handleSendOrStop() {
        if (isStreaming) stopGeneration();
        else sendMessage();
    }

    function stopGeneration() {
        if (activeController) { activeController.abort(); activeController = null; }
        isStreaming = false;
        if (DOM.sendBtn) DOM.sendBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>`;
    }

    // ═══════════════════════════════════════════════════════════════
    // ★ v6.3.3 — INJECTION AUTOMATIQUE DES MÉDIAS GÉNÉRÉS
    // ------------------------------------------------------------------
    // Détecte les nouveaux fichiers (images/vidéos) créés pendant la requête
    // et les injecte dans la réponse, même si le LLM a "oublié" le markdown.
    // ═══════════════════════════════════════════════════════════════
    async function injectNewMediaFiles(assistantDiv, filesBefore, fullResponse) {
        try {
            // Attendre que les fichiers soient bien écrits sur disque
            await new Promise(r => setTimeout(r, 800));

            // Récupérer la liste actuelle
            const res = await fetch(`${API_BASE}/api/files?t=${Date.now()}`);
            if (!res.ok) {
                console.warn('[Media] Impossible de récupérer la liste des fichiers');
                return;
            }
            const data = await res.json();
            const filesAfter = data.files || [];

            // Identifier les nouveaux fichiers
            const beforeNames = new Set((filesBefore || []).map(f => f.name));
            const newFiles = filesAfter.filter(f => !beforeNames.has(f.name));

            // Extensions supportées
            const imageExts = ['png', 'jpg', 'jpeg', 'webp', 'gif'];
            const videoExts = ['mp4', 'webm', 'mov', 'avi', 'mkv'];
            const audioExts = ['mp3', 'wav', 'ogg', 'm4a'];

            const isMedia = (name) => {
                const ext = (name.split('.').pop() || '').toLowerCase();
                return [...imageExts, ...videoExts, ...audioExts].includes(ext);
            };

            // Filtrer les nouveaux médias
            let mediaToInject = newFiles.filter(f => isMedia(f.name));

            // Fallback : si aucun nouveau média détecté mais que la réponse mentionne une génération
            const responseLower = (fullResponse || '').toLowerCase();
            const mentionsImage = responseLower.includes('image générée') ||
                                  responseLower.includes('image generee') ||
                                  responseLower.includes('logo généré') ||
                                  responseLower.includes('image créée') ||
                                  responseLower.includes('image cr��e');
            const mentionsVideo = responseLower.includes('vidéo générée') ||
                                  responseLower.includes('video generee') ||
                                  responseLower.includes('vidéo créée');

            if (mediaToInject.length === 0 && (mentionsImage || mentionsVideo)) {
                console.log('[Media] Fallback : recherche des derniers médias générés');
                // Prendre les 3 derniers médias du dossier generated (pas uploads)
                mediaToInject = filesAfter
                    .filter(f => isMedia(f.name) && (f.folder === 'generated' || f.folder?.includes('generated')))
                    .slice(0, 3);
            }

            if (mediaToInject.length === 0) {
                console.log('[Media] Aucun média à injecter');
                return;
            }

            // Vérifier si le markdown contient déjà un lien vers ces fichiers
            const responseHasMarkdownImage = /!\[.*?\]\(.*?\)/.test(fullResponse || '');
            const alreadyDisplayed = mediaToInject.some(f => {
                const name = f.name || '';
                return (fullResponse || '').includes(name);
            });

            if (responseHasMarkdownImage && alreadyDisplayed) {
                console.log('[Media] Le markdown contient déjà les médias, skip injection');
                return;
            }

            console.log('[Media] ✅ Injection automatique de', mediaToInject.length, 'média(s)');

            // Créer un conteneur pour les médias
            const mediaContainer = document.createElement('div');
            mediaContainer.style.cssText = 'margin-top: 16px; display: flex; flex-direction: column; gap: 12px; padding-top: 12px; border-top: 1px solid rgba(255,255,255,0.06);';

            for (const f of mediaToInject) {
                const name = f.name || '';
                const ext = (name.split('.').pop() || '').toLowerCase();
                const url = `${API_BASE}/api/download/${encodeURIComponent(name)}`;

                if (imageExts.includes(ext)) {
                    const img = document.createElement('img');
                    img.src = url;
                    img.alt = name;
                    img.loading = 'lazy';
                    img.style.cssText = `
                        max-width: min(560px, 100%);
                        max-height: 560px;
                        width: auto;
                        height: auto;
                        object-fit: contain;
                        border-radius: 12px;
                        margin: 0;
                        cursor: zoom-in;
                        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
                        display: block;
                        transition: transform 0.2s ease;
                    `;
                    img.onmouseenter = () => img.style.transform = 'scale(1.01)';
                    img.onmouseleave = () => img.style.transform = 'scale(1)';
                    mediaContainer.appendChild(img);
                } else if (videoExts.includes(ext)) {
                    const video = document.createElement('video');
                    video.src = url;
                    video.controls = true;
                    video.loop = true;
                    video.muted = true;
                    video.playsInline = true;
                    video.preload = 'metadata';
                    video.style.cssText = `
                        max-width: min(640px, 100%);
                        max-height: 480px;
                        border-radius: 12px;
                        background: #000;
                        box-shadow: 0 4px 20px rgba(0,0,0,0.35);
                        display: block;
                    `;
                    mediaContainer.appendChild(video);
                } else if (audioExts.includes(ext)) {
                    const audio = document.createElement('audio');
                    audio.src = url;
                    audio.controls = true;
                    audio.preload = 'metadata';
                    audio.style.cssText = 'width: 100%; max-width: 480px; display: block;';
                    mediaContainer.appendChild(audio);
                }
            }

            assistantDiv.appendChild(mediaContainer);

        } catch (e) {
            console.warn('[Media] Échec injection automatique :', e);
        }
    }

    async function sendMessage() {
        if (!DOM.userInput || !DOM.sendBtn || !DOM.chatBox) return;
        const text = DOM.userInput.value.trim();
        if (!text && attachedFiles.length === 0) return;

        let fullTextContent = text;
        if (attachedFiles.length > 0) {
            fullTextContent += "\n[Fichiers joints : " + attachedFiles.map(f => typeof f === 'string' ? f : f.filename).join(', ') + "]";

            const imageFiles = attachedFiles.filter(f => {
                const name = typeof f === 'string' ? f : f.filename;
                return name.match(/\.(png|jpe?g|gif|webp)$/i);
            });
            const zipFiles = attachedFiles.filter(f => {
                const name = typeof f === 'string' ? f : f.filename;
                return name.match(/\.zip$/i);
            });

            if (imageFiles.length > 0) {
                const firstName = typeof imageFiles[0] === 'string' ? imageFiles[0] : imageFiles[0].filename;
                fullTextContent += "\n(INSTRUCTION SYSTEME : L'utilisateur a attaché ces images. Tu DOIS utiliser l'action [ACTION:analyze_image]{\"image_path\": \"uploads/" + firstName + "\", \"prompt\": \"Décris cette image en détail\"}[/ACTION] pour les lire).";
            }
            if (zipFiles.length > 0) {
                const firstName = typeof zipFiles[0] === 'string' ? zipFiles[0] : zipFiles[0].filename;
                fullTextContent += "\n(INSTRUCTION SYSTEME : Utilise [ACTION:analyze_zip_content]{\"zip_path\": \"uploads/" + firstName + "\"}[/ACTION]).";
            }
        }

        // ★ v6.3.3 — Snapshot AVANT d'envoyer pour détecter les nouveaux fichiers
        let filesBefore = [];
        try {
            const resBefore = await fetch(`${API_BASE}/api/files?t=${Date.now()}`);
            if (resBefore.ok) {
                const dataBefore = await resBefore.json();
                filesBefore = dataBefore.files || [];
            }
        } catch (e) {
            console.warn('[Media] Snapshot avant échoué :', e);
        }

        appendUserMessage(fullTextContent);

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
                            // ★ Pendant le streaming : texte brut pour perf
                            assistantDiv.textContent = fullResponse;
                            DOM.chatBox.scrollTop = DOM.chatBox.scrollHeight;
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
                assistantDiv.innerHTML = `<span style="color:#ff4a4a;">Erreur : ${err.message}</span>`;
            }
        } finally {
            isStreaming = false;
            activeController = null;

            // ★ RENDU MARKDOWN FINAL (images/vidéos/code/tableaux)
            if (fullResponse) {
                assistantDiv.innerHTML = formatMarkdown(fullResponse);

                // Rendu des diagrammes Mermaid
                renderMermaidIn(assistantDiv);

                // Re-highlight des blocs de code
                if (window.hljs) {
                    assistantDiv.querySelectorAll('pre code').forEach(el => {
                        if (!el.classList.contains('language-mermaid') &&
                            !el.classList.contains('lang-mermaid')) {
                            try { hljs.highlightElement(el); } catch (e) {}
                        }
                    });
                }
            } else {
                assistantDiv.innerHTML = '<span style="color:#ff6b6b;">⚠️ Réponse vide</span>';
            }

            // ★ v6.3.3 — INJECTION AUTOMATIQUE DES NOUVEAUX MÉDIAS
            await injectNewMediaFiles(assistantDiv, filesBefore, fullResponse);

            // Rafraîchir la liste des fichiers dans la sidebar
            if (window.loadFilesList) {
                try { await window.loadFilesList(); } catch (e) {}
            }

            // Scroll final en bas
            DOM.chatBox.scrollTop = DOM.chatBox.scrollHeight;

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
                <span class="name">BEK-v16 Hybrid</span>
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
        let cleanText = text.replace(/<think>[\s\S]*?(?:<\/think>|$)/gi, '');

        cleanText = cleanText.replace(/\[FILE:(.*?)\]\((.*?)\)/g, (match, filename, url) => {
            return `<div class="file-attachment-card"><div class="file-attachment-icon">📄</div><div class="file-attachment-info"><div class="file-attachment-name">${filename}</div><div class="file-attachment-desc">Fichier généré prêt au téléchargement</div></div><a href="${url}" target="_blank" download class="file-attachment-btn">Télécharger</a></div>`;
        });

        if (typeof marked !== 'undefined') {
            const renderer = new marked.Renderer();

            // Rendu personnalisé des images ET vidéos
            renderer.image = function(href, title, text) {
                const url = href || '';
                const cleanTitle = title || '';
                const cleanAlt = (text || '').replace(/"/g, '&quot;');

                // Détection vidéo
                if (isVideoUrl(url)) {
                    return `<video controls loop muted playsinline preload="metadata" src="${url}" title="${cleanTitle}"></video>`;
                }

                // Détection audio
                if (isAudioUrl(url)) {
                    return `<audio controls preload="metadata" src="${url}" title="${cleanTitle}"></audio>`;
                }

                // Image normale
                return `<img src="${url}" alt="${cleanAlt}" title="${cleanTitle}" loading="lazy">`;
            };

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

                if (cleanLang === 'mermaid') {
                    const sanitized = sanitizeMermaid(actualCode);
                    return `<pre><code class="language-mermaid">${escapeHtml(sanitized)}</code></pre>`;
                }

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
                return marked.parse(cleanText, { renderer: renderer, gfm: true, breaks: true });
            } catch (e) {
                return escapeHtml(cleanText).replace(/\n/g, '<br>');
            }
        }
        return escapeHtml(cleanText).replace(/\n/g, '<br>');
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
                <button onclick="event.stopPropagation(); deleteConversation('${c.id}')" style="color:var(--text-dim); background:none; border:none; cursor:pointer;">&times;</button>
            </div>
        `).join('');
    }

    function createNewConversation() {
        const id = 'conv_' + Date.now();
        conversations.unshift({ id, title: 'Nouvelle conversation', messages: [] });
        saveConversationsToStorage();
        loadConversation(id);
    }

    // Chargement d'anciennes conversations avec rendu markdown complet
    window.loadConversation = function(id) {
        currentConvId = id;
        const conv = conversations.find(c => c.id === id);
        if (!conv) return;
        messageHistory = conv.messages || [];
        if (DOM.chatBox) DOM.chatBox.innerHTML = '';

        messageHistory.forEach(m => {
            if (m.role === 'user') {
                appendUserMessage(m.content);
            } else if (m.role === 'assistant') {
                const div = appendAssistantMessage('');
                if (m.content) {
                    div.innerHTML = formatMarkdown(m.content);
                    renderMermaidIn(div);
                    if (window.hljs) {
                        div.querySelectorAll('pre code').forEach(el => {
                            if (!el.classList.contains('language-mermaid') &&
                                !el.classList.contains('lang-mermaid')) {
                                try { hljs.highlightElement(el); } catch (e) {}
                            }
                        });
                    }
                } else {
                    div.textContent = '';
                }
            }
        });
        renderConversationsList();
    };

    window.deleteConversation = function(id) {
        conversations = conversations.filter(c => c.id !== id);
        saveConversationsToStorage();
        if (conversations.length > 0) loadConversation(conversations[0].id);
        else createNewConversation();
    }

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

    // ═══════════════════════════════════════════════════════════════
    // CRM MATRIX BEK
    // ═══════════════════════════════════════════════════════════════
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
                    <button onclick="openSubCRMModal('${item.id}', '${escapeHtml(item.niche_name)}')" style="background:rgba(92,156,230,0.2); color:var(--accent-blue); padding:6px 12px; border-radius:6px; font-size:12px; cursor:pointer; border:none;">Ouvrir ➜</button>
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
                        <button onclick="deleteOpportunityRecord('${opp.id}')" style="color:#ef4444; padding:2px 6px; font-size:11px; cursor:pointer; background:none; border:none;">&times;</button>
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
        if (window.loadOpportunitiesUI) window.loadOpportunitiesUI();
    };

    // Stubs pour modales CRM
    window.promptSpawnNewSubCRM = function() {};
    window.promptCreateOpportunity = function() {};
    window.closeSubCRMModal = function() {};
    window.switchModalTab = function() {};
    window.promptAddEntity = function() {};
    window.promptAddOperation = function() {};
    window.openSubCRMModal = function() {};

    document.addEventListener('DOMContentLoaded', init);
})();