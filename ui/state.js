// ==============================================================================
// BEK-v18 — UI : State
// ==============================================================================

export const API_BASE = window.location.origin;

export const DOM = {
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
    lightboxImg: document.getElementById('lightboxImg'),
    brainToggleBtn: document.getElementById('brainToggleBtn') // ★ NOUVEAU
};

export const state = {
    currentProvider: 'kimi',
    currentModel: 'kimi-k3',
    availableModels: {},
    messageHistory: [],
    conversations: [],
    currentConvId: null,
    isStreaming: false,
    attachedFiles: [],
    pendingUploads: {},
    activeController: null,
    globalSkills: [],
    reflexFilter: 'staging',
    reflexProposals: [],
    isBrainMode: false // ★ NOUVEAU
};

window.__codeSnippetsRegistry = window.__codeSnippetsRegistry || {};