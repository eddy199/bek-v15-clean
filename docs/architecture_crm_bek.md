# 🏛️ RÉFÉRENTIEL TECHNIQUE DU CRM (Projet `bek-v15-clean`)

## 1. Vue d'Ensemble & Stack Technique
Le CRM est structuré sous forme de monorepo optimisé, exécuté principalement avec **Bun** et connecté à une base PostgreSQL Serverless hébergée sur **Neon**[cite: 1, 2].

* **Frontend (`apps/app`)** : Application Next.js (App Router, Tailwind CSS, composants UI partagés)[cite: 3].
* **Backend API (`apps/api`)** : Serveur d'API modulaire NestJS + tRPC contenant 34 modules métier (`contacts`, `deals`, `companies`, `activities`, `users`, `crm`, `trpc`, etc.)[cite: 1, 3].
* **Moteur d'Agents Monorepo (`apps/agent`)** : Gestion des subagents, channels, sandboxes, tools et hooks.
* **Module Base de Données (`packages/db`)** : Client Prisma centralisé, migrations et scripts utilitaires d'accès rapide (`peek.ts`, `keep-alive.ts`, `agent-tasks.ts`, `crm-events.ts`)[cite: 2].
* **Packages Partagés (`packages/`)** : `auth`, `env`, `telemetry`, `typescript-config`, `ui`, `validation`[cite: 3].

---

## 2. Cartographie des Tables & Entités Principales (Prisma / Neon)
L'Agent Actionneur et l'Agent Exécuteur ciblent principalement les entités suivantes pour les opérations automatisées[cite: 1, 2] :

* **Contact** : Prospects et clients (`name`, `email`, `phone`, `companyId`, `metadata`).
* **Deal** : Opportunités commerciales (`title`, `amount`, `stage`, `contactId`, `currency`).
* **Company** : Entreprises et comptes associés.
* **Activity / Task** : Tâches planifiées, rendez-vous et notes d'historique.
* **CrmEvent / Telemetry** : Traçabilité des actions et journalisation des signaux d'erreur.

---

## 3. Voies d'Exécution de l'Agent Actionneur (MCP)
L'Agent Actionneur dispose de deux voies prioritaires pour appliquer les changements :

1. **Voie 1 : tRPC / API REST (`apps/api`)**
   * Utilisée pour les opérations standard nécessitant la validation complète des règles métier et des middlewares NestJS[cite: 1, 3].

2. **Voie 2 : Scripts Bun Directs (`packages/db/src`)**
   * Utilisée via `plugin_crm.py` pour des opérations ultra-rapides, contournant les latences de routage en exécutant directement des requêtes SQL/Prisma via le runtime Bun[cite: 1, 2].

---

## 4. Règles & Contraintes pour les Agents
* Toujours valider la structure des paramètres (`params`) avant d'émettre un payload JSON d'action[cite: 1, 2].
* En cas d'échec sur une route d'API, utiliser le canal `error-signals` pour permettre à l'Auditeur d'évaluer la panne.
* Ne jamais altérer la structure du schéma (`schema.prisma`) sans validation du sas de sécurité. 
