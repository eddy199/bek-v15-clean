// ==============================================================================
// BEK-v18 — UI : State
// ★ FIX : valeurs par défaut alignées avec loadConfig() (nvidia) + flag configReady
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
    brainToggleBtn: document.getElementById('brainToggleBtn')
};

export const state = {
    // ★ FIX : défauts alignés avec loadConfig() qui force nvidia au boot.
    //   Comme ça, si loadConfig() échoue ou est lent, l'UI et l'état restent cohérents.
    currentProvider: 'nvidia',
    currentModel: 'nvidia/nemotron-3.5-super-vl-120b-a12b',
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
    isBrainMode: false,
    // ★ NOUVEAU : indique si /api/config a été chargé avec succès.
    //   sendMessage() peut refuser d'envoyer si false (évite d'envoyer avec un modèle non confirmé).
    configReady: false
};

window.__codeSnippetsRegistry = window.__codeSnippetsRegistry || {};