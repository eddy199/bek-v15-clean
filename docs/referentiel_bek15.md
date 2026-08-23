# 🏛️ RÉFÉRENTIEL OFFICIEL DE L'ARCHITECTURE BEK-v15.2
*Écosystème Multi-Agents Autonome, Sécurisé & Haute Performance*
*Version consolidée en production — 22 Août 2026*

---

## 1. Vue d'Ensemble & Objectif du Système
L'écosystème **BEK-v15.2** est un système multi-agents asynchrone, probabiliste et hautement sécurisé[cite: 3]. Il orchestre l'interaction entre les modèles de langage (Groq, NVIDIA NIM, Google Gemini), une mémoire vectorielle à long terme (Pinecone), un pipeline d'événements Kafka, un sas de sécurité cryptographique (OPA/HSM) et un CRM PostgreSQL hébergé sur Neon Serverless via un moteur d'exécution ultra-rapide sous Bun[cite: 2, 3].

---

## 2. Cartographie Détaillée des Agents

### 🤖 1. Agent Superviseur & Décideur (L'Orchestrateur Global)
* **Rôle** : Réceptionne les messages de l'interface Flask (`app.py`), planifie l'exécution, régule les quotas de tokens et supervise le routage multi-agents[cite: 3].
* **Optimisation de Contexte** : Applique une fenêtre glissante stricte (2 derniers tours) et une compression maximale du prompt pour éliminer tout risque de dépassement de limite de tokens (TPM Rate Limit).
* **Liaisons & Routes** :
  * **Amont** : Interface Web Flask (Port 8765)[cite: 3].
  * **Aval** : Sollicite en parallèle l'Agent Mémoire, l'Agent Chercheur et l'Agent Exécuteur[cite: 3].

### 🔍 2. Agent Chercheur (Le Scanneur de Skills & Contexte)
* **Rôle** : Spécialiste de la recherche documentaire et de l'injection des compétences métier locales[cite: 3].
* **Tâches** : Scanne la base locale des 5 477 compétences JSON (`skills/`), extrait les instructions directes et les compresse sous format compact (`SKILL:nom|instruction`)[cite: 3].
* **Liaisons** : Publie l'événement de détection sur le topic Kafka `skills-index`[cite: 3].

### 🧠 3. Agent Mémoire (Le Gestionnaire Vectoriel & RAG)
* **Rôle** : Gestionnaire de la mémoire sémantique à long terme et de la contextualisation[cite: 3].
* **Tâches** :
  * Interroge l'index Pinecone Turbo pour retrouver les contextes métiers passés, les contacts existants ou les contraintes de base[cite: 3].
  * Injecte un contexte tronqué (< 300 caractères) pour préserver la fenêtre de tokens des LLM.
  * Sauvegarde automatiquement chaque action CRM réussie ou incident pour permettre l'apprentissage adaptatif du système[cite: 3].
* **Liaisons** : Publie l'état de récupération sur le topic Kafka `vector-context`[cite: 3].

### 🛡️ 4. Agent Auditeur & Sas de Sécurité (Le Certificateur Blindé)
* **Rôle** : Régulateur de sécurité, filtre OPA Gatekeeper et armurier cryptographique du système[cite: 3].
* **Tâches** :
  * **Validation par Liste Blanche** : Contrôle strict des actions autorisées (`create_contact`, `create_deal`, `create_task`, `search_contact`, `update_contact`, `get_stats`) et suppression de tout paramètre non déclaré.
  * **Bouclier Anti-Injection** : Analyse syntaxique par expressions régulières pour bloquer les patterns destructeurs (`DROP TABLE`, `ALTER`, `DELETE`, etc.).
  * **Signature HSM Virtuelle** : Appose une signature HMAC-SHA256 sur le payload validé.
* **Obligations** : Aucune écriture n'atteint Neon sans certification de l'Auditeur[cite: 3].
* **Liaisons** : Publie sur `error-signals` en cas d'anomalie et déclenche le mode `POLICE_ISOLATION` (Radar Rouge)[cite: 3].

### ⚡ 5. Agent Actionneur / MCP (L'Exécuteur de Tâches)
* **Rôle** : Bras armé exécutant les opérations certifiées directement sur la base de données[cite: 3].
* **Voies d'Exécution** :
  * **Voie 1 (tRPC / API REST NestJS)** : Passage par le backend officiel (`apps/api`) pour la validation des règles métiers applicatives[cite: 2, 3].
  * **Voie 2 (Scripts Bun CLI / Prisma direct)** : Exécution prioritaire via `plugin_crm.py` (`packages/db/src`) contournant la latence réseau avec un temps de réponse < 50 ms[cite: 2, 3].
* **Résilience** : En cas de doublon (ex: email déjà existant dans Neon), relaie l'erreur SQL pour permettre à l'agent de basculer automatiquement sur une mise à jour (`update_contact`).

---

## 3. Moteur Probabiliste, Asynchronisme & Réconciliation

### A. Algorithmes Probabilistes Spider (`fast_math.py`)
* **HyperLogLog (HLL)** : Évaluation de cardinalité en temps constant et mémoire minimale pour mesurer le volume de requêtes traitées sans saturer la RAM.
* **MinHash Similarity** : Calcul rapide de similarité de signatures avec routage adaptatif :
  * Similarité $> 0.9$ : Routage direct / Cache Spider.
  * Similarité $0.7 - 0.9$ : Échantillonnage à 10%.
  * Similarité $\le 0.7$ : Traitement RAG complet à 100%.

### B. Pipeline d'Événements Kafka (`event_bus.py`)
* File d'attente asynchrone non-bloquante gérant 4 topics stricts[cite: 3] :
  1. `web-cleaned` : Données nettoyées de navigation[cite: 3].
  2. `skills-index` : Indexation des compétences appelées[cite: 3].
  3. `error-signals` : Alertes, rejets OPA et anomalies CRM (déclencheur du Radar Rouge)[cite: 3].
  4. `vector-context` : Journalisation des flux Pinecone[cite: 3].

### C. Job de Réconciliation Nocturne (`reconciliation_job.py`)
* Script d'audit automatique comparant les prédictions probabilistes aux totaux réels et consignant l'intégrité globale dans `approximation_audit.json`.

---

## 4. Schéma d'Architecture Globale

```text
================================================================================
                    UTILISATEUR (Interface Chat Web Flask :8765)
================================================================================
                                      │
                                      ▼
================================================================================
                 AGENT SUPERVISEUR & DÉCIDEUR (Anti-Saturation TPM)
================================================================================
         │                                                        │
         ▼                                                        ▼
┌────────────────────────┐┌────────────────────────┐    ┌─────────────────────┐
│    AGENT CHERCHEUR     ││     AGENT MÉMOIRE      │    │  SECOURS D'URGENCE  │
│ (Scan Skills Locaux)   ││ (RAG Pinecone <300 car)│    │  (Failover Modèle)  │
└───────────┬────────────┘└───────────┬────────────┘    └─────────────────────┘
            │                         │                            │
            ▼                         ▼                            │
================================================================================
                   PIPELINE KAFKA (Flux Asynchrones Découplés)
================================================================================
  [web-cleaned]  ──►  [skills-index]  ──►  [error-signals]  ──►  [vector-context]
================================================================================
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                  MOTEUR PROBABILISTE & APPROXIMATION (fast_math)             │
│  - Estimation de Cardinalité (HyperLogLog)                                   │
│  - Calcul de Similarité & Routage Adaptatif (MinHash)                        │
└─────────────────────────────────────┬────────────────────────────────────────┘
                                      │
                                      ▼
================================================================================
            AGENT AUDITEUR & SAS DE SÉCURITÉ (security_guard.py)
================================================================================
  - Filtrage Liste Blanche Stricte (OPA Gatekeeper)
  - Blocage Immédiat des Injections SQL
  - Cachet Cryptographique Virtuel (Signature HMAC-SHA256)
                                      │
                                      ▼
================================================================================
                    AGENT ACTIONNEUR / MCP (plugin_crm.py)
================================================================================
                      │
       ┌──────────────┴──────────────┐
       ▼                             ▼
┌──────────────────────────┐  ┌────────────────────────────────────────────────┐
│  Voie 1 : tRPC NestJS    │  │  Voie 2 : Scripts Bun CLI / Prisma Direct      │
│  (Validation API REST)   │  │  (Accès Ultra-Rapide PostgreSQL Cloud Neon)    │
└──────────────────────────┘  └────────────────────────────────────────────────┘
                                      │
                                      ▼
================================================================================
                      POSTGRESQL SERVERLESS CLOUD (NEON)
================================================================================