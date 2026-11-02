// ==============================================================================
// BEK-v18 — UI : Markdown & Mermaid
// ==============================================================================

export function isVideoUrl(url) {
    if (!url) return false;
    return /\.(mp4|webm|mov|avi|mkv|ogv|m4v)(\?.*)?$/i.test(url);
}

export function isAudioUrl(url) {
    if (!url) return false;
    return /\.(mp3|wav|ogg|flac|m4a|aac)(\?.*)?$/i.test(url);
}

export function isImageUrl(url) {
    if (!url) return false;
    return /\.(png|jpg|jpeg|gif|webp|bmp|svg)(\?.*)?$/i.test(url);
}

export function sanitizeMermaid(code) {
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

export function initMermaid() {
    if (!window.mermaid) return;
    if (window.__mermaidReady) return;
    try {
        window.mermaid.initialize({
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
    } catch (e) {
        console.error('[Mermaid] init failed:', e);
    }
}

export function renderMermaidIn(container) {
    if (!container || !window.mermaid) return;
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
            const result = window.mermaid.run({ nodes: [target] });
            if (result && typeof result.catch === 'function') {
                result.catch(err => {
                    wrapper.innerHTML = '<div style="color:#ff6b6b; padding:12px; font-size:12px;">⚠️ Mermaid : erreur</div><pre style="background:#1a1f26; padding:12px; border-radius:6px; font-size:11px; overflow-x:auto;"><code>' + escapeHtml(graph) + '</code></pre>';
                });
            }
        } catch (e) {}
    });
}

export function escapeHtml(text) {
    if (text === null || text === undefined) return "";
    return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

export function formatMarkdown(text) {
    let cleanText = text.replace(/<think>[\s\S]*?(?:<\/think>|$)/gi, '');

    cleanText = cleanText.replace(/\[FILE:(.*?)\]\((.*?)\)/g, (match, filename, url) => {
        return `<div class="file-attachment-card"><div class="file-attachment-icon">📄</div><div class="file-attachment-info"><div class="file-attachment-name">${filename}</div><div class="file-attachment-desc">Fichier généré prêt au téléchargement</div></div><a href="${url}" target="_blank" download class="file-attachment-btn">Télécharger</a></div>`;
    });

    if (typeof window.marked !== 'undefined') {
        const renderer = new window.marked.Renderer();

        renderer.image = function(hrefOrToken, title, text) {
            let url = "";
            let cleanTitle = "";
            let cleanAlt = "";

            if (typeof hrefOrToken === 'object' && hrefOrToken !== null) {
                url = hrefOrToken.href || '';
                cleanTitle = hrefOrToken.title || '';
                cleanAlt = String(hrefOrToken.text || '').replace(/"/g, '&quot;');
            } else {
                url = hrefOrToken || '';
                cleanTitle = title || '';
                cleanAlt = String(text || '').replace(/"/g, '&quot;');
            }

            url = String(url).trim();

            if (!url || url === '[object Object]' || url.startsWith('[object')) {
                return '<div style="color:#f5a623;padding:8px 12px;border:1px solid rgba(245,166,35,0.3);border-radius:8px;font-size:12px;background:rgba(245,166,35,0.08);">🖼️ Image (URL manquante)</div>';
            }

            if (isVideoUrl(url)) {
                return `<video controls loop muted playsinline preload="metadata" src="${url}" title="${cleanTitle}"></video>`;
            }

            if (isAudioUrl(url)) {
                return `<audio controls preload="metadata" src="${url}" title="${cleanTitle}"></audio>`;
            }

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
                return `<pre><code class="language-mermaid">${escapeHtml(sanitizeMermaid(actualCode))}</code></pre>`;
            }

            const snippetId = 'snip_' + Math.random().toString(36).substring(2, 9);
            window.__codeSnippetsRegistry[snippetId] = { code: actualCode, lang: cleanLang };

            let highlightedCode = escapeHtml(actualCode);
            if (typeof window.hljs !== 'undefined') {
                try {
                    if (cleanLang && window.hljs.getLanguage(cleanLang)) {
                        highlightedCode = window.hljs.highlight(actualCode, { language: cleanLang }).value;
                    } else {
                        highlightedCode = window.hljs.highlightAuto(actualCode).value;
                    }
                } catch (e) { highlightedCode = escapeHtml(actualCode); }
            }

            return `
            <div class="code-container">
                <div class="code-header">
                    <span class="code-lang-name">${cleanLang.toUpperCase()}</span>
                    <div class="code-actions-group">
                        <button class="code-action-btn" title="Télécharger" onclick="window.downloadCodeSnippet('${snippetId}')">Télécharger</button>
                        <button class="code-action-btn" title="Copier" onclick="window.copyCodeSnippet('${snippetId}', this)">Copier</button>
                    </div>
                </div>
                <pre><code class="hljs language-${cleanLang}">${highlightedCode}</code></pre>
            </div>`;
        };
        try {
            return window.marked.parse(cleanText, { renderer: renderer, gfm: true, breaks: true });
        } catch (e) {
            return escapeHtml(cleanText).replace(/\n/g, '<br>');
        }
    }
    return escapeHtml(cleanText).replace(/\n/g, '<br>');
}