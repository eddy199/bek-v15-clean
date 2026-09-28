# BEK-CPU — Le CPU Logique Virtuel
## Le Control Processing Unit Cognitif

**Version :** 1.0
**Date :** 2026-09-26
**Brevet :** BEK-CPU-v1.0
**Doc :** `bek_core/README.md`

---

## 1. PRINCIPE

Le **BEK-CPU** est un CPU **logique** (pas physique) qui :

1. Reçoit une **abréviation** (ex: `BEK-REX`)
2. **Traduit** cette abréviation en code exécutable Python
3. **Exécute** la brique correspondante
4. **Retourne** le résultat

**Analogie :** exactement comme un CPU physique reçoit un opcode (`ADD`, `MOV`, `JMP`), l'exécute, et retourne un résultat.

**En 3 lignes :**

```python
from bek_core import BekCPU

result = BekCPU.execute("BEK-REX", "bek_rex_route", query="Cherche Bitcoin")
# → {"tier": "TIER_2", "confidence": 0.95, "reasoning": "..."}
```

---

## 2. ARCHITECTURE

### 2.1 — Composants

```
┌──────────────────────────────────────────────────────────────┐
│                       BekCPU (cpu.py)                        │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  execute(abrev, function, **kwargs)                  │    │
│  │  list()  ·  list_functions()  ·  doc()  ·  describe()│    │
│  └────────────────────┬─────────────────────────────────┘    │
│                       ▼                                       │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  BekTranslator (translator.py)                       │    │
│  │  - Résout module Python depuis registry.json         │    │
│  │  - Charge le module                                  │    │
│  │  - Récupère la fonction                              │    │
│  │  - Valide les paramètres requis                      │    │
│  └────────────────────┬─────────────────────────────────┘    │
│                       ▼                                       │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  BekRegistry (registry.py)                           │    │
│  │  - Lit registry.json                                 │    │
│  │  - Retourne les métadonnées d'une brique             │    │
│  └──────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │   6 briques cognitives       │
        │   REX  ·  FLUX  ·  MEM       │
        │   LOOP ·  ECO   ·  STAIR     │
        └──────────────────────────────┘
```

### 2.2 — Flux d'exécution

```
Utilisateur
   │
   ▼
BekCPU.execute("BEK-REX", "bek_rex_route", query="...")
   │
   ├─► BekRegistry.get("BEK-REX")
   │     → {"module": "bek_core.rex.router", "functions": {...}}
   │
   ├─► BekTranslator.resolve("bek_core.rex.router", "bek_rex_route")
   │     → importlib.import_module + getattr
   │
   ├─► Validation des paramètres (["query"])
   │
   └─► Exécution de la fonction
         → retourne le résultat
```

### 2.3 — Structure des fichiers

```
bek_core/
├── __init__.py          # Exports publics (BekCPU, BekTranslator, BekRegistry)
├── cpu.py               # Point d'entrée — la classe BekCPU
├── registry.py          # Chargement du registre
├── registry.json        # Catalogue des 6 briques
├── translator.py        # Résolution abréviation → module Python
│
├── rex/                 # BEK-REX (routing)
│   ├── __init__.py
│   ├── MANIFEST.json
│   ├── router.py
│   └── BREVET_REX.md
│
├── flux/                # BEK-FLUX (parallélisation)
├── mem/                 # BEK-MEM (mémoire)
├── loop/                # BEK-LOOP (apprentissage)
├── eco/                 # BEK-ECO (optimisation)
└── stair/               # BEK-STAIR (anti-hallucination)
```

---

## 3. API DU CPU

### 3.1 — `execute(abreviation, function, **kwargs)`

Exécute une instruction BEK.

```python
result = BekCPU.execute(
    "BEK-REX",              # Abréviation
    "bek_rex_route",        # Fonction
    query="Cherche Bitcoin" # Paramètres (kwargs)
)
```

**Erreurs possibles :**
- `ValueError` — abréviation inconnue, fonction inexistante, paramètre requis manquant
- `ImportError` — module Python introuvable

### 3.2 — `list()`

Liste toutes les briques disponibles.

```python
BekCPU.list()
# → ['BEK-ECO', 'BEK-FLUX', 'BEK-LOOP', 'BEK-MEM', 'BEK-REX', 'BEK-STAIR']
```

### 3.3 — `list_functions(abreviation)`

Liste les fonctions d'une brique.

```python
BekCPU.list_functions("BEK-REX")
# → ['bek_rex_list_tiers', 'bek_rex_route']
```

### 3.4 — `doc(abreviation)`

Retourne le chemin du brevet.

```python
BekCPU.doc("BEK-REX")
# → 'docs/brevets/BREVET_REX.md'
```

### 3.5 — `describe(abreviation)`

Description complète.

```python
BekCPU.describe("BEK-REX")
# → {
#     "abreviation": "BEK-REX",
#     "nom_complet": "Reflective EXecution",
#     "version": "1.0",
#     "module": "bek_core.rex.router",
#     "brevet": "docs/brevets/BREVET_REX.md",
#     "functions": ["bek_rex_list_tiers", "bek_rex_route"],
#     "dependencies": [],
#     "status": "active"
# }
```

### 3.6 — `exists(abreviation)`

```python
BekCPU.exists("BEK-REX")   # → True
BekCPU.exists("BEK-XXXX")  # → False
```

### 3.7 — `validate()`

Valide le registre.

```python
BekCPU.validate()
# → {"valid": True, "errors": [], "warnings": [], "total_briques": 6}
```

### 3.8 — `can_execute(abreviation, function)`

Vérifie si une instruction peut être exécutée.

```python
BekCPU.can_execute("BEK-REX", "bek_rex_route")  # → True
```

### 3.9 — `reload()`

Recharge le registre depuis le disque (après modification de `registry.json`).

```python
BekCPU.reload()
```

---

## 4. LES 6 BRIQUES

### 4.1 — BEK-REX (routing 5 tiers)

```python
BekCPU.execute("BEK-REX", "bek_rex_route", query="Cherche Bitcoin")
# → {"tier": "TIER_2", "confidence": 1.0, "reasoning": "..."}
```

**Tiers :** TIER_0 (local) → TIER_4 (spécialisé)

### 4.2 — BEK-FLUX (parallélisation DAG)

```python
tasks = [{"id": "t1", "fn": ma_fonction, "args": []}]
BekCPU.execute("BEK-FLUX", "bek_flux_run", tasks=tasks)
# → {"t1": ..., "_meta": {"total": 1, "success": 1, "elapsed_ms": 200}}
```

**Gain mesuré :** 7.2x sur 8 tâches.

### 4.3 — BEK-MEM (mémoire par prototypes)

```python
proto_id = BekCPU.execute("BEK-MEM", "bek_mem_store",
    query="Cherche Bitcoin", tier="TIER_2", result={"method": "web_sync"})
# → "proto_4d9b05dcb39b"

match = BekCPU.execute("BEK-MEM", "bek_mem_match", query="Cherche Bitcoin")
# → {"prototype_id": "proto_...", "score": 1.0}
```

### 4.4 — BEK-LOOP (apprentissage continu)

```python
BekCPU.execute("BEK-LOOP", "bek_loop_record",
    episode={"query": "news Bitcoin", "tier": "TIER_2", "success": True, "time_ms": 1240})

analysis = BekCPU.execute("BEK-LOOP", "bek_loop_analyze")
# → {"total": 13, "success_rate": 0.69, "by_tier": {...}}
```

### 4.5 — BEK-ECO (optimisation économique)

```python
decision = BekCPU.execute("BEK-ECO", "bek_eco_optimize",
    tier="TIER_2", query="Cherche news crypto")
# → {"decision": "proceed", "score": 0.805, "cost_estimate": 0.01}
```

### 4.6 — BEK-STAIR (anti-hallucination)

```python
toc = BekCPU.execute("BEK-STAIR", "bek_stair_build_toc",
    pages=[{"url": "...", "content": "..."}], query="Bitcoin")

validation = BekCPU.execute("BEK-STAIR", "bek_stair_validate",
    llm_response="...", toc_context=toc, pages=[...])
# → {"valid": True, "hallucinations": [], "score": 1.0}
```

---

## 5. LE REGISTRE

**Fichier :** `bek_core/registry.json`

**Format d'une entrée :**

```json
"BEK-REX": {
  "nom_complet": "Reflective EXecution",
  "version": "1.0",
  "module": "bek_core.rex.router",
  "brevet": "docs/brevets/BREVET_REX.md",
  "functions": {
    "bek_rex_route": {"params": ["query"]},
    "bek_rex_list_tiers": {"params": []}
  },
  "dependencies": [],
  "status": "active"
}
```

**Champs obligatoires :**

| Champ | Type | Rôle |
|---|---|---|
| `nom_complet` | string | Nom long de la brique |
| `version` | string | Version sémantique |
| `module` | string | Chemin Python (importlib) |
| `brevet` | string | Chemin relatif du brevet |
| `functions` | object | Nom → params |
| `dependencies` | array | Liste de `BEK-YYY` requis |
| `status` | string | `active`, `beta`, `deprecated` |

---

## 6. AJOUTER UNE BRIQUE

**Voir `docs/ADDING_A_BRICK.md`** — guide officiel complet (7 étapes, 15 minutes).

**En 30 secondes :**

1. Créer `bek_core/<nom_court>/` avec `__init__.py`, `MANIFEST.json`, `<nom>.py`, `BREVET_<BRIQUE>.md`
2. Ajouter l'entrée dans `registry.json`
3. Copier le brevet dans `docs/brevets/`
4. Tester avec `BekCPU.execute("BEK-XXX", "bek_xxx_action", ...)`

---

## 7. PREUVE D'EXÉCUTION

**Test officiel :**

```cmd
cd /d F:\workspacekimi
python demo.py
```

**Sortie :** 8 étapes (CPU existe → REX → FLUX → MEM → LOOP → ECO → Agent 15 lignes → Mapping 13 langages).

**Résultats clés :**
- ✅ 6 briques listées avec leurs brevets
- ✅ BEK-REX : 5/5 requêtes routées correctement
- ✅ BEK-FLUX : speedup 7.2x sur 8 tâches
- ✅ BEK-MEM : match score 1.00
- ✅ BEK-LOOP : 13 épisodes analysés
- ✅ BEK-ECO : score pondéré 0.805 sur 7 facteurs
- ✅ Agent complet en 15 lignes
- ✅ Mapping 13 langages

**Document complet :** `docs/BEK_LVC_PROOF.md`

---

## 8. MAPPING 13 LANGAGES

| Langage | Convention | Exemple |
|---|---|---|
| Python | snake_case | `BekCPU.execute("BEK-REX", "bek_rex_route", query="...")` |
| Java | camelCase | `BekCPU.execute("BEK-REX", "bekRexRoute", "query", "...")` |
| Kotlin | camelCase | `BekCPU.execute("BEK-REX", "bekRexRoute", "query", "...")` |
| Swift | camelCase | `BekCPU.execute("BEK-REX", "bekRexRoute", "query", "...")` |
| JavaScript | camelCase | `BekCPU.execute("BEK-REX", "bekRexRoute", "query", "...")` |
| TypeScript | camelCase | `BekCPU.execute("BEK-REX", "bekRexRoute", "query", "...")` |
| Rust | snake_case | `BekCPU::execute("BEK-REX", "bek_rex_route", "query", "...")` |
| Go | PascalCase | `BekCPU.Execute("BEK-REX", "BekRexRoute", "query", "...")` |
| C | snake_case | `bek_cpu_execute("BEK-REX", "bek_rex_route", "query", "...")` |
| C++ | snake_case | `BekCPU::execute("BEK-REX", "bek_rex_route", "query", "...")` |
| Zig | snake_case | `BekCPU.execute("BEK-REX", "bek_rex_route", "query", "...")` |
| Nim | snake_case | `BekCPU.execute("BEK-REX", "bek_rex_route", "query", "...")` |
| PHP | snake_case | `BekCPU::execute("BEK-REX", "bek_rex_route", "query", "...")` |

**L'abréviation reste identique dans les 13 langages.**

---

## 9. FICHIERS ASSOCIÉS

| Fichier | Rôle |
|---|---|
| `bek_core/cpu.py` | Classe BekCPU |
| `bek_core/registry.py` | Chargement du registre |
| `bek_core/registry.json` | Catalogue des briques |
| `bek_core/translator.py` | Résolution abréviation → module |
| `bek_core/README.md` | Documentation technique complète |
| `docs/BEK_LVC.md` | Référentiel universel |
| `docs/BEK_LVC_PROOF.md` | Preuve d'exécution |
| `docs/ADDING_A_BRICK.md` | Guide pour ajouter une brique |
| `docs/BRIQUES_REGISTRY.md` | Catalogue global des briques |
| `demo.py` | Démonstration (8 étapes) |
| `bek_core/<brique>/BREVET_<BRIQUE>.md` | Brevets individuels |
| `docs/brevets/BREVET_<BRIQUE>.md` | Copies centrales des brevets |

---

## 10. VERSION

**Version actuelle :** BEK-CPU-v1.0
**Date :** 2026-09-26
**Briques actives :** 6 (REX, FLUX, MEM, LOOP, ECO, STAIR)
**Dernière mise à jour :** Ajout BEK-STAIR + section `chat_modules/` + section `bek_core/`

---

**Signature :** BEK Project
**Date :** 2026-09-26