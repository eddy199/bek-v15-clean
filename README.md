<div align="center">
  <img src="./assets/logo.png" alt="BEK Hybrid Logo" width="250"/>
  
  <h1>🧠 BEK Hybrid Agent v19</h1>
  
  <p><strong>L'écosystème d'IA agentique souverain, économe en tokens et sans hallucination.</strong></p>
  
  <p>Créé par <strong>BEKKARA Mohamed</strong> — Oran, Algérie.</p>

  <!-- 🛡️ SÉCURITÉ & LÉGAL -->
  <p>
    <img src="https://img.shields.io/badge/License-AGPL%20v3-blue.svg?style=for-the-badge&logo=gnu" alt="License" />
    <img src="https://img.shields.io/badge/Python-3.12+-3776AB.svg?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
    <img src="https://img.shields.io/badge/FastAPI-005571.svg?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
    <img src="https://img.shields.io/badge/Brevets-16%20D%C3%A9pos%C3%A9s-critical?style=for-the-badge" alt="Brevets" />
    <img src="https://img.shields.io/badge/S%C3%A9curit%C3%A9-Token%20Guard%20L1--L5-red?style=for-the-badge" alt="Security" />
  </p>

  <!-- ⚙️ ARCHITECTURE & INNOVATIONS -->
  <p>
    <img src="https://img.shields.io/badge/BEK--CPU-Logique%20Virtuel-purple?style=for-the-badge" alt="BEK-CPU" />
    <img src="https://img.shields.io/badge/BEK--LVC-10x%20%C3%89conomie-orange?style=for-the-badge" alt="BEK-LVC" />
    <img src="https://img.shields.io/badge/Nerves-12%20Modules-success?style=for-the-badge" alt="Nerves" />
    <img src="https://img.shields.io/badge/Hermes-62%20Outils-blueviolet?style=for-the-badge" alt="Hermes" />
  </p>

  <!-- 🧠 CAPACITÉS AGENTIQUES & MÉDIAS -->
  <p>
    <img src="https://img.shields.io/badge/Skills-329-brightgreen?style=for-the-badge" alt="Skills" />
    <img src="https://img.shields.io/badge/Agentic-Autonome-ff69b4?style=for-the-badge" alt="Agentic" />
    <img src="https://img.shields.io/badge/Alter--Egos-6-9cf?style=for-the-badge" alt="Alter Egos" />
    <img src="https://img.shields.io/badge/Vision-Multim%C3%A9dia-informational?style=for-the-badge" alt="Vision" />
    <img src="https://img.shields.io/badge/Vid%C3%A9o-Agnes%20%2F%20Veo-yellow?style=for-the-badge" alt="Video" />
  </p>
</div>

---

## 📸 Aperçu de l'Interface

Voici à quoi ressemble BEK Hybrid Agent en action :

| 💬 Chat & Raisonnement | 🧠 329 Compétences Actives |
| :---: | :---: |
| <img src="assets/chat.png" width="400"/> | <img src="assets/skills.png" width="400"/> |

| 🗄️ Mémoire Vectorielle (Pinecone) | 🔌 Connecteurs Système |
| :---: | :---: |
| <img src="assets/memory.png" width="400"/> | <img src="assets/connectors.png" width="400"/> |

| 🤖 Fournisseurs d'IA Connectés | 🎨 Génération d'Images (Vision) |
| :---: | :---: |
| <img src="assets/providers.png" width="400"/> | <img src="assets/generation.png" width="400"/> |

| 🔁 Reflex Loop (Auto-Correction) | 📁 Gestion de Fichiers |
| :---: | :---: |
| <img src="assets/reflex.png" width="400"/> | <img src="assets/files.png" width="400"/> |

---

## 🚀 Qu'est-ce que BEK ?

**BEK** (Bekkara Hybrid Agent) est un **agent autonome multi-fonction** qui unifie :
- 🧠 **6 briques cognitives** (BEK-LVC : REX, FLUX, MEM, LOOP, ECO, STAIR) et **12 modules nerveux** additifs.
- 🔌 **Le protocole MCP** (Model Context Protocol) pour connecter des outils externes
- 💻 **La génération de code** (Python, JavaScript, C++, etc.)
- 🔍 **L'analyse de code** (REA pour le reverse engineering, analyseur Python AST)
- 🎨 **La création multimédia** (images, vidéos, sous-titres)
- 🌐 **La recherche web** (Headless Browser, WebAgent)

**Le tout avec 0 hallucination et un coût en tokens divisé par 10.**

---

## ✨ Les 5 innovations majeures

### 1. 🔍 BEK-LVC (Layered Value Cache)
Un système de **cache multi-niveaux et de compression de contexte** qui réduit la consommation de tokens de manière drastique.
- **Pause économique** de 3s entre les appels LLM
- **Pré-résumé JSON** avant analyse (compression 10:1)
- **Cache intelligent** des requêtes identiques

### 2. 🧠 SkillAgent (329 skills)
Un **agent de compétences** qui filtre les 329 skills BEK avant d'appeler le LLM.
- Détection automatique de la catégorie (CODE, SECURITY, DATA, AGENT)
- Injection uniquement des skills pertinentes
- **Économie : 90% de tokens en moins** par requête

### 3. 🛡️ Anti-Hallucination
3 modules cognitifs (Critic, Grounding, Swarm) qui **valident chaque réponse** contre les sources réelles.
- Détection des URLs inventées
- Détection des faits hallucinés
- Score de confiance sur chaque réponse

### 4. 🔌 MCP Gateway (Model Context Protocol)
Une passerelle qui connecte **n'importe quel outil** via le protocole MCP :
- **REA** (reverse engineering JavaScript/binaire)
- **Python Analyzer** (AST, analyse de dossiers)
- **Tous les outils Hermes** (62 outils enregistrés)

### 5. 👁️ Vision Pipeline
Un pipeline multimédia complet :
- **Images** : Pollinations (gratuit), Gemini, Hugging Face
- **Vidéos** : Agnes (gratuit, avec audio), Veo 3.1
- **Sous-titres** : Whisper local (gratuit)
- **Extension vidéo** : continuité personnage par keyframes

---

## 🏗️ Architecture

```mermaid
graph TD
    A[Utilisateur] -->|Prompt| B[FastAPI BEK]
    B --> C{SkillAgent Router}
    C -->|Filtre 329 skills| D[BEK-LVC Cache]
    D --> E[Hermes Core & 12 Nerves]
    E -->|Appel Outils| F[MCP Gateway]
    F --> G[REA - Reverse Engineering]
    F --> H[Python Analyzer]
    F --> I[Vision Pipeline]
    E --> J[Codex - Génération Code]
    B --> K[Anti-Hallucination]
    K -->|Réponse Finale| A