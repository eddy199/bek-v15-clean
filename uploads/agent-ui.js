/* ═══════════════════════════════════════════════════════════════
   BEK-v15 Hybrid — Agent UI Complet (Version Finale Déboguée)
   ═══════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  const State = {
    tab: 'chat',
    config: null,
    providers: [],
    models: {},
    selectedProvider: 'groq',
    selectedModel: 'openai/gpt-oss-120b',
    useMemory: true,
    isStreaming: false,
    streamAbort: null,
    conversations: [],
    currentConvId: null,
    skills: [],
    files: [],
    connectors: [],
    plugins: [],
    connSearch: '',
    pendingImages: [],
    pendingFiles: []
  };

  const $ = (s) => document.querySelector(s);
  const $$ = (s) => document.querySelectorAll(s);

  function esc(s) {
    const d = document.createElement('div');
    d.textContent = String(s ?? '');
    return d.innerHTML;
  }

  function escAttr(s) {
    return String(s ?? '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/'/g, '&#39;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function uid() { return 'm' + Date.now().toString(36) + Math.random().toString(36).slice(2, 7); }

  function fmtSize(bytes) {
    if (!bytes && bytes !== 0) return '0 o';
    if (typeof bytes === 'string') return bytes;
    if (bytes < 1024) return bytes + ' o';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' Ko';
    return (bytes / 1048576).toFixed(1) + ' Mo';
  }

  function formatLangName(lang) {
    if (!lang) return 'Code';
    const l = lang.toLowerCase();
    if (l === 'py' || l === 'python') return 'Python';
    if (l === 'js' || l === 'javascript') return 'JavaScript';
    if (l === 'ts' || l === 'typescript') return 'TypeScript';
    if (l === 'html') return 'HTML';
    if (l === 'css') return 'CSS';
    if (l === 'json') return 'JSON';
    if (l === 'sh' || l === 'bash') return 'Shell';
    if (l === 'sql') return 'SQL';
    if (l === 'cpp' || l === 'c++') return 'C++';
    if (l === 'c') return 'C';
    return lang.charAt(0).toUpperCase() + lang.slice(1);
  }

  async function api(path, opts = {}) {
    const res = await fetch(path, {
      headers: { 'Content-Type': 'application/json' },
      ...opts,
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    });
    if (!res.ok) {
      const t = await res.text();
      throw new Error(t || res.statusText);
    }
    return res.json();
  }

  function toast(msg, type = 'ok') {
    let root = $('#toastRoot');
    if (!root) {
      root = document.createElement('div');
      root.id = 'toastRoot';
      root.style.cssText = 'position:fixed;bottom:20px;right:20px;z-index:999999;display:flex;flex-direction:column;gap:8px;pointer-events:none;';
      document.body.appendChild(root);
    }
    const el = document.createElement('div');
    el.className = 'toast ' + type;
    el.style.cssText = 'background:#1e293b;color:#f8fafc;padding:10px 18px;border-radius:8px;border:1px solid #6366f1;font-size:13px;box-shadow:0 4px 15px rgba(0,0,0,0.6);pointer-events:auto;';
    el.textContent = msg;
    root.appendChild(el);
    setTimeout(() => { el.style.opacity = '0'; el.style.transition = '.3s'; setTimeout(() => el.remove(), 300); }, 2600);
  }

  function loadConversations() {
    try { State.conversations = JSON.parse(localStorage.getItem('bek_conv_v2') || '[]'); } catch (e) { State.conversations = []; }
  }
  function saveConversations() {
    try { localStorage.setItem('bek_conv_v2', JSON.stringify(State.conversations)); } catch (e) {}
  }
  function currentConv() {
    return State.conversations.find((c) => c.id === State.currentConvId) || null;
  }
  function newConversation() {
    const c = {
      id: uid(),
      title: 'Nouvelle conversation',
      provider: State.selectedProvider,
      model: State.selectedModel,
      pinned: false,
      messages: [],
      ts: Date.now(),
    };
    State.conversations.unshift(c);
    State.currentConvId = c.id;
    saveConversations();
    renderConvList();
    renderMessages();
  }
  function deleteConversation(id) {
    State.conversations = State.conversations.filter((c) => c.id !== id);
    if (State.currentConvId === id) {
      State.currentConvId = State.conversations[0]?.id || null;
      renderMessages();
    }
    saveConversations();
    renderConvList();
  }
  function updateConvTitle(c, text) {
    if (c.messages.length === 1 && (c.title === 'Nouvelle conversation')) {
      c.title = text.length > 35 ? text.slice(0, 35) + '…' : text;
    }
  }

  document.addEventListener('DOMContentLoaded', init);

  async function init() {
    bindGlobal();
    loadConversations();
    await loadConfig();
    $('#memoryToggle')?.classList.toggle('active', State.useMemory);
    renderConvList();
    renderMessages();
    renderView();
    refreshStatus();
    setupGeminiActionsMenu();
    setupGeminiPlusMenu();
  }

  function bindGlobal() {
    $('#newChatBtn')?.addEventListener('click', newConversation);
    $('#settingsBtn')?.addEventListener('click', openSettingsModal);
    
    const helpBtn = $('#helpBtn');
    if (helpBtn) {
      helpBtn.title = 'Options de la conversation';
      helpBtn.onclick = (e) => {
        e.stopPropagation();
        toggleGeminiMenu();
      };
    }

    $('#memoryToggle')?.addEventListener('click', () => {
      State.useMemory = !State.useMemory;
      $('#memoryToggle').classList.toggle('active', State.useMemory);
      toast(State.useMemory ? 'Mémoire activée' : 'Mémoire désactivée');
    });

    $('#providerSelect')?.addEventListener('change', (e) => {
      State.selectedProvider = e.target.value;
      State.selectedModel = (State.models[State.selectedProvider] || [])[0] || null;
      updateModelSelect();
      const c = currentConv();
      if (c) { c.provider = State.selectedProvider; c.model = State.selectedModel; saveConversations(); }
      updateBadge();
    });

    $('#modelSelect')?.addEventListener('change', (e) => {
      State.selectedModel = e.target.value;
      const c = currentConv();
      if (c) { c.model = State.selectedModel; saveConversations(); }
      updateBadge();
    });

    $$('.nav-item').forEach((item) => item.addEventListener('click', () => switchTab(item.dataset.tab)));

    const ta = $('#chatInput');
    if (ta) {
      ta.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
      });
      ta.addEventListener('input', autoResize);
      ta.addEventListener('paste', handlePaste);
    }
    window.addEventListener('paste', (e) => {
      if (e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
        handlePaste(e);
      }
    });

    const allFileInput = document.createElement('input');
    allFileInput.id = 'allFileInput';
    allFileInput.type = 'file';
    allFileInput.multiple = true;
    allFileInput.style.display = 'none';
    allFileInput.addEventListener('change', handleFileSelect);
    document.body.appendChild(allFileInput);

    const photosInput = document.createElement('input');
    photosInput.id = 'photosInput';
    photosInput.type = 'file';
    photosInput.accept = 'image/*';
    photosInput.multiple = true;
    photosInput.style.display = 'none';
    photosInput.addEventListener('change', handleFileSelect);
    document.body.appendChild(photosInput);

    const codeInput = document.createElement('input');
    codeInput.id = 'codeInput';
    codeInput.type = 'file';
    codeInput.accept = '.py,.js,.ts,.html,.css,.json,.md,.sh,.csv,.sql,.env,.yml,.yaml';
    codeInput.multiple = true;
    codeInput.style.display = 'none';
    codeInput.addEventListener('change', handleFileSelect);
    document.body.appendChild(codeInput);

    let plusBtn = $('#uploadBtn');
    if (!plusBtn) {
      plusBtn = document.createElement('button');
      plusBtn.id = 'uploadBtn';
      plusBtn.className = 'icon-btn';
      plusBtn.title = 'Ajouter et Créer';
      plusBtn.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 5v14M5 12h14"/></svg>';
      plusBtn.style.marginRight = '8px';
      plusBtn.style.cursor = 'pointer';
      plusBtn.style.display = 'flex';
      plusBtn.style.alignItems = 'center';
      plusBtn.style.justifyContent = 'center';

      const inputWrap = ta ? ta.parentElement : null;
      if (inputWrap) {
        inputWrap.insertBefore(plusBtn, inputWrap.firstChild);
      }
    }

    let previewBar = $('#filePreviewBar');
    if (!previewBar) {
      previewBar = document.createElement('div');
      previewBar.id = 'filePreviewBar';
      previewBar.style.display = 'none';
      previewBar.style.flexWrap = 'wrap';
      previewBar.style.gap = '8px';
      previewBar.style.padding = '8px 12px';
      previewBar.style.background = 'rgba(255, 255, 255, 0.05)';
      previewBar.style.borderRadius = '8px';
      previewBar.style.marginBottom = '8px';

      const inputContainer = ta ? (ta.closest('.chat-input-box') || ta.parentElement.parentElement) : null;
      if (inputContainer && ta.parentElement) {
        inputContainer.insertBefore(previewBar, ta.parentElement);
      }
    }

    const dropZone = document.body;
    dropZone.addEventListener('dragover', (e) => { e.preventDefault(); e.stopPropagation(); });
    dropZone.addEventListener('drop', (e) => {
      e.preventDefault();
      e.stopPropagation();
      const files = Array.from(e.dataTransfer?.files || []);
      if (files.length) processFiles(files);
    });

    $('#sendBtn')?.addEventListener('click', sendMessage);

    $('#convSearch')?.addEventListener('input', (e) => {
      State.connSearch = e.target.value.trim().toLowerCase();
      renderConvList();
    });
  }

  // ─── Menu Popover d'Ajout (+) ───
  function setupGeminiPlusMenu() {
    let menu = $('#geminiPlusMenuDropdown');
    if (menu) return;

    menu = document.createElement('div');
    menu.id = 'geminiPlusMenuDropdown';
    menu.style.cssText = `
      display: none; position: fixed; bottom: 85px; left: 280px; background: #1e293b;
      border: 1px solid #334155; border-radius: 14px; box-shadow: 0 16px 35px rgba(0,0,0,0.65);
      width: 250px; z-index: 99999; padding: 8px 0; font-family: inherit;
    `;

    menu.innerHTML = `
      <div class="p-item" data-act="upload_all" style="display:flex;align-items:center;gap:12px;padding:10px 16px;cursor:pointer;font-size:13px;color:#f8fafc;">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48"/></svg>
        Importer des fichiers
      </div>
      <div id="moreImportsTrigger" style="position:relative;display:flex;align-items:center;justify-content:space-between;padding:10px 16px;cursor:pointer;font-size:13px;color:#f8fafc;">
        <div style="display:flex;align-items:center;gap:12px;">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/></svg>
          Importations spécifiques
        </div>
        <span style="font-size:11px;color:#94a3b8;">›</span>

        <div id="moreImportsSubmenu" style="display:none;position:absolute;left:245px;top:-10px;background:#1e293b;border:1px solid #334155;border-radius:12px;box-shadow:0 12px 30px rgba(0,0,0,0.65);width:200px;padding:6px 0;">
          <div class="p-sub-item" data-act="upload_photos" style="display:flex;align-items:center;gap:12px;padding:9px 16px;cursor:pointer;font-size:13px;color:#f8fafc;">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>
            Photos
          </div>
          <div class="p-sub-item" data-act="upload_code" style="display:flex;align-items:center;gap:12px;padding:9px 16px;cursor:pointer;font-size:13px;color:#f8fafc;">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 18l6-6-6-6M8 6l-6 6 6 6"/></svg>
            Importer du code
          </div>
        </div>
      </div>
      <div style="height:1px;background:#334155;margin:6px 0;"></div>
      <div class="p-item" data-act="create_image" style="display:flex;align-items:center;gap:12px;padding:10px 16px;cursor:pointer;font-size:13px;color:#38bdf8;">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h7M16 5l3 3M19 2l3 3"/></svg>
        Créer une image
      </div>
      <div class="p-item" data-act="create_video" style="display:flex;align-items:center;gap:12px;padding:10px 16px;cursor:pointer;font-size:13px;color:#a855f7;">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="2.18"/><path d="M7 2v20M17 2v20M2 12h20M2 7h5M2 17h5M17 17h5M17 7h5"/></svg>
        Créer une vidéo
      </div>
    `;

    document.body.appendChild(menu);

    const plusBtn = $('#uploadBtn');
    if (plusBtn) {
      plusBtn.onclick = (e) => {
        e.stopPropagation();
        const r = plusBtn.getBoundingClientRect();
        menu.style.left = Math.max(10, r.left - 20) + 'px';
        menu.style.bottom = (window.innerHeight - r.top + 10) + 'px';
        menu.style.display = menu.style.display === 'none' ? 'block' : 'none';
      };
    }

    const trigger = $('#moreImportsTrigger');
    const submenu = $('#moreImportsSubmenu');
    trigger?.addEventListener('mouseenter', () => { submenu.style.display = 'block'; });
    trigger?.addEventListener('mouseleave', () => { submenu.style.display = 'none'; });

    document.addEventListener('click', (e) => {
      if (!menu.contains(e.target) && e.target !== plusBtn) {
        menu.style.display = 'none';
      }
    });

    menu.querySelectorAll('.p-item, .p-sub-item').forEach((item) => {
      item.addEventListener('mouseenter', () => { item.style.background = '#334155'; });
      item.addEventListener('mouseleave', () => { item.style.background = 'transparent'; });
      item.addEventListener('click', (e) => {
        e.stopPropagation();
        menu.style.display = 'none';
        executeGeminiPlusAction(item.dataset.act);
      });
    });
  }

  async function executeGeminiPlusAction(action) {
    switch (action) {
      case 'upload_all': $('#allFileInput')?.click(); break;
      case 'upload_photos': $('#photosInput')?.click(); break;
      case 'upload_code': $('#codeInput')?.click(); break;
      case 'create_image': {
        const prompt = window.prompt('Décrivez l\'image :');
        if (!prompt || !prompt.trim()) return;
        toast('Génération de l\'image...');
        try {
          const res = await api('/api/media/generate', { method: 'POST', body: { type: 'image', prompt: prompt.trim() } });
          if (res.ok) {
            let conv = currentConv();
            if (!conv) newConversation();
            conv = currentConv();
            conv.messages.push({
              id: uid(),
              role: 'assistant',
              content: `### 🎨 Image générée : *${esc(res.prompt)}*\n\n![${esc(res.prompt)}](${res.url})`,
              model: 'Pollinations AI'
            });
            saveConversations();
            renderMessages();
          }
        } catch (e) { toast(e.message, 'err'); }
        break;
      }
      case 'create_video': {
        const prompt = window.prompt('Décrivez la scène vidéo :');
        if (!prompt || !prompt.trim()) return;
        toast('Génération de la vidéo...');
        try {
          const res = await api('/api/media/generate', { method: 'POST', body: { type: 'video', prompt: prompt.trim() } });
          if (res.ok) {
            let conv = currentConv();
            if (!conv) newConversation();
            conv = currentConv();
            conv.messages.push({
              id: uid(),
              role: 'assistant',
              content: `### 🎬 Vidéo animée : *${esc(res.prompt)}*\n\n<img src="${res.url}" style="max-width:100%;border-radius:8px;border:1px solid #4f46e5;">`,
              model: 'Pollinations Video'
            });
            saveConversations();
            renderMessages();
          }
        } catch (e) { toast(e.message, 'err'); }
        break;
      }
    }
  }

  // ─── Menu Options (⋮) ───
  function setupGeminiActionsMenu() {
    let menu = $('#geminiActionMenuDropdown');
    if (menu) return;

    menu = document.createElement('div');
    menu.id = 'geminiActionMenuDropdown';
    menu.style.cssText = `
      display: none; position: fixed; top: 55px; right: 20px; background: #1e293b;
      border: 1px solid #334155; border-radius: 12px; box-shadow: 0 12px 30px rgba(0,0,0,0.6);
      width: 250px; z-index: 99999; overflow: hidden; padding: 6px 0; font-family: inherit;
    `;

    menu.innerHTML = `
      <div class="g-opt" data-act="share" style="display:flex;align-items:center;gap:12px;padding:10px 16px;cursor:pointer;font-size:13px;color:#f8fafc;">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 12v8a2 2 0 002 2h12a2 2 0 002-2v-8M16 6l-4-4-4 4M12 2v13"/></svg>
        Partager
      </div>
      <div class="g-opt" data-act="pin" style="display:flex;align-items:center;gap:12px;padding:10px 16px;cursor:pointer;font-size:13px;color:#f8fafc;">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 17v5M5 12V7a7 7 0 0114 0v5l2 3H3l2-3z"/></svg>
        Épingler
      </div>
      <div class="g-opt" data-act="rename" style="display:flex;align-items:center;gap:12px;padding:10px 16px;cursor:pointer;font-size:13px;color:#f8fafc;">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
        Renommer
      </div>
      <div class="g-opt" data-act="docs" style="display:flex;align-items:center;gap:12px;padding:10px 16px;cursor:pointer;font-size:13px;color:#f8fafc;">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8zM14 2v6h6"/></svg>
        Exporter (MD)
      </div>
      <div style="height:1px;background:#334155;margin:4px 0;"></div>
      <div class="g-opt" data-act="del" style="display:flex;align-items:center;gap:12px;padding:10px 16px;cursor:pointer;font-size:13px;color:#ef4444;">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg>
        Supprimer
      </div>
    `;

    document.body.appendChild(menu);

    document.addEventListener('click', (e) => {
      if (!menu.contains(e.target) && e.target !== $('#helpBtn')) {
        menu.style.display = 'none';
      }
    });

    menu.querySelectorAll('.g-opt').forEach((item) => {
      item.addEventListener('mouseenter', () => { item.style.background = '#334155'; });
      item.addEventListener('mouseleave', () => { item.style.background = 'transparent'; });
      item.addEventListener('click', () => {
        menu.style.display = 'none';
        executeGeminiAction(item.dataset.act);
      });
    });
  }

  function toggleGeminiMenu() {
    const menu = $('#geminiActionMenuDropdown');
    if (!menu) return;
    menu.style.display = menu.style.display === 'none' ? 'block' : 'none';
  }

  function executeGeminiAction(action) {
    const conv = currentConv();
    if (!conv) return toast('Aucune conversation active', 'err');

    switch (action) {
      case 'share': {
        const textShare = conv.messages.map(m => `--- ${m.role === 'user' ? 'Vous' : 'BEK'}:\n${m.content}`).join('\n\n');
        navigator.clipboard.writeText(textShare);
        toast('Lien & Contenu copiés !');
        break;
      }
      case 'pin': {
        conv.pinned = !conv.pinned;
        saveConversations();
        renderConvList();
        toast(conv.pinned ? 'Discussion épinglée 📌' : 'Discussion désépinglée');
        break;
      }
      case 'rename': {
        const newName = prompt('Renommer la discussion :', conv.title);
        if (newName && newName.trim()) {
          conv.title = newName.trim();
          saveConversations();
          renderConvList();
          toast('Discussion renommée');
        }
        break;
      }
      case 'docs': {
        const content = `# ${conv.title}\nDate: ${new Date(conv.ts).toLocaleString()}\n\n` +
          conv.messages.map(m => `### ${m.role === 'user' ? 'Utilisateur' : 'BEK'}\n\n${m.content}\n`).join('\n---\n\n');
        const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = `${conv.title.replace(/[^a-z0-9]/gi, '_').toLowerCase()}.md`;
        a.click();
        toast('Document exporté (.md)');
        break;
      }
      case 'del': {
        if (confirm('Voulez-vous supprimer définitivement cette conversation ?')) {
          deleteConversation(conv.id);
          toast('Conversation supprimée');
        }
        break;
      }
    }
  }

  function autoResize() {
    const ta = $('#chatInput');
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 140) + 'px';
  }

  function handlePaste(e) {
    const items = (e.clipboardData || window.clipboardData)?.items;
    if (!items) return;
    let found = false;

    for (let i = 0; i < items.length; i++) {
      if (items[i].type.indexOf('image') !== -1) {
        const blob = items[i].getAsFile();
        processFiles([blob]);
        found = true;
      }
    }
    if (found) e.preventDefault();
  }

  function handleFileSelect(e) {
    const files = Array.from(e.target.files || []);
    if (files.length) processFiles(files);
    e.target.value = '';
  }

  async function processFiles(files) {
    const maxSize = 300 * 1024 * 1024;

    for (const file of files) {
      if (file.size > maxSize) {
        toast(`${file.name} dépasse 300 Mo`, 'err');
        continue;
      }

      if (file.type.startsWith('image/')) {
        const reader = new FileReader();
        reader.onload = (event) => {
          State.pendingImages.push({
            id: uid(),
            blob: file,
            base64: event.target.result,
            name: file.name || `image_${Date.now()}.png`
          });
          renderPreviews();
          toast(`Image attachée : ${file.name || 'Capture'}`);
        };
        reader.readAsDataURL(file);
      } else {
        toast(`Téléversement de ${file.name}...`);
        const fd = new FormData();
        fd.append('file', file);
        try {
          const res = await fetch('/api/upload', { method: 'POST', body: fd });
          const data = await res.json();
          if (data.ok) {
            State.pendingFiles.push({
              id: uid(),
              name: data.filename,
              path: data.path,
              size: data.size,
              text: data.text_sample || '',
            });
            renderPreviews();
            toast(`Fichier prêt : ${data.filename}`);
            if (State.tab === 'files') renderFiles();
          } else {
            toast(data.error || 'Erreur téléversement', 'err');
          }
        } catch (err) {
          toast('Erreur téléversement: ' + err.message, 'err');
        }
      }
    }
  }

  function renderPreviews() {
    const bar = $('#filePreviewBar');
    if (!bar) return;
    const total = State.pendingImages.length + State.pendingFiles.length;
    if (total === 0) {
      bar.style.display = 'none';
      bar.innerHTML = '';
      return;
    }
    bar.style.display = 'flex';

    let html = '';
    html += State.pendingImages.map((img) => `
      <div style="position:relative;display:inline-block;">
        <img src="${img.base64}" style="height:60px;border-radius:6px;border:1px solid #4f46e5;object-fit:cover;">
        <button data-del-img="${img.id}" style="position:absolute;top:-6px;right:-6px;background:#ef4444;color:#fff;border:none;border-radius:50%;width:18px;height:18px;font-size:10px;font-weight:bold;cursor:pointer;line-height:18px;text-align:center;">✕</button>
      </div>`).join('');

    html += State.pendingFiles.map((f) => {
      const ext = (f.name.split('.').pop() || 'FILE').toUpperCase().slice(0, 4);
      return `
      <div style="position:relative;display:flex;align-items:center;background:#1e293b;padding:6px 12px;border-radius:6px;border:1px solid #334155;color:#e2e8f0;font-size:12px;gap:8px;">
        <span style="font-weight:bold;color:#38bdf8;">${esc(ext)}</span>
        <span>${esc(f.name.length > 20 ? f.name.slice(0, 18) + '…' : f.name)} (${fmtSize(f.size)})</span>
        <button data-del-file="${f.id}" style="background:transparent;border:none;color:#ef4444;cursor:pointer;font-weight:bold;margin-left:4px;">✕</button>
      </div>`;
    }).join('');

    bar.innerHTML = html;

    bar.querySelectorAll('[data-del-img]').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        State.pendingImages = State.pendingImages.filter((im) => im.id !== e.target.dataset.delImg);
        renderPreviews();
      });
    });

    bar.querySelectorAll('[data-del-file]').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        State.pendingFiles = State.pendingFiles.filter((f) => f.id !== e.target.dataset.delFile);
        renderPreviews();
      });
    });
  }

  async function loadConfig() {
    try {
      State.config = await api('/api/config');
      State.providers = State.config.providers.filter((p) => p.configured);
      if (State.providers.length === 0) State.providers = State.config.providers;
      State.models = State.config.models || {};
      
      const savedProv = $('#providerSelect')?.value || State.selectedProvider;
      if (State.providers.find((p) => p.id === savedProv)) {
        State.selectedProvider = savedProv;
      } else {
        State.selectedProvider = State.providers[0]?.id || 'groq';
      }
      State.selectedModel = $('#modelSelect')?.value || (State.models[State.selectedProvider] || [])[0] || null;

      updateProviderSelect();
      if ($('#navSkillsCount')) $('#navSkillsCount').textContent = State.config.skills_count ?? '0';
      if ($('#navFilesCount')) $('#navFilesCount').textContent = State.config.files_count ?? '0';
    } catch (e) {
      if ($('#statusDot')) $('#statusDot').className = 'dot err';
      if ($('#statusText')) $('#statusText').textContent = 'Serveur injoignable';
    }
  }

  function updateProviderSelect() {
    const sel = $('#providerSelect');
    if (!sel) return;
    sel.innerHTML = State.providers.map((p) =>
      `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('');
    sel.value = State.selectedProvider || '';
    updateModelSelect();
  }

  function updateModelSelect() {
    const sel = $('#modelSelect');
    if (!sel) return;
    const mods = State.models[State.selectedProvider] || [];
    if (!mods.length) {
      sel.innerHTML = '<option>Aucun modèle</option>';
      sel.disabled = true;
      return;
    }
    sel.disabled = false;
    sel.innerHTML = mods.map((m) => `<option value="${esc(m)}">${esc(m)}</option>`).join('');
    if (State.selectedModel && mods.includes(State.selectedModel)) {
      sel.value = State.selectedModel;
    } else {
      State.selectedModel = mods[0];
      sel.value = State.selectedModel;
    }
    updateBadge();
  }

  function updateBadge() {
    const b = $('#modelBadge');
    if (b) b.textContent = State.selectedModel || '—';
  }

  async function refreshStatus() {
    try {
      const st = await api('/api/system/status');
      const configuredCount = Object.values(st.providers).filter(Boolean).length;
      if ($('#statusDot')) $('#statusDot').className = 'dot ' + (configuredCount > 0 ? 'ok' : 'err');
      if ($('#statusText')) $('#statusText').textContent = configuredCount + ' provider(s) actif(s)';
    } catch (e) {}
  }

  function renderConvList() {
    const list = $('#convList');
    if (!list) return;
    const q = State.connSearch;
    
    const convs = [...State.conversations].sort((a, b) => (b.pinned ? 1 : 0) - (a.pinned ? 1 : 0))
      .filter((c) => !q || c.title.toLowerCase().includes(q));

    if (!convs.length) {
      list.innerHTML = '<div class="conv-empty">' + (q ? 'Aucun résultat' : 'Aucune conversation') + '</div>';
      return;
    }

    list.innerHTML = convs.map((c) => `
      <div class="conv-item ${c.id === State.currentConvId ? 'active' : ''}" data-id="${c.id}">
        <span style="opacity:${c.pinned ? '1' : '0.4'};font-size:12px;">${c.pinned ? '📌' : '💬'}</span>
        <span class="conv-title">${esc(c.title)}</span>
        <button class="conv-del" data-del="${c.id}" title="Supprimer">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
        </button>
      </div>`).join('');

    list.querySelectorAll('.conv-item').forEach((el) => {
      el.addEventListener('click', (e) => {
        if (e.target.closest('.conv-del')) return;
        State.currentConvId = el.dataset.id;
        renderConvList();
        renderMessages();
      });
    });
    list.querySelectorAll('.conv-del').forEach((el) => {
      el.addEventListener('click', (e) => {
        e.stopPropagation();
        deleteConversation(el.dataset.del);
      });
    });
  }

  function switchTab(tab) {
    State.tab = tab;
    $$('.nav-item').forEach((n) => n.classList.toggle('active', n.dataset.tab === tab));
    $$('.view').forEach((v) => v.classList.remove('active'));
    $('#view' + capitalize(tab))?.classList.add('active');
    renderView();
  }
  function capitalize(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

  function renderView() {
    switch (State.tab) {
      case 'chat': break;
      case 'skills': renderSkills(); break;
      case 'files': renderFiles(); break;
      case 'memory': renderMemory(); break;
      case 'plugins': renderPlugins(); break;
      case 'connectors': renderConnectors(); break;
    }
  }

  function renderMessages() {
    const container = $('#messages');
    if (!container) return;
    const conv = currentConv();

    if (!conv || !conv.messages.length) {
      container.innerHTML = `
        <div class="empty-state" style="padding:40px 20px;text-align:center;">
          <div style="font-size:36px;margin-bottom:12px;">✨</div>
          <h2 style="font-size:24px;font-weight:500;color:#f8fafc;margin-bottom:8px;">Que souhaitez-vous explorer ?</h2>
          <p style="color:#94a3b8;font-size:14px;max-width:500px;margin:0 auto;">Agent IA multi-modèles avec streaming et gestionnaire de fichiers.</p>
        </div>`;
      return;
    }
    container.innerHTML = '';
    conv.messages.forEach((m) => appendMsgDOM(container, m));
    scrollBottom();
  }

  function appendMsgDOM(container, msg) {
    const el = document.createElement('div');
    el.className = 'message ' + msg.role;
    el.id = msg.id || uid();
    msg.id = el.id;
    const meta = `
      <div class="msg-meta">
        <span class="name">${msg.role === 'user' ? 'Vous' : 'BEK'}</span>
        ${msg.model ? `<span class="model-tag">${esc(msg.model)}</span>` : ''}
      </div>`;
    
    let mediaHtml = '';
    if (msg.images && msg.images.length) {
      mediaHtml += '<div style="display:flex;gap:8px;margin-bottom:8px;flex-wrap:wrap;">' +
        msg.images.map(img => `<img src="${img}" style="max-height:160px;border-radius:6px;border:1px solid rgba(255,255,255,0.2)">`).join('') +
        '</div>';
    }
    if (msg.attached_files && msg.attached_files.length) {
      mediaHtml += '<div style="display:flex;gap:6px;margin-bottom:8px;flex-wrap:wrap;">' +
        msg.attached_files.map(f => `<span style="background:#0f172a;padding:4px 8px;border-radius:4px;font-size:11px;border:1px solid #334155;color:#38bdf8;">📎 ${esc(f.name)}</span>`).join('') +
        '</div>';
    }

    el.innerHTML = meta + `<div class="msg-bubble${msg.streaming ? ' streaming' : ''}">${mediaHtml}${renderMarkdown(msg.content)}</div>`;
    container.appendChild(el);
    return el;
  }

  function buildCrossConversationMemory() {
    if (!State.useMemory) return '';
    const otherConvs = State.conversations.filter(c => c.id !== State.currentConvId && c.messages.length > 0);
    if (!otherConvs.length) return '';

    let summary = '### HISTORIQUE DES DISCUSSIONS PRÉCÉDENTES DE L\'UTILISATEUR :\n';
    otherConvs.slice(0, 3).forEach(c => {
      const lastExchange = c.messages.slice(-2).map(m => `${m.role === 'user' ? 'Utilisateur' : 'BEK'}: ${m.content.slice(0, 200)}`).join(' | ');
      summary += `- Sujet "${c.title}" : ${lastExchange}\n`;
    });
    return summary;
  }

  async function sendMessage() {
    const ta = $('#chatInput');
    let text = ta ? ta.value.trim() : '';
    const hasImages = State.pendingImages.length > 0;
    const hasFiles = State.pendingFiles.length > 0;

    if (State.isStreaming) {
      if (State.streamAbort) {
        State.streamAbort.abort();
        State.streamAbort = null;
      }
      setStreaming(false);
      return;
    }

    if (!text && !hasImages && !hasFiles) return;

    let conv = currentConv();
    if (!conv) newConversation();
    conv = currentConv();

    const attachedImages = State.pendingImages.map(img => img.base64);
    const attachedFiles = [...State.pendingFiles];
    State.pendingImages = [];
    State.pendingFiles = [];
    renderPreviews();

    let fullPromptText = text;
    if (attachedFiles.length > 0) {
      attachedFiles.forEach(f => {
        if (f.text) {
          fullPromptText += `\n\n--- Fichier : ${f.name} ---\n${f.text}\n--- Fin du fichier ---\n`;
        } else {
          fullPromptText += `\n\n[Fichier sur serveur : ${f.name}]`;
        }
      });
    }

    const userMsg = {
      id: uid(),
      role: 'user',
      content: text || (hasImages ? 'Image attachée' : 'Fichier attaché'),
      full_content: fullPromptText,
      images: attachedImages,
      attached_files: attachedFiles
    };
    conv.messages.push(userMsg);
    updateConvTitle(conv, text || 'Fichier');
    saveConversations();
    renderConvList();
    renderMessages();

    let reqProvider = $('#providerSelect')?.value || State.selectedProvider || 'groq';
    let reqModel = $('#modelSelect')?.value || State.selectedModel || 'openai/gpt-oss-120b';

    if (attachedImages.length > 0) {
      reqProvider = 'nvidia';
      reqModel = 'meta/llama-3.2-11b-vision-instruct';
    }

    const astMsg = { id: uid(), role: 'assistant', content: '', model: reqModel, streaming: true };
    conv.messages.push(astMsg);
    saveConversations();
    renderMessages();

    if (ta) { ta.value = ''; autoResize(); }
    setStreaming(true);

    const crossMemory = buildCrossConversationMemory();

    const formattedMessages = conv.messages.filter((m) => m.role !== 'assistant' || m.content || m.streaming)
      .map((m, idx) => {
        let msgText = m.full_content || m.content || '';
        if (idx === 0 && crossMemory && m.role === 'user') {
          msgText = `${crossMemory}\n---\n${msgText}`;
        }
        if (m.images && m.images.length) {
          const parts = [{ type: 'text', text: msgText || 'Analyse cette image' }];
          m.images.forEach(img => parts.push({ type: 'image_url', image_url: { url: img } }));
          return { role: m.role, content: parts };
        }
        return { role: m.role, content: msgText };
      });

    try {
      await streamSSE('/api/chat', {
        messages: formattedMessages,
        provider: reqProvider,
        model: reqModel,
        use_memory: State.useMemory,
      }, (chunk) => {
        astMsg.content += chunk;
        updateMsgBubble(astMsg);
      }, (meta) => {
        astMsg.model = meta.model || astMsg.model;
        updateMsgBubble(astMsg);
      }, (err) => {
        astMsg.content += (astMsg.content ? '\n\n' : '') + '**Erreur:** ' + err;
        updateMsgBubble(astMsg);
      });
    } catch (e) {
      astMsg.content = astMsg.content || '**Erreur de connexion:** ' + e.message;
      updateMsgBubble(astMsg);
    }
    astMsg.streaming = false;
    updateMsgBubble(astMsg);
    saveConversations();
    setStreaming(false);
    renderConvList();
    scrollBottom();
  }

  function updateMsgBubble(msg) {
    const el = document.getElementById(msg.id);
    if (!el) return;
    const b = el.querySelector('.msg-bubble');
    if (b) {
      b.className = 'msg-bubble' + (msg.streaming ? ' streaming' : '');
      b.innerHTML = renderMarkdown(msg.content);
      const m = el.querySelector('.msg-meta .model-tag');
      if (m && msg.model) m.textContent = msg.model;
    }
    scrollBottom();
  }

  function setStreaming(on) {
    State.isStreaming = on;
    const btn = $('#sendBtn');
    if (!btn) return;
    btn.innerHTML = on
      ? '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>'
      : '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>';
  }

  function scrollBottom() {
    const c = $('#messages');
    if (c) requestAnimationFrame(() => { c.scrollTop = c.scrollHeight; });
  }

  function syntaxHighlight(rawCode) {
    let safe = esc(rawCode);
    safe = safe.replace(/\b(def|class|return|if|elif|else|for|while|import|from|try|except|raise|with|as|async|await|const|let|var|function)\b/g, '<span style="color:#c678dd;font-weight:bold;">$1</span>');
    safe = safe.replace(/\b(True|False|None|true|false|null|undefined)\b/g, '<span style="color:#d19a66;">$1</span>');
    safe = safe.replace(/(".*?"|'.*?'|`.*?`)/g, '<span style="color:#98c379;">$1</span>');
    safe = safe.replace(/(#.*|\/\/.*)/g, '<span style="color:#5c6370;font-style:italic;">$1</span>');
    return safe;
  }

  function renderMarkdown(src) {
    if (!src) return '';
    let text = src;
    const blocks = [];

    text = text.replace(/```([\w]*)\n?([\s\S]*?)(?:```|$)/g, (m, lang, code) => {
      const id = blocks.length;
      blocks.push({ lang: lang || 'code', code: code });
      return `⟦CB_${id}⟧`;
    });

    let lines = text.split('\n');
    let inList = null;
    let inQuote = false;
    let inTable = false;
    let tableRows = [];
    let html = '';

    function flushTable() {
      if (!inTable) return;
      html += '<div style="overflow-x:auto;margin:12px 0;"><table style="width:100%;border-collapse:collapse;border:1px solid #334155;font-size:13px;color:#e2e8f0;">';
      tableRows.forEach((row, rIdx) => {
        const isHeader = rIdx === 0;
        const tag = isHeader ? 'th' : 'td';
        const bg = isHeader ? 'background:#1e293b;' : (rIdx % 2 === 0 ? 'background:rgba(30,41,59,0.4);' : '');
        html += `<tr style="${bg}">`;
        row.forEach(cell => {
          html += `<${tag} style="border:1px solid #334155;padding:6px 12px;text-align:left;${isHeader ? 'font-weight:600;color:#38bdf8;' : ''}">${inline(cell)}</${tag}>`;
        });
        html += '</tr>';
      });
      html += '</table></div>';
      tableRows = [];
      inTable = false;
    }

    for (let i = 0; i < lines.length; i++) {
      let line = lines[i];
      const trimmed = line.trim();

      if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
        if (inList) { html += '</ul>'; inList = null; }
        if (inQuote) { html += '</blockquote>'; inQuote = false; }
        if (trimmed.includes('---')) continue;
        const cells = trimmed.split('|').slice(1, -1).map(c => c.trim());
        tableRows.push(cells);
        inTable = true;
        continue;
      } else if (inTable) {
        flushTable();
      }

      if (trimmed === '') {
        if (inList) { html += '</ul>'; inList = null; }
        if (inQuote) { html += '</blockquote>'; inQuote = false; }
        html += '<br>';
        continue;
      }
      if (trimmed === '---' || trimmed === '***' || trimmed === '___') {
        if (inList) { html += '</ul>'; inList = null; }
        html += '<hr style="border:none;border-top:1px solid #334155;margin:16px 0;">';
        continue;
      }

      const codeMatch = trimmed.match(/^⟦CB_(\d+)⟧$/);
      if (codeMatch) {
        if (inList) { html += '</ul>'; inList = null; }
        if (inQuote) { html += '</blockquote>'; inQuote = false; }
        const b = blocks[parseInt(codeMatch[1])];
        
        html += `
          <div style="background:#13161c; border-radius:14px; margin:14px 0; border: 1px solid rgba(255,255,255,0.08); overflow:hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.35);">
            <div style="display:flex; justify-content:space-between; align-items:center; padding:10px 16px 6px 16px; background:#13161c; border-bottom:1px solid rgba(255,255,255,0.05);">
              <span style="color:#e2e8f0; font-size:12px; font-weight:500;">${esc(formatLangName(b.lang))}</span>
              <div style="display:flex; gap:8px; align-items:center;">
                <button onclick="window.BEK_CODE.dl(this, '${escAttr(b.lang)}')" data-code="${escAttr(b.code)}" style="background:transparent; border:none; cursor:pointer; color:#94a3b8; padding:4px; border-radius:4px;" title="Télécharger le fichier">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="8 12 12 16 16 12"/><line x1="12" y1="8" x2="12" y2="16"/></svg>
                </button>
                <button onclick="window.BEK_CODE.cp(this)" data-code="${escAttr(b.code)}" style="background:transparent; border:none; cursor:pointer; color:#94a3b8; padding:4px; border-radius:4px;" title="Copier le code">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                </button>
              </div>
            </div>
            <div style="padding:12px 16px 14px 16px; overflow-x:auto; font-family:'Consolas', 'Monaco', 'Courier New', monospace; font-size:13px; line-height:1.55; color:#e2e8f0;">
              <pre style="margin:0; background:transparent;"><code>${syntaxHighlight(b.code)}</code></pre>
            </div>
          </div>
        `;
        continue;
      }

      const h = trimmed.match(/^(#{1,4})\s+(.*)/);
      if (h) {
        if (inList) { html += '</ul>'; inList = null; }
        html += `<h${h[1].length} style="color:#f8fafc;margin:12px 0 6px 0;">${inline(h[2])}</h${h[1].length}>`;
        continue;
      }

      if (trimmed.startsWith('>')) {
        if (!inQuote) { html += '<blockquote style="border-left:3px solid #6366f1;padding-left:12px;margin:8px 0;color:#cbd5e1;">'; inQuote = true; }
        html += inline(trimmed.replace(/^>\s?/, '')) + '<br>';
        continue;
      }

      const li = trimmed.match(/^([-*•+]|\d+[.)])\s+(.*)/);
      if (li) {
        if (!inList) { html += '<ul style="margin:6px 0;padding-left:20px;">'; inList = 'ul'; }
        html += `<li>${inline(li[2])}</li>`;
        continue;
      } else if (inList) {
        html += '</ul>';
        inList = null;
      }

      html += `<p style="margin:6px 0;">${inline(trimmed)}</p>`;
    }
    if (inTable) flushTable();
    if (inList) html += '</ul>';
    if (inQuote) html += '</blockquote>';

    return html;
  }

  function inline(t) {
    return esc(t)
      .replace(/\*\*([^*]+)\*\*/g, '<strong style="color:#f8fafc;">$1</strong>')
      .replace(/\*([^*]+)\*/g, '<em>$1</em>')
      .replace(/`([^`]+)`/g, '<code style="background:rgba(255,255,255,0.1);padding:2px 4px;border-radius:4px;color:#38bdf8;font-family:monospace;">$1</code>')
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener" style="color:#38bdf8;text-decoration:underline;">$1</a>');
  }

  window.BEK_CODE = {
    cp: function(btn) {
      const code = btn.getAttribute('data-code');
      navigator.clipboard.writeText(code).then(() => {
        const originalHTML = btn.innerHTML;
        btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
        toast('Code copié !');
        setTimeout(() => { btn.innerHTML = originalHTML; }, 2000);
      });
    },
    dl: function(btn, lang) {
      const code = btn.getAttribute('data-code');
      const blob = new Blob([code], { type: 'text/plain;charset=utf-8' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      
      let ext = 'txt';
      const l = String(lang).toLowerCase();
      if (l.includes('py') || l.includes('python')) ext = 'py';
      else if (l.includes('js') || l.includes('javascript')) ext = 'js';
      else if (l.includes('ts') || l.includes('typescript')) ext = 'ts';
      else if (l.includes('html')) ext = 'html';
      else if (l.includes('css')) ext = 'css';
      else if (l.includes('json')) ext = 'json';
      else if (l.includes('sh') || l.includes('bash')) ext = 'sh';
      else if (l.includes('sql')) ext = 'sql';
      else if (l.includes('cpp') || l.includes('c++')) ext = 'cpp';
      else if (l.includes('c')) ext = 'c';
      
      a.download = `code_${Date.now()}.${ext}`;
      a.click();
      toast(`Fichier .${ext} téléchargé !`);
    }
  };

  async function streamSSE(url, body, onChunk, onMeta, onError) {
    State.streamAbort = new AbortController();
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: State.streamAbort.signal,
    });
    if (!res.ok) {
      const t = await res.text();
      throw new Error(t.slice(0, 200));
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let closed = false;
    while (!closed) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buffer.indexOf('\n\n')) !== -1) {
        const raw = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        for (const line of raw.split('\n')) {
          if (!line.startsWith('data: ')) continue;
          try {
            const d = JSON.parse(line.slice(6));
            if (d.chunk) onChunk(d.chunk);
            else if (d.meta) onMeta && onMeta(d.meta);
            else if (d.error) onError && onError(d.error);
            else if (d.done) closed = true;
          } catch (e) {}
        }
      }
    }
  }

  // ─── VUE COMPÉTENCES (SKILLS) ───
  async function renderSkills() {
    const view = $('#viewSkills');
    if (!view) return;
    view.innerHTML = `
      <div class="view-header" style="display:flex;justify-content:space-between;align-items:center;padding:20px 24px;border-bottom:1px solid #334155;">
        <div>
          <h2 style="margin:0;font-size:20px;color:#f8fafc;">Compétences (Skills)</h2>
          <p style="margin:4px 0 0;font-size:13px;color:#94a3b8;">Modules réutilisables exécutables par l'agent</p>
        </div>
        <button class="btn btn-primary" id="newSkillBtn" style="background:#4f46e5;color:#fff;border:none;padding:8px 16px;border-radius:8px;cursor:pointer;font-size:13px;">+ Nouveau skill</button>
      </div>
      <div class="view-body" style="padding:24px;overflow-y:auto;height:calc(100vh - 100px);" id="skillsBody">
        <div style="color:#94a3b8;">Chargement des compétences...</div>
      </div>`;

    try {
      const d = await api('/api/skills');
      State.skills = d.skills || [];
      const body = $('#skillsBody');
      if (!body) return;
      if (!State.skills.length) {
        body.innerHTML = '<div style="text-align:center;padding:40px;color:#94a3b8;"><div style="font-size:32px;margin-bottom:8px;">🧠</div><h3>Aucune compétence enregistrée</h3><p>Créez votre première compétence pour automatiser vos tâches.</p></div>';
      } else {
        body.innerHTML = `
          <div style="display:grid;grid-template-columns:repeat(auto-fill, minmax(280px, 1fr));gap:16px;">
            ${State.skills.map(s => `
              <div style="background:#1e293b;border:1px solid #334155;border-radius:12px;padding:16px;display:flex;flex-direction:column;justify-content:space-between;">
                <div>
                  <h4 style="margin:0 0 6px 0;color:#f8fafc;font-size:15px;">${esc(s.name)}</h4>
                  <p style="margin:0 0 12px 0;font-size:12.5px;color:#94a3b8;line-height:1.4;">${esc(s.description || 'Sans description')}</p>
                </div>
                <div style="display:flex;justify-content:space-between;align-items:center;border-top:1px solid #334155;padding-top:12px;margin-top:12px;">
                  <span style="font-size:11px;color:#38bdf8;font-family:monospace;">/${esc(s.command || s.name)}</span>
                  <button data-del-skill="${esc(s.name)}" style="background:transparent;border:none;color:#ef4444;cursor:pointer;font-size:12px;">Supprimer</button>
                </div>
              </div>
            `).join('')}
          </div>`;
        
        body.querySelectorAll('[data-del-skill]').forEach(btn => {
          btn.addEventListener('click', async () => {
            if (confirm(`Supprimer la compétence ${btn.dataset.delSkill} ?`)) {
              await api(`/api/skills/${btn.dataset.delSkill}`, { method: 'DELETE' });
              renderSkills();
            }
          });
        });
      }
    } catch (e) {
      $('#skillsBody').innerHTML = `<div style="color:#ef4444;">Erreur : ${e.message}</div>`;
    }

    $('#newSkillBtn')?.addEventListener('click', openSkillCreateModal);
  }

  function openSkillCreateModal() {
    openModal('Nouvelle Compétence', `
      <div style="margin-bottom:12px;">
        <label style="display:block;font-size:12px;color:#94a3b8;margin-bottom:4px;">Nom de la compétence</label>
        <input class="form-input" id="skName" placeholder="analyseur-code" style="width:100%;padding:8px 12px;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#f8fafc;">
      </div>
      <div style="margin-bottom:12px;">
        <label style="display:block;font-size:12px;color:#94a3b8;margin-bottom:4px;">Description</label>
        <input class="form-input" id="skDesc" placeholder="Analyse et optimise les scripts Python" style="width:100%;padding:8px 12px;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#f8fafc;">
      </div>
      <div style="margin-bottom:12px;">
        <label style="display:block;font-size:12px;color:#94a3b8;margin-bottom:4px;">Instruction Prompt</label>
        <textarea class="form-input" id="skPrompt" rows="4" placeholder="Tu es un expert... Analyse le code suivant : {input}" style="width:100%;padding:8px 12px;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#f8fafc;"></textarea>
      </div>`,
      `<button class="btn btn-secondary" onclick="BEK.closeModal()" style="background:#334155;color:#fff;border:none;padding:8px 16px;border-radius:6px;cursor:pointer;">Annuler</button>
       <button class="btn btn-primary" id="saveSkillBtn" style="background:#4f46e5;color:#fff;border:none;padding:8px 16px;border-radius:6px;cursor:pointer;">Créer</button>`);

    $('#saveSkillBtn')?.addEventListener('click', async () => {
      const name = $('#skName').value.trim();
      const desc = $('#skDesc').value.trim();
      const prompt = $('#skPrompt').value.trim();
      if (!name || !prompt) return toast('Nom et Prompt obligatoires', 'err');

      try {
        await api('/api/skills', { method: 'POST', body: { name, description: desc, prompt, command: name } });
        closeModal();
        renderSkills();
        toast('Compétence ajoutée');
      } catch (e) { toast(e.message, 'err'); }
    });
  }

  // ─── VUE FICHIERS (FILES) ───
  async function renderFiles() {
    const view = $('#viewFiles');
    if (!view) return;
    view.innerHTML = `
      <div class="view-header" style="padding:20px 24px;border-bottom:1px solid #334155;">
        <h2 style="margin:0;font-size:20px;color:#f8fafc;">Fichiers & Documents</h2>
        <p style="margin:4px 0 0;font-size:13px;color:#94a3b8;">Fichiers générés par l'IA et documents téléversés</p>
      </div>
      <div class="view-body" style="padding:24px;overflow-y:auto;height:calc(100vh - 100px);" id="filesBody">
        <div style="color:#94a3b8;">Chargement des fichiers...</div>
      </div>`;

    try {
      const d = await api('/api/files');
      State.files = d.files || [];
      const body = $('#filesBody');
      if (!body) return;
      if (!State.files.length) {
        body.innerHTML = '<div style="text-align:center;padding:40px;color:#94a3b8;"><div style="font-size:32px;margin-bottom:8px;">📁</div><h3>Aucun fichier disponible</h3><p>Téléversez des documents ou demandez à l\'IA d\'en générer.</p></div>';
      } else {
        body.innerHTML = `
          <div style="display:flex;flex-direction:column;gap:10px;">
            ${State.files.map(f => {
              const ext = (f.filename.split('.').pop() || 'file').toUpperCase();
              return `
              <div style="background:#1e293b;border:1px solid #334155;border-radius:10px;padding:12px 18px;display:flex;justify-content:space-between;align-items:center;">
                <div style="display:flex;align-items:center;gap:12px;">
                  <span style="background:#0f172a;padding:6px 10px;border-radius:6px;color:#38bdf8;font-weight:bold;font-size:12px;">${esc(ext)}</span>
                  <div>
                    <div style="color:#f8fafc;font-size:14px;font-weight:500;">${esc(f.filename)}</div>
                    <div style="font-size:11px;color:#94a3b8;">${fmtSize(f.size)} • ${new Date(f.created_at).toLocaleString()}</div>
                  </div>
                </div>
                <a href="/api/files/${esc(f.filename)}" download class="btn btn-secondary" style="background:#334155;color:#f8fafc;text-decoration:none;padding:6px 12px;border-radius:6px;font-size:12px;">⬇ Télécharger</a>
              </div>`;
            }).join('')}
          </div>`;
      }
    } catch (e) {
      $('#filesBody').innerHTML = `<div style="color:#ef4444;">Erreur : ${e.message}</div>`;
    }
  }

  // ─── VUE MÉMOIRE (MEMORY) ───
  async function renderMemory() {
    const view = $('#viewMemory');
    if (!view) return;
    view.innerHTML = `
      <div class="view-header" style="padding:20px 24px;border-bottom:1px solid #334155;">
        <h2 style="margin:0;font-size:20px;color:#f8fafc;">Mémoire Vectorielle</h2>
        <p style="margin:4px 0 0;font-size:13px;color:#94a3b8;">Persistance des connaissances inter-conversations</p>
      </div>
      <div class="view-body" style="padding:24px;overflow-y:auto;height:calc(100vh - 100px);">
        <div style="display:flex;gap:12px;margin-bottom:20px;">
          <input id="memSearchInput" placeholder="Rechercher une information en mémoire..." style="flex:1;padding:10px 14px;background:#1e293b;border:1px solid #334155;border-radius:8px;color:#f8fafc;">
          <button id="memSearchBtn" style="background:#4f46e5;color:#fff;border:none;padding:0 20px;border-radius:8px;cursor:pointer;">Rechercher</button>
        </div>
        <div id="memResults" style="color:#94a3b8;">Statut : Mémoire vectorielle prête (Pinecone / Local).</div>
      </div>`;

    $('#memSearchBtn')?.addEventListener('click', async () => {
      const q = $('#memSearchInput').value.trim();
      if (!q) return;
      $('#memResults').innerHTML = '<div style="color:#38bdf8;">Recherche en cours...</div>';
      try {
        const res = await api('/api/memory/search', { method: 'POST', body: { query: q } });
        if (!res.results || !res.results.length) {
          $('#memResults').innerHTML = '<div>Aucune mémoire correspondante trouvée.</div>';
        } else {
          $('#memResults').innerHTML = res.results.map(r => `
            <div style="background:#1e293b;border:1px solid #334155;border-radius:8px;padding:12px;margin-bottom:10px;color:#f8fafc;">
              ${esc(r.text)}
            </div>
          `).join('');
        }
      } catch (e) {
        $('#memResults').innerHTML = `<div style="color:#ef4444;">Erreur : ${e.message}</div>`;
      }
    });
  }

  // ─── VUE PLUGINS ───
  async function renderPlugins() {
    const view = $('#viewPlugins');
    if (!view) return;
    view.innerHTML = `
      <div class="view-header" style="padding:20px 24px;border-bottom:1px solid #334155;">
        <h2 style="margin:0;font-size:20px;color:#f8fafc;">Plugins Actifs</h2>
        <p style="margin:4px 0 0;font-size:13px;color:#94a3b8;">Extensions Python chargées depuis le dossier <code>plugins/</code></p>
      </div>
      <div class="view-body" style="padding:24px;overflow-y:auto;height:calc(100vh - 100px);" id="pluginsBody">
        <div style="color:#94a3b8;">Chargement des plugins...</div>
      </div>`;

    try {
      const d = await api('/api/plugins');
      const plugins = d.plugins || [];
      const body = $('#pluginsBody');
      if (!body) return;
      if (!plugins.length) {
        body.innerHTML = '<div style="text-align:center;padding:40px;color:#94a3b8;"><div style="font-size:32px;margin-bottom:8px;">🔌</div><h3>Aucun plugin actif</h3><p>Déposez des scripts Python dans <code>plugins/</code> pour étendre l\'agent.</p></div>';
      } else {
        body.innerHTML = plugins.map(p => `
          <div style="background:#1e293b;border:1px solid #334155;border-radius:10px;padding:14px;margin-bottom:10px;display:flex;justify-content:space-between;align-items:center;">
            <div>
              <div style="color:#f8fafc;font-weight:600;">🔌 ${esc(p.name)}</div>
              <div style="font-size:12px;color:#94a3b8;">Fichier : ${esc(p.file)}</div>
            </div>
            <span style="background:#0f172a;padding:4px 8px;border-radius:4px;color:#10b981;font-size:11px;border:1px solid #334155;">Actif</span>
          </div>
        `).join('');
      }
    } catch (e) {
      $('#pluginsBody').innerHTML = `<div style="color:#ef4444;">Erreur : ${e.message}</div>`;
    }
  }

  // ─── VUE CONNECTEURS API ───
  async function renderConnectors() {
    const view = $('#viewConnectors');
    if (!view) return;
    view.innerHTML = `
      <div class="view-header" style="display:flex;justify-content:space-between;align-items:center;padding:20px 24px;border-bottom:1px solid #334155;">
        <div>
          <h2 style="margin:0;font-size:20px;color:#f8fafc;">Connecteurs API</h2>
          <p style="margin:4px 0 0;font-size:13px;color:#94a3b8;">Connexions vers des API, Webhooks et services tiers</p>
        </div>
        <button class="btn btn-primary" id="newConnBtn" style="background:#4f46e5;color:#fff;border:none;padding:8px 16px;border-radius:8px;cursor:pointer;font-size:13px;font-weight:500;">+ Ajouter un connecteur</button>
      </div>
      <div class="view-body" style="padding:24px;overflow-y:auto;height:calc(100vh - 100px);" id="connectorsBody">
        <div style="color:#94a3b8;">Chargement des connecteurs...</div>
      </div>`;

    try {
      const d = await api('/api/connectors');
      State.connectors = d.connectors || [];
      const body = $('#connectorsBody');
      if (!body) return;
      if (!State.connectors.length) {
        body.innerHTML = `
          <div style="text-align:center;padding:60px 20px;color:#94a3b8;">
            <div style="font-size:36px;margin-bottom:10px;">🔗</div>
            <h3 style="color:#f8fafc;font-size:16px;margin:0 0 6px 0;">Aucun connecteur configuré</h3>
            <p style="font-size:13px;margin:0;">Ajoutez des webhooks ou API REST pour enrichir votre agent.</p>
          </div>`;
      } else {
        body.innerHTML = `
          <div style="display:grid;grid-template-columns:repeat(auto-fill, minmax(320px, 1fr));gap:16px;">
            ${State.connectors.map(c => `
              <div style="background:#1e293b;border:1px solid #334155;border-radius:12px;padding:16px;display:flex;flex-direction:column;justify-content:space-between;">
                <div>
                  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                    <h4 style="margin:0;color:#f8fafc;font-size:15px;font-weight:600;">🔗 ${esc(c.name)}</h4>
                    <span style="background:#0f172a;padding:2px 8px;border-radius:4px;color:#38bdf8;font-size:11px;font-family:monospace;">${esc(c.command || '/' + c.name)}</span>
                  </div>
                  <p style="margin:0 0 8px 0;font-size:12px;color:#94a3b8;word-break:break-all;"><strong>URL:</strong> ${esc(c.base_url || c.url)}</p>
                  <span style="font-size:11px;color:${c.api_key ? '#10b981' : '#64748b'};">${c.api_key ? '● Clé API configurée' : '○ Sans authentification'}</span>
                </div>
                <div style="display:flex;justify-content:flex-end;border-top:1px solid #334155;padding-top:12px;margin-top:12px;">
                  <button data-del-conn="${esc(c.name)}" style="background:transparent;border:none;color:#ef4444;cursor:pointer;font-size:12px;padding:4px 8px;">Supprimer</button>
                </div>
              </div>
            `).join('')}
          </div>`;

        body.querySelectorAll('[data-del-conn]').forEach(btn => {
          btn.addEventListener('click', async () => {
            if (confirm(`Supprimer le connecteur "${btn.dataset.delConn}" ?`)) {
              await api(`/api/connectors/${encodeURIComponent(btn.dataset.delConn)}`, { method: 'DELETE' });
              toast('Connecteur supprimé');
              renderConnectors();
            }
          });
        });
      }
    } catch (e) {
      $('#connectorsBody').innerHTML = `<div style="color:#ef4444;">Erreur : ${e.message}</div>`;
    }

    $('#newConnBtn')?.addEventListener('click', openConnectorModal);
  }

  function openConnectorModal() {
    openModal('Nouveau Connecteur API', `
      <div style="margin-bottom:12px;">
        <label style="display:block;font-size:12px;color:#94a3b8;margin-bottom:4px;">Nom du service</label>
        <input class="form-input" id="cnName" placeholder="ex: meteo-api ou crm-sync" style="width:100%;padding:8px 12px;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#f8fafc;">
      </div>
      <div style="margin-bottom:12px;">
        <label style="display:block;font-size:12px;color:#94a3b8;margin-bottom:4px;">URL du point de terminaison (Endpoint)</label>
        <input class="form-input" id="cnUrl" placeholder="https://api.monservice.com/v1/data" style="width:100%;padding:8px 12px;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#f8fafc;">
      </div>
      <div style="margin-bottom:12px;">
        <label style="display:block;font-size:12px;color:#94a3b8;margin-bottom:4px;">Commande dans le chat</label>
        <input class="form-input" id="cnCmd" placeholder="/meteo" style="width:100%;padding:8px 12px;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#f8fafc;">
      </div>
      <div style="margin-bottom:12px;">
        <label style="display:block;font-size:12px;color:#94a3b8;margin-bottom:4px;">Clé API ou Token Bearer (Optionnel)</label>
        <input class="form-input" id="cnKey" type="password" placeholder="sk-..." style="width:100%;padding:8px 12px;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#f8fafc;">
      </div>`,
      `<button class="btn btn-secondary" onclick="BEK.closeModal()" style="background:#334155;color:#fff;border:none;padding:8px 16px;border-radius:6px;cursor:pointer;">Annuler</button>
       <button class="btn btn-primary" id="saveConnBtn" style="background:#4f46e5;color:#fff;border:none;padding:8px 16px;border-radius:6px;cursor:pointer;font-weight:500;">Enregistrer</button>`);

    $('#saveConnBtn')?.addEventListener('click', async () => {
      const name = $('#cnName').value.trim();
      const url = $('#cnUrl').value.trim();
      const command = $('#cnCmd').value.trim() || `/${name}`;
      const apiKey = $('#cnKey').value.trim();

      if (!name || !url) {
        toast('Nom et URL requis', 'err');
        return;
      }

      try {
        await api('/api/connectors', {
          method: 'POST',
          body: { name, base_url: url, command, api_key: apiKey, method: 'GET' }
        });
        closeModal();
        renderConnectors();
        toast('Connecteur configuré avec succès !');
      } catch (e) {
        toast(e.message, 'err');
      }
    });
  }

  function openModal(title, bodyHTML, footHTML, lg) {
    let root = $('#modalRoot');
    if (!root) {
      root = document.createElement('div');
      root.id = 'modalRoot';
      document.body.appendChild(root);
    }
    root.innerHTML = `
      <div class="modal-overlay" id="overlay" style="position:fixed;inset:0;background:rgba(0,0,0,0.7);z-index:999999;display:flex;align-items:center;justify-content:center;">
        <div class="modal ${lg ? 'modal-lg' : ''}" style="background:#1e293b;border:1px solid #334155;border-radius:14px;max-width:550px;width:90%;padding:24px;color:#f8fafc;box-shadow:0 20px 45px rgba(0,0,0,0.7);">
          <div class="modal-head" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
            <h3 style="margin:0;font-size:17px;font-weight:600;">${esc(title)}</h3>
            <button class="modal-close" id="modalX" style="background:transparent;border:none;color:#94a3b8;font-size:18px;cursor:pointer;">✕</button>
          </div>
          <div class="modal-body">${bodyHTML}</div>
          ${footHTML ? `<div class="modal-foot" style="margin-top:20px;display:flex;justify-content:flex-end;gap:10px;">${footHTML}</div>` : ''}
        </div>
      </div>`;
    $('#modalX')?.addEventListener('click', closeModal);
    $('#overlay')?.addEventListener('mousedown', (e) => { if (e.target.id === 'overlay') closeModal(); });
  }
  function closeModal() {
    const root = $('#modalRoot');
    if (root) root.innerHTML = '';
  }

  async function openSettingsModal() {
    let keysStatus = {};
    try { keysStatus = await api('/api/keys'); } catch (e) {}
    const prov = State.providers.length ? State.providers : (State.config?.providers || []);

    openModal('Paramètres — Clés API', `
      <div style="font-size:12px;color:var(--text-dim);margin-bottom:14px">
        Vos clés API sont sauvegardées dans <code>env.txt</code>.
      </div>
      ${prov.map((p) => `
        <div class="key-row" style="margin-bottom:12px;">
          <label style="display:block;font-size:12px;color:#94a3b8;margin-bottom:4px;">${esc(p.name)}</label>
          <input class="form-input" type="password" id="key_${esc(p.id)}" placeholder="sk-..." autocomplete="off" style="width:100%;padding:8px 12px;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#f8fafc;">
        </div>`).join('')}
      <div class="form-group" style="margin-top:14px">
        <label style="display:block;font-size:12px;color:#94a3b8;margin-bottom:4px;">Rafraîchir les modèles</label>
        <div style="display:flex;gap:8px">
          <select class="form-input" id="fetchProv" style="flex:1;padding:8px;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#f8fafc;">
            ${prov.map((p) => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('')}
          </select>
          <button class="btn btn-secondary" id="fetchModelsBtn" style="background:#334155;color:#f8fafc;border:none;padding:8px 16px;border-radius:6px;cursor:pointer;">⟳ Charger</button>
        </div>
      </div>`,
      `<button class="btn btn-secondary" onclick="BEK.closeModal()" style="background:#334155;color:#f8fafc;border:none;padding:8px 16px;border-radius:6px;cursor:pointer;">Fermer</button>
       <button class="btn btn-primary" id="keysSaveBtn" style="background:#4f46e5;color:#fff;border:none;padding:8px 16px;border-radius:6px;cursor:pointer;">Enregistrer</button>`, true);

    $('#keysSaveBtn')?.addEventListener('click', async () => {
      const keyMappings = { "groq": "GROQ_API_KEY", "nvidia": "NVIDIA_API_KEY" };
      let saved = 0;
      for (const id of Object.keys(keyMappings)) {
        const input = $('#key_' + id);
        if (!input) continue;
        const v = input.value.trim();
        if (!v) continue;
        try {
          await api('/api/keys', { method: 'POST', body: { key_name: keyMappings[id], key_value: v } });
          saved++;
        } catch (e) {}
      }
      if (saved) { toast(saved + ' clé(s) enregistrée(s)'); closeModal(); await loadConfig(); refreshStatus(); }
    });

    $('#fetchModelsBtn')?.addEventListener('click', async () => {
      try {
        const d = await api('/api/models/fetch', { method: 'POST', body: { provider: $('#fetchProv').value } });
        toast(d.models.length + ' modèles récupérés (' + d.provider + ')');
        State.models = await (await fetch('/api/config')).json().then((c) => c.models);
        updateProviderSelect();
      } catch (e) { toast(e.message, 'err'); }
    });
  }

  window.BEK = { State, closeModal, switchTab, sendMessage, openSettingsModal, toggleGeminiMenu };
})();