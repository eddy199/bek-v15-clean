# BEK — Registre des Briques
## BRIBES REGISTRY

**Version :** 1.0
**Date :** 2026-09-23

---

## 1. PRINCIPE

Ce document liste **TOUTES les briques BEK** disponibles.
Chaque brique a :
- Une **abréviation** (nom court, 3-5 lettres)
- Un **brevet** (documentation complète)
- Une **implémentation** (code Python)
- Des **fonctions** (API)

---

## 2. LES 5 INSTRUCTIONS PRINCIPALES (BCA)

### 2.1 — BEK-REX

**Nom complet :** Reflective EXecution
**Brevet :** `docs/brevets/BREVET_REX.md`
**Implémentation :** `bek_core/rex/`
**Rôle :** Routing 5 tiers (LOCAL, FAST, DEEP, EXPERT, SPECIALIZED)
**Version :** 1.0
**Statut :** ✅ Actif

### 2.2 — BEK-FLUX

**Nom complet :** Fast Layered Unified eXecution
**Brevet :** `docs/brevets/BREVET_FLUX.md`
**Implémentation :** `bek_core/flux/`
**Rôle :** Parallélisation DAG Engine
**Version :** 1.0
**Statut :** ✅ Actif

### 2.3 — BEK-MEM

**Nom complet :** Methodological Evolution Memory
**Brevet :** `docs/brevets/BREVET_MEM.md`
**Implémentation :** `bek_core/mem/`
**Rôle :** Mémoire associative par prototypes
**Version :** 1.0
**Statut :** ✅ Actif

### 2.4 — BEK-LOOP

**Nom complet :** LOOp-adaptive Protocol
**Brevet :** `docs/brevets/BREVET_LOOP.md`
**Implémentation :** `bek_core/loop/`
**Rôle :** Auto-apprentissage continu
**Version :** 1.0
**Statut :** ✅ Actif

### 2.5 — BEK-ECO

**Nom complet :** Economic Cognitive Optimization
**Brevet :** `docs/brevets/BREVET_ECO.md`
**Implémentation :** `bek_core/eco/`
**Rôle :** Optimisation économique (cache, limites, scoring)
**Version :** 1.0
**Statut :** ✅ Actif

---

## 3. LES BRIQUES EXISTANTES (à refondre)

### 3.1 — BEK-MUX

**Nom complet :** BEK Multiplexer
**Rôle :** Multiplexage providers (Kimi, NVIDIA, Groq...)
**Version actuelle :** intégré dans `provider_manager.py`
**Version cible :** 1.0 (à refondre)
**Statut :** ⏳ À refondre

### 3.2 — BEK-HERMES

**Nom complet :** BEK Hermes Orchestrator
**Rôle :** Orchestrateur principal
**Version actuelle :** intégré dans `hermes_core.py`
**Version cible :** 1.0 (à refondre)
**Statut :** ⏳ À refondre

### 3.3 — BEK-HEAD

**Nom complet :** BEK Headless Search
**Rôle :** Recherche rapide (10 sources)
**Version actuelle :** `worker_headless.py` v15
**Version cible :** 1.0 (à refondre)
**Statut :** ⏳ À refondre

### 3.4 — BEK-WEB

**Nom complet :** BEK WebAgent
**Rôle :** Recherche profonde (13-20 sources + DAG)
**Version actuelle :** `web_agent.py` v2
**Version cible :** 1.0 (à refondre)
**Statut :** ⏳ À refondre

### 3.5 — BEK-MCP

**Nom complet :** BEK Model Context Protocol
**Rôle :** Passerelle MCP
**Version actuelle :** `mcp_gateway.py`
**Version cible :** 1.0 (à refondre)
**Statut :** ⏳ À refondre

### 3.6 — BEK-CRM

**Nom complet :** BEK Sub-CRM Engine
**Rôle :** CRM Matrix
**Version actuelle :** `sub_crm_engine.py`
**Version cible :** 1.0 (à refondre)
**Statut :** ⏳ À refondre

### 3.7 — BEK-GUARD

**Nom complet :** BEK Security Guardian
**Rôle :** Sécurité (HMAC, allowlist)
**Version actuelle :** `security_guard.py`
**Version cible :** 1.0 (à refondre)
**Statut :** ⏳ À refondre

### 3.8 — BEK-APPROVAL

**Nom complet :** BEK Approval Manager
**Rôle :** Approbation humaine L3+
**Version actuelle :** `approval_manager.py`
**Version cible :** 1.0 (à refondre)
**Statut :** ⏳ À refondre

### 3.9 — BEK-SKILL

**Nom complet :** BEK Skill Engine
**Rôle :** Skills dynamiques (5193 skills)
**Version actuelle :** `skill_registry.py`
**Version cible :** 1.0 (à refondre)
**Statut :** ⏳ À refondre

### 3.10 — BEK-VISION

**Nom complet :** BEK Vision Engine
**Rôle :** Images, vidéos, sous-titres Whisper
**Version actuelle :** `services/vision/`
**Version cible :** 1.0 (à refondre)
**Statut :** ⏳ À refondre

---

## 4. LES BRIQUES À CRÉER (futures)

### 4.1 — BEK-TRACE

**Nom complet :** BEK Tracing Engine
**Rôle :** Tracing distribué (OpenTelemetry)
**Statut :** 📝 Planifié

### 4.2 — BEK-CACHE

**Nom complet :** BEK Cache Manager
**Rôle :** Cache multi-niveaux (Redis, Chroma, Pinecone)
**Statut :** 📝 Planifié

### 4.3 — BEK-SCHED

**Nom complet :** BEK Scheduler
**Rôle :** Ordonnancement des tâches (DAG-aware)
**Statut :** 📝 Planifié

### 4.4 — BEK-DOC

**Nom complet :** BEK Documentation Engine
**Rôle :** Auto-génération de la documentation
**Statut :** 📝 Planifié

### 4.5 — BEK-TRANSLATE

**Nom complet :** BEK Translation Engine
**Rôle :** Multi-langages (13 langages supportés)
**Statut :** 📝 Planifié

---

## 5. LES AGENTS (compositions)

### 5.1 — BEK-AGENT-v18

**Nom complet :** BEK Agent v18
**Dépendances :** REX + FLUX + MEM + LOOP + ECO + HERMES + WEB + MCP
**Docker :** `bek-agent-v18`
**Statut :** ✅ Actif (ton agent actuel)

### 5.2 — BEK-AGENT-MEDICAL (futur)

**Nom complet :** BEK Agent Medical
**Spécialisation :** Médecine, biologie
**Dépendances :** REX + FLUX + MEM + LOOP + ECO + BEK-HEAD
**Statut :** 📝 Planifié

### 5.3 — BEK-AGENT-RESEARCH (futur)

**Nom complet :** BEK Agent Research
**Spécialisation :** Recherche académique
**Dépendances :** REX + FLUX + MEM + LOOP + ECO + WEB + MCP
**Statut :** 📝 Planifié

### 5.4 — BEK-AGENT-LEGAL (futur)

**Nom complet :** BEK Agent Legal
**Spécialisation :** Juridique, droit
**Dépendances :** REX + FLUX + MEM + LOOP + ECO + BEK-HEAD
**Statut :** 📝 Planifié

---

## 6. FORMAT DES ABRÉVIATIONS

**Règle :** `BEK-<NOM>-<VERSION>`

**Exemples :**
- `BEK-REX` (instruction)
- `BEK-AGENT-v18` (agent)
- `BEK-CACHE-v1.0` (brique avec version)
- `BEK-CUSTOM-XXX` (brique custom)

---

## 7. TABLEAU RÉCAPITULATIF

| Abréviation | Type | Rôle | Statut |
|---|---|---|---|
| BEK-REX | Instruction | Routing | ✅ Actif |
| BEK-FLUX | Instruction | Parallélisation | ✅ Actif |
| BEK-MEM | Instruction | Mémoire | ✅ Actif |
| BEK-LOOP | Instruction | Apprentissage | ✅ Actif |
| BEK-ECO | Instruction | Optimisation | ✅ Actif |
| BEK-MUX | Brique | Multiplexage | ⏳ À refondre |
| BEK-HERMES | Brique | Orchestrateur | ⏳ À refondre |
| BEK-HEAD | Brique | Recherche rapide | ⏳ À refondre |
| BEK-WEB | Brique | Recherche profonde | ⏳ À refondre |
| BEK-MCP | Brique | Passerelle MCP | ⏳ À refondre |
| BEK-CRM | Brique | CRM Matrix | ⏳ À refondre |
| BEK-GUARD | Brique | Sécurité | ⏳ À refondre |
| BEK-APPROVAL | Brique | Approbation | ⏳ À refondre |
| BEK-SKILL | Brique | Skills | ⏳ À refondre |
| BEK-VISION | Brique | Vision | ⏳ À refondre |
| BEK-AGENT-v18 | Agent | Agent complet | ✅ Actif |

---

## 8. SIGNATURE
