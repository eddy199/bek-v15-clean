<div align="center">
  <img src="./assets/logo.png" alt="BEK Hybrid Logo" width="250"/>
  <h1>🧠 BEK Hybrid Agent v19</h1>
  <p><strong>L'écosystème d'IA agentique souverain, économe en tokens et sans hallucination.</strong></p>
  <p>Créé par <strong>BEKKARA Mohamed</strong> - Oran, Algérie.</p>
  <p><img src="https://img.shields.io/badge/License-AGPL%20v3-blue.svg?style=for-the-badge" alt="License" /><img src="https://img.shields.io/badge/Python-3.12+-3776AB.svg?style=for-the-badge" alt="Python" /><img src="https://img.shields.io/badge/FastAPI-005571.svg?style=for-the-badge" alt="FastAPI" /><img src="https://img.shields.io/badge/Brevets-16%20D%C3%A9pos%C3%A9s-critical?style=for-the-badge" alt="Brevets" /><img src="https://img.shields.io/badge/S%C3%A9curit%C3%A9-Token%20Guard-red?style=for-the-badge" alt="Security" /></p>
  <p><img src="https://img.shields.io/badge/BEK--CPU-Logique%20Virtuel-purple?style=for-the-badge" /><img src="https://img.shields.io/badge/BEK--LVC-10x%20%C3%89conomie-orange?style=for-the-badge" /><img src="https://img.shields.io/badge/Nerves-12-success?style=for-the-badge" /><img src="https://img.shields.io/badge/Hermes-62-blueviolet?style=for-the-badge" /></p>
  <p><img src="https://img.shields.io/badge/Skills-329-brightgreen?style=for-the-badge" /><img src="https://img.shields.io/badge/Alter--Egos-6-9cf?style=for-the-badge" /><img src="https://img.shields.io/badge/Vision-Multim%C3%A9dia-informational?style=for-the-badge" /><img src="https://img.shields.io/badge/Vid%C3%A9o-Agnes-yellow?style=for-the-badge" /></p>
</div>

---

## 📸 Aperçu de l'Interface

| 💬 Chat & Raisonnement | 🧠 329 Compétences Actives |
| :---: | :---: |
| <img src="assets/chat.png" width="400"/> | <img src="assets/skills.png" width="400"/> |

| 🗄️ Mémoire Vectorielle | 🔌 Connecteurs Système |
| :---: | :---: |
| <img src="assets/memory.png" width="400"/> | <img src="assets/connectors.png" width="400"/> |

| 🤖 Fournisseurs d'IA | 🎨 Génération d'Images |
| :---: | :---: |
| <img src="assets/providers.png" width="400"/> | <img src="assets/generation.png" width="400"/> |

| 🔁 Reflex Loop | 📁 Gestion de Fichiers |
| :---: | :---: |
| <img src="assets/reflex.png" width="400"/> | <img src="assets/files.png" width="400"/> |

---

## 🚀 Qu'''est-ce que BEK ?

**BEK** est un **agent autonome multi-fonction** qui unifie :
- 🧠 **6 briques cognitives** et **12 modules nerveux**
- 🔌 **Le protocole MCP**
- 💻 **Génération de code**
- 🔍 **Analyse de code**
- 🎨 **Création multimédia**
- 🌐 **Recherche web**

**0 hallucination, coût divisé par 10.**

---

## ✨ Les 5 innovations majeures

### 1. 🔍 BEK-LVC (Layered Value Cache)
Cache multi-niveaux et compression de contexte.

### 2. 🧠 SkillAgent (329 skills)
Filtre les skills avant le LLM (90% économie).

### 3. 🛡️ Anti-Hallucination
Critic, Grounding, Swarm valident les réponses.

### 4. 🔌 MCP Gateway
Connecte les outils (REA, Python, Hermes).

### 5. 👁️ Vision Pipeline
Images, Vidéos, Sous-titres.

---

## 🏗️ Architecture

```mermaid
graph TD
    A[Utilisateur] -->|Prompt| B[FastAPI BEK]
    B --> C{SkillAgent}
    C --> D[BEK-LVC Cache]
    D --> E[Hermes Core]
    E --> F[MCP Gateway]
    F --> G[REA/Python/Vision]
    E --> J[Codex]
    B --> K[Anti-Hallucination]
    K --> A
```

---

## 🚀 Démarrage Rapide

**1. Cloner :**
```bash
git clone https://github.com/eddy199/bek-v15-clean.git
cd bek-v15-clean
```

**2. Installer :**
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**3. Configurer :**
```bash
cp env.example env.txt
```

**4. Lancer :**
```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

**5. Ouvrir :** `http://localhost:8000`
