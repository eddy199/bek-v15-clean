# Architecture CRM — Document de référence

> Date : août 2026 — Projet `crm-release` + `workspacekimi`
> Objectif : servir de base si tu veux créer un nouveau CRM, plus rapide et plus léger.

---

## 1. Architecture actuelle (telle qu'elle existe)

### Vue d'ensemble

```
                        ┌──────────────┐
                        │ UTILISATEUR  │
                        └──────┬───────┘
                               │ HTTPS
        ┌──────────────────────▼──────────────────────┐
        │  FRONTEND — apps/app (Next.js)              │
        │  Hébergé sur : Vercel                       │
        │  Pages : dashboard, companies, contacts,    │
        │  deals, settings, agent-builder, tracking   │
        └──────────────────────┬──────────────────────┘
                               │ tRPC / REST
                               │ (NEXT_PUBLIC_API_URL)
        ┌──────────────────────▼──────────────────────┐
        │  API — apps/api (NestJS + tRPC)             │
        │  Hébergé sur : Render (Docker)              │
        │  Modules : auth, companies, contacts,       │
        │  deals, conversations, google, microsoft,   │
        │  slack, currency, tracking, telemetry,      │
        │  search, settings, sso, agent               │
        └───┬──────────────┬───────────────┬──────────┘
            │ Prisma       │               │ Bearer secret
   ┌────────▼─────┐  ┌─────▼──────┐  ┌─────▼───────────────┐
   │ NEON         │  │ SERVICES   │  │ AGENT FLASK         │
   │ (PostgreSQL) │  │ EXTERNES   │  │ (workspacekimi)     │
   │              │  │            │  │ Hébergé : Render    │
   │ Tables CRM   │  │ Google     │  │ Routes :            │
   └──────────────┘  │ Microsoft  │  │ /internal/crm/*     │
                     │ Slack      │  │ /health             │
                     │ Groq       │  └─────────────────────┘
                     │ OpenRouter │
                     │ Perplexity │
                     └────────────┘

   ┌─────────────────────────────────────────────────────┐
   │  AGENT TS — apps/agent (dans le monorepo)           │
   │  Moteur d'agents : subagents (builder / runner),    │
   │  outils CRM, sandbox, channels (crm, eve)           │
   └─────────────────────────────────────────────────────┘
```

### Les 4 composants déployés

| # | Composant | Techno | Hébergeur | Rôle |
|---|-----------|--------|-----------|------|
| 1 | `apps/app` | Next.js | Vercel | Interface web CRM |
| 2 | `apps/api` | NestJS + tRPC + Prisma | Render (Docker) | Logique métier + base de données |
| 3 | `apps/agent` | TypeScript | (dans le monorepo) | Moteur d'agents IA |
| 4 | `workspacekimi` | Python Flask | Render (Docker) | Pont agent ↔ CRM (dispatch, cancel) |

### Structure du monorepo `crm-release`

```
crm-release/
├── apps/
│   ├── app/        → Frontend Next.js (pages CRM + agent-builder)
│   ├── api/        → API NestJS (tous les modules métier)
│   └── agent/      → Agents IA TypeScript (subagents, tools, sandbox)
├── packages/
│   ├── ui/         → Composants partagés (boutons, tables, formulaires…)
│   └── validation/ → Schémas de validation partagés
├── turbo.json      → Orchestration monorepo (Turborepo)
├── vercel.json     → Config déploiement frontend
├── render.yaml     → Config déploiement API
└── apps/api/Dockerfile
```

### Structure de `workspacekimi` (agent Flask)

```
workspacekimi/
├── app.py            → Serveur Flask (routes /internal/crm/*, /health)
├── requirements.txt  → Dépendances Python
├── Dockerfile        → Image Docker pour Render
├── render.yaml       → Config déploiement
└── venv/             → (local uniquement, jamais sur GitHub)
```

Sécurité du pont : `AGENT_BRIDGE_SECRET` (Bearer token) entre l'API et l'agent Flask.

---

## 2. Pourquoi c'était lourd (leçons pour le prochain)

| Problème | Cause | Conséquence |
|----------|-------|-------------|
| 4 services à déployer | Front + API + 2 agents séparés | 4 configs, 4 hébergeurs à synchroniser |
| Monorepo Turborepo | 1400+ fichiers, builds en chaîne | Builds de 6 minutes en local |
| Sync Gmail / Outlook / Slack | Des centaines de fichiers de modules | 80 % de la complexité pour 20 % de la valeur |
| Agent en double | Agent TypeScript **et** agent Python Flask | Deux runtimes à maintenir |
| URLs croisées | Front ↔ API ↔ Agent doivent se connaître | 3 variables d'env à synchroniser |

---

## 3. Architecture recommandée pour un CRM léger et rapide

### Principe : 1 seul service au départ

```
        ┌──────────────────────────────────────────┐
        │              UTILISATEUR                 │
        └───────────────────┬──────────────────────┘
                            │ HTTPS
        ┌───────────────────▼──────────────────────┐
        │   MONOLITHE Next.js (App Router)         │
        │   ─ Frontend (pages CRM)                 │
        │   ─ Backend (API routes / server actions)│
        │   ─ IA : appels directs Groq/OpenRouter  │
        │   Hébergé sur : Vercel (1 déploiement)   │
        └───────────────────┬──────────────────────┘
                            │ Prisma ou Drizzle
                ┌───────────▼────────────┐
                │  PostgreSQL (Neon)     │
                └────────────────────────┘
```

### Stack recommandée

| Couche | Choix léger | Pourquoi |
|--------|-------------|----------|
| Front + Back | **Next.js seul** (pas de NestJS séparé) | 1 projet, 1 build, 1 déploiement |
| Base de données | **Neon (Postgres)** + Drizzle ou Prisma | Gratuit, serverless, stable |
| Auth | **better-auth** ou Auth.js | Simple, pas besoin de SSO au début |
| UI | **shadcn/ui + Tailwind** | Tu as déjà les composants dans `packages/ui` |
| IA | Appels API **directs** (Groq / OpenRouter) | Pas de service agent séparé |
| Déploiement | **Vercel uniquement** | Fini les URLs croisées |

### Ordre de construction (par priorité)

1. **Cœur CRM** : Contacts, Entreprises, Deals (CRUD simple)
2. **Activités** : notes et historique sur chaque fiche
3. **Dashboard** : 3-4 indicateurs (deals ouverts, montant, activité)
4. **Recherche** : barre de recherche globale
5. **IA (optionnel)** : bouton "résumer" / "enrichir" qui appelle Groq directement
6. **Plus tard seulement** : sync emails, agents autonomes, Slack…

### Règle d'or

> **Un service = un problème en moins.** N'ajoute un composant séparé (API, agent, worker) que quand le monolithe montre une vraie limite. Le projet précédent avait l'architecture d'une équipe de 10 développeurs ; pour 1 personne, le monolithe Next.js suffit largement.

---

## 4. Ce que tu peux réutiliser de l'ancien projet

| Élément | Réutilisable ? |
|---------|----------------|
| `packages/ui` (composants) | ✅ Oui, copie les composants dont tu as besoin |
| Schéma Prisma (tables CRM) | ✅ Oui, bonne base de départ |
| `packages/validation` | ✅ Oui |
| Modules sync Google/Microsoft/Slack | ❌ Trop lourds, à réécrire si besoin un jour |
| Agents (TS + Flask) | ❌ Remplacer par des appels IA directs |
| Config Vercel/Render/Docker | ⚠️ Seul `vercel.json` reste utile |
