# 🚀 Migration Cloud — Guide Express

## Architecture

| Service | Hébergeur | URL finale | Coût |
|---------|-----------|------------|------|
| Frontend Next.js | **Vercel** | `https://crm-tonnom.vercel.app` | Gratuit |
| API NestJS | **Render** | `https://crm-api-xxx.onrender.com` | Gratuit |
| Agent Python | **Render** | `https://crm-agent-xxx.onrender.com` | Gratuit |
| Base de données | **Neon** (déjà fait) | `ep-empty-surf-...neon.tech` | Gratuit |

---

## ÉTAPE 1 : Préparer les repos GitHub (2 min)

1. Crée un repo GitHub : `crm-release`
2. Crée un repo GitHub : `workspacekimi`
3. Dans chaque dossier local, exécute :

```bash
cd E:\\crm-release
git init
git add .
git commit -m "init"
git remote add origin https://github.com/TON_USER/crm-release.git
git push -u origin main

cd E:\\workspacekimi
git init
git add .
git commit -m "init"
git remote add origin https://github.com/TON_USER/workspacekimi.git
git push -u origin main
```

---

## ÉTAPE 2 : Déployer le Frontend sur Vercel (3 min)

1. Va sur [vercel.com](https://vercel.com) → Sign up with GitHub
2. **New Project** → Import `crm-release`
3. **Framework Preset** : Next.js
4. **Root Directory** : `.` (laisse par défaut)
5. **Build Command** : laisse Vercel lire le `vercel.json`
6. **Environment Variables** → Ajoute :

```
NEXT_PUBLIC_API_URL=https://crm-api-xxx.onrender.com
```

7. **Deploy**

✅ Build : ~30 secondes (vs 6 minutes sur ton disque E:)

---

## ÉTAPE 3 : Déployer l'API sur Render (5 min)

1. Va sur [render.com](https://render.com) → Connect GitHub
2. **New** → **Blueprint** → Connecte le repo `crm-release`
3. Render détecte automatiquement `render.yaml`
4. Remplis les variables d'environnement manquantes :

```
DATABASE_URL=postgresql://neondb_owner:npg_2IUtRVkPGpz1@ep-empty-surf-axt8wat4.c-4.us-east-2.aws.neon.tech/neondb?sslmode=require
DIRECT_URL=postgresql://neondb_owner:npg_2IUtRVkPGpz1@ep-empty-surf-axt8wat4.c-4.us-east-2.aws.neon.tech/neondb?sslmode=require
AGENT_URL=https://crm-agent-xxx.onrender.com
GOOGLE_CLIENT_ID=ton-client-id
GOOGLE_CLIENT_SECRET=ton-secret
BETTER_AUTH_SECRET=un-secret-32-caracteres-aleatoires
BETTER_AUTH_URL=https://crm-api-xxx.onrender.com
```

5. **Apply**

✅ Build : ~2 minutes

---

## ÉTAPE 4 : Déployer l'Agent sur Render (3 min)

1. **New** → **Blueprint** → Connecte le repo `workspacekimi`
2. Render détecte `render.yaml`
3. Remplis les variables :

```
API_URL=https://crm-api-xxx.onrender.com
AGENT_BRIDGE_SECRET=dev-bridge-secret-crm-bek-2026
```

4. **Apply**

✅ Build : ~1 minute

---

## ÉTAPE 5 : Mettre à jour les URLs croisées (2 min)

| Fichier | Variable | Valeur |
|---------|----------|--------|
| Vercel (UI) | `NEXT_PUBLIC_API_URL` | `https://crm-api-xxx.onrender.com` |
| Render API | `AGENT_URL` | `https://crm-agent-xxx.onrender.com` |
| Render Agent | `API_URL` | `https://crm-api-xxx.onrender.com` |

Redéploie si nécessaire.

---

## ⚡ Résultat

| Action | Avant (disque E:) | Après (cloud) |
|--------|-------------------|---------------|
| Build Next.js | **6 minutes** | **30 secondes** |
| Compilation page | **2-3 minutes** | **Instantané** |
| Connexion Neon | Timeout fréquent | **Stable** |
| Redémarrage | Tout à refaire | **Zero-downtime** |
| Accès | `localhost:3000` | **Partout dans le monde** |

---

## ⚠️ Limites du gratuit

- **Render Free** : Le service s'endort après 15 min d'inactivité. Le premier appel prend 30-60s (cold start). Le keep-alive Neon ne s'applique plus (Neon est déjà en cloud).
- **Vercel Free** : 100 GB de bande passante/mois (suffisant pour un CRM perso).
- **Neon Free** : 500 MB de stockage (déjà configuré).

**Pour éviter le cold start Render** : ajoute un ping toutes les 10 minutes via [UptimeRobot](https://uptimerobot.com) (gratuit).

---

## 🆘 Si le build Vercel échoue

Vérifie que `next.config.ts` ne contient PAS :
```ts
output: 'export'
```

Si c'est le cas, supprime cette ligne.

## 🆘 Si le build API échoue

Vérifie dans Render les logs. L'erreur la plus fréquente est un mauvais `dist/main.js`. Si NestJS compile vers `dist/src/main.js`, modifie le Dockerfile :
```dockerfile
CMD ["bun", "run", "apps/api/dist/src/main.js"]
```
