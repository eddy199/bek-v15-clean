# 🏛️ ADDING_A_BRICK — Guide officiel BEK-LVC

> **Comment ajouter une nouvelle brique au CPU logique virtuel BEK**
>
> Ce guide s'applique à toute nouvelle brique BEK-XXX.
> Durée moyenne : **15 minutes**.

**Version :** 1.0
**Date :** 2026-09-26
**Auteur :** BEK Project

---

## 🎯 En 30 secondes

Ajouter une brique BEK, c'est **5 étapes** :

1. Créer le dossier `bek_core/<brique>/`
2. Écrire le code (`<brique>.py`)
3. Écrire le manifeste (`MANIFEST.json`)
4. Écrire le brevet (`BREVET_<BRIQUE>.md`)
5. Enregistrer dans `registry.json`

Puis tester avec `BekCPU.execute(...)`.

---

## 📁 ÉTAPE 1 — Créer la structure du dossier

**Convention :** une brique = un dossier dans `bek_core/`.

```
bek_core/<nom_court>/
├── __init__.py
├── MANIFEST.json
├── <nom_court>.py       (ou un nom plus explicite : router.py, matcher.py, etc.)
└── BREVET_<BRIQUE>.md
```

**Exemples existants :**

| Brique | Dossier | Fichier principal |
|---|---|---|
| BEK-REX | `bek_core/rex/` | `router.py` |
| BEK-FLUX | `bek_core/flux/` | `executor.py` |
| BEK-MEM | `bek_core/mem/` | `matcher.py` |
| BEK-LOOP | `bek_core/loop/` | `recorder.py` |
| BEK-ECO | `bek_core/eco/` | `optimizer.py` |
| BEK-STAIR | `bek_core/stair/` | `toc_builder.py` |

**Règles de nommage :**

- Nom du dossier : **minuscules**, court, sans tiret (`mux`, `hermes`, `vision`)
- Fichier principal : nom descriptif (`router.py`, `matcher.py`, `client.py`)
- Brevet : `BREVET_<BRIQUE>.md` (majuscules)

---

## 📝 ÉTAPE 2 — Écrire le code de la brique

**Squelette obligatoire :**

```python
# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — <NOM COMPLET DE LA BRIQUE>
# ------------------------------------------------------------------------------
# 🏛️ BREVET : <BEK-XXX>-v1.0
# 📄 Doc : bek_core/<nom_court>/BREVET_<BRIQUE>.md
# 🎯 Rôle : <description courte>
# ------------------------------------------------------------------------------
# Auteur : BEK Project
# Version : 1.0
# Date : 2026-09-26
# ==============================================================================

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bek.core.<nom_court>")


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES
# ══════════════════════════════════════════════════════════════════════════════

BEK_<BRIQUE>_VERSION = "1.0.0"


# ══════════════════════════════════════════════════════════════════════════════
# FONCTIONS PUBLIQUES
# ══════════════════════════════════════════════════════════════════════════════

def bek_<nom_court>_<action>(param1: str, param2: int) -> Dict[str, Any]:
    """
    <Description de la fonction>.

    Args:
        param1: <description>
        param2: <description>

    Returns:
        Dict avec les résultats.
    """
    # Implémentation
    return {"status": "OK", "result": ...}
```

**Conventions de nommage des fonctions :**

| Type | Format | Exemple |
|---|---|---|
| Fonction publique | `bek_<brique>_<action>` | `bek_rex_route`, `bek_mem_store` |
| Classe publique | `Bek<Brique><Rôle>` | `BekStairToC`, `BekMemMatcher` |
| Constante | `BEK_<BRIQUE>_<NOM>` | `BEK_REX_KEYWORDS` |
| Variable privée | `_<nom>` | `_cache`, `_episodes` |

**Règles absolues :**

- ✅ Toutes les fonctions publiques sont préfixées `bek_<brique>_`
- ✅ Tous les retours sont des `Dict[str, Any]` ou types simples
- ✅ Le logger est nommé `bek.core.<nom_court>`
- ❌ Pas de `print()` dans le code de production
- ❌ Pas de dépendances lourdes (pas de pandas, pas de numpy)
- ❌ Pas d'appels réseau synchrones bloquants

---

## 📋 ÉTAPE 3 — Écrire `MANIFEST.json`

**Ce fichier contient les métadonnées étendues de la brique.**

**Format :**

```json
{
  "abreviation": "BEK-XXX",
  "nom_complet": "<Nom complet>",
  "nom_court": "XXX",
  "sous_titre": "<Sous-titre>",
  "version": "1.0",
  "categorie": "Instruction principale",
  "statut": "active",
  "priorite": "critique",
  "auteur": "BEK Project",
  "date_creation": "2026-09-26",
  "module": "bek_core.<nom_court>.<fichier>",
  "brevet": "bek_core/<nom_court>/BREVET_<BRIQUE>.md",
  "description_courte": "<1 phrase>",
  "functions": [
    "bek_<brique>_<action1>",
    "bek_<brique>_<action2>"
  ],
  "dependencies": [],
  "utilise_par": []
}
```

**Champs obligatoires :**

| Champ | Valeurs possibles |
|---|---|
| `abreviation` | `BEK-XXX` (majuscules) |
| `nom_complet` | Texte libre |
| `version` | `1.0`, `1.1`, etc. |
| `categorie` | `Instruction principale`, `Instruction de validation`, `Brique`, `Agent` |
| `statut` | `active`, `beta`, `deprecated` |
| `priorite` | `critique`, `haute`, `moyenne`, `basse` |
| `module` | Chemin Python complet |
| `brevet` | Chemin relatif depuis la racine |
| `functions` | Liste des noms exacts |
| `dependencies` | Liste des `BEK-YYY` requis |

---

## 🏛️ ÉTAPE 4 — Écrire `BREVET_<BRIQUE>.md`

**Utilisez `docs/brevets/BREVET_TEMPLATE.md` comme point de départ.**

**Structure minimale :**

```markdown
# BREVET BEK-XXX
## <Nom complet> — <Sous-titre>

**Code brevet :** BEK-XXX-v1.0
**Version :** 1.0
**Date :** 2026-09-26
**Auteur :** BEK Project

---

## 1. IDENTIFICATION

| Champ | Valeur |
|---|---|
| **Abréviation** | BEK-XXX |
| **Nom long** | <Nom complet> |
| **Version** | 1.0 |
| **Catégorie** | <Instruction / Brique / Agent> |
| **Statut** | ✅ Actif |
| **Priorité** | 🔴 Critique |

---

## 2. PROBLÈME RÉSOLU

<Décrire le problème concret que la brique résout.>

---

## 3. SOLUTION UNIQUE

<Décrire la solution apportée, en quoi elle est différente.>

---

## 4. PREUVE D'EXÉCUTION

<Sortie d'un test réel (demo, unit test, log).>

---

## 5. API PUBLIQUE

```python
from bek_core import BekCPU

result = BekCPU.execute(
    "BEK-XXX",
    "bek_xxx_action",
    param1="...",
)
```

---

## 6. FICHIERS ASSOCIÉS

| Fichier | Rôle |
|---|---|
| `bek_core/xxx/__init__.py` | Exports publics |
| `bek_core/xxx/xxx.py` | Implémentation |
| `bek_core/xxx/MANIFEST.json` | Métadonnées |
| `bek_core/registry.json` | Référence dans le registre |

---

## 7. DIFFÉRENCE AVEC L'ÉTAT DE L'ART

| Solution existante | Limitation | Notre différence |
|---|---|---|
| ... | ... | ... |

---

**Signature :** BEK Project
**Date :** 2026-09-26
```

**Où placer le brevet ?**

- **Obligatoire :** `bek_core/<nom_court>/BREVET_<BRIQUE>.md`
- **Obligatoire :** `docs/brevets/BREVET_<BRIQUE>.md` (copie)

**Pourquoi deux copies ?**

- `bek_core/<nom_court>/` → le brevet voyage avec le code (si on copie le dossier, tout est inclus)
- `docs/brevets/` → catalogue central (référencé par `registry.json`)

**Commande de copie après création :**

```cmd
copy bek_core\<nom_court>\BREVET_<BRIQUE>.md docs\brevets\BREVET_<BRIQUE>.md
```

---

## 📝 ÉTAPE 5 — Enregistrer dans `registry.json`

**Ouvrez `F:\workspacekimi\bek_core\registry.json`.**

**Ajoutez votre brique dans `"briques"`, en respectant l'ordre alphabétique.**

**Format exact (Style 1 — compact) :**

```json
"BEK-XXX": {
  "nom_complet": "<Nom complet>",
  "version": "1.0",
  "module": "bek_core.<nom_court>.<fichier>",
  "brevet": "docs/brevets/BREVET_<BRIQUE>.md",
  "functions": {
    "bek_<brique>_<action1>": {"params": ["param1", "param2"]},
    "bek_<brique>_<action2>": {"params": []}
  },
  "dependencies": [],
  "status": "active"
}
```

⚠️ **Points d'attention :**

- La virgule après `}` de chaque brique **sauf** la dernière
- Les noms de fonctions doivent être **exacts** (vérifiez dans votre `.py`)
- L'ordre des params dans `"params"` doit correspondre aux **arguments keyword** de la fonction
- Si la fonction accepte `**kwargs` (comme `bek_loop_record(episode=...)`), listez juste les noms des paramètres

---

## ✅ ÉTAPE 6 — Tester la nouvelle brique

**3 commandes de validation :**

**Test 1 — La brique est dans le registre**

```cmd
cd /d F:\workspacekimi
python -c "from bek_core import BekCPU; print('BEK-XXX' in BekCPU.list())"
```

**Sortie attendue :** `True`

**Test 2 — Les fonctions sont accessibles**

```cmd
python -c "from bek_core import BekCPU; print(BekCPU.list_functions('BEK-XXX'))"
```

**Sortie attendue :** `['bek_xxx_action1', 'bek_xxx_action2']`

**Test 3 — La brique s'exécute**

```cmd
python -c "from bek_core import BekCPU; print(BekCPU.execute('BEK-XXX', 'bek_xxx_action1', param1='test'))"
```

**Sortie attendue :** un dict avec les résultats.

---

## 🔬 ÉTAPE 7 — Exemple complet : créer `BEK-DEMO` en 15 minutes

**Objectif :** créer une brique minimale `BEK-DEMO` qui expose une fonction `bek_demo_hello`.

### 7.1 — Créer le dossier

```cmd
mkdir F:\workspacekimi\bek_core\demo
```

### 7.2 — Créer `bek_core/demo/__init__.py`

```python
# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — BEK-DEMO (Brique d'exemple)
# ------------------------------------------------------------------------------
# 🏛️ BREVET : BEK-DEMO-v1.0
# 📄 Doc : bek_core/demo/BREVET_DEMO.md
# 🎯 Rôle : Démontrer comment créer une brique BEK
# ------------------------------------------------------------------------------
# Auteur : BEK Project
# Version : 1.0
# Date : 2026-09-26
# ==============================================================================

from .demo import bek_demo_hello, BEK_DEMO_VERSION

__all__ = ["bek_demo_hello", "BEK_DEMO_VERSION"]
```

### 7.3 — Créer `bek_core/demo/demo.py`

```python
# -*- coding: utf-8 -*-
# ==============================================================================
# BEK-v18 — BEK-DEMO
# ------------------------------------------------------------------------------
# 🏛️ BREVET : BEK-DEMO-v1.0
# 📄 Doc : bek_core/demo/BREVET_DEMO.md
# 🎯 Rôle : Brique d'exemple
# ==============================================================================

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger("bek.core.demo")

BEK_DEMO_VERSION = "1.0.0"


def bek_demo_hello(name: str = "world") -> Dict[str, Any]:
    """
    Dit bonjour à quelqu'un.

    Args:
        name: Le nom à saluer

    Returns:
        Dict avec le message et le statut.
    """
    message = f"Hello, {name}!"
    logger.info("BEK-DEMO : %s", message)
    return {"status": "OK", "message": message}
```

### 7.4 — Créer `bek_core/demo/MANIFEST.json`

```json
{
  "abreviation": "BEK-DEMO",
  "nom_complet": "BEK Demo",
  "nom_court": "DEMO",
  "sous_titre": "Brique d'exemple",
  "version": "1.0",
  "categorie": "Brique",
  "statut": "active",
  "priorite": "basse",
  "auteur": "BEK Project",
  "date_creation": "2026-09-26",
  "module": "bek_core.demo.demo",
  "brevet": "bek_core/demo/BREVET_DEMO.md",
  "description_courte": "Démontre comment créer une brique BEK",
  "functions": ["bek_demo_hello"],
  "dependencies": [],
  "utilise_par": []
}
```

### 7.5 — Créer `bek_core/demo/BREVET_DEMO.md`

```markdown
# BREVET BEK-DEMO
## Brique d'exemple — Comment créer une brique BEK

**Code brevet :** BEK-DEMO-v1.0
**Version :** 1.0
**Date :** 2026-09-26
**Auteur :** BEK Project

---

## 1. IDENTIFICATION

| Champ | Valeur |
|---|---|
| **Abréviation** | BEK-DEMO |
| **Version** | 1.0 |
| **Catégorie** | Brique |
| **Statut** | ✅ Actif |

---

## 2. PROBLÈME RÉSOLU

Aucun. Cette brique sert uniquement d'exemple pédagogique.

---

## 3. SOLUTION UNIQUE

Une fonction `bek_demo_hello` qui retourne un message de salutation.

---

## 4. PREUVE D'EXÉCUTION

```python
BekCPU.execute("BEK-DEMO", "bek_demo_hello", name="BEK")
# → {"status": "OK", "message": "Hello, BEK!"}
```

---

**Signature :** BEK Project
```

### 7.6 — Ajouter dans `registry.json`

```json
"BEK-DEMO": {
  "nom_complet": "BEK Demo",
  "version": "1.0",
  "module": "bek_core.demo.demo",
  "brevet": "docs/brevets/BREVET_DEMO.md",
  "functions": {
    "bek_demo_hello": {"params": ["name"]}
  },
  "dependencies": [],
  "status": "active"
}
```

### 7.7 — Copier le brevet

```cmd
copy F:\workspacekimi\bek_core\demo\BREVET_DEMO.md F:\workspacekimi\docs\brevets\BREVET_DEMO.md
```

### 7.8 — Tester

```cmd
cd /d F:\workspacekimi
python -c "from bek_core import BekCPU; print(BekCPU.execute('BEK-DEMO', 'bek_demo_hello', name='BEK'))"
```

**Sortie attendue :**

```
{'status': 'OK', 'message': 'Hello, BEK!'}
```

**Voilà. Une nouvelle brique BEK en 15 minutes.** ✅

---

## 📋 Checklist finale

Avant de considérer une brique comme terminée :

- [ ] Dossier `bek_core/<nom_court>/` créé
- [ ] Fichier `__init__.py` créé avec les exports
- [ ] Fichier `<nom_court>.py` créé avec l'en-tête brevet
- [ ] Fichier `MANIFEST.json` créé
- [ ] Fichier `BREVET_<BRIQUE>.md` créé dans `bek_core/<nom_court>/`
- [ ] Copie du brevet dans `docs/brevets/`
- [ ] Entrée ajoutée dans `registry.json` (ordre alphabétique)
- [ ] Test `BekCPU.list()` retourne la nouvelle brique
- [ ] Test `BekCPU.list_functions(...)` retourne les bonnes fonctions
- [ ] Test `BekCPU.execute(...)` s'exécute sans erreur

**Si tout est coché → la brique est officiellement intégrée au standard BEK-LVC.** 🏛️

---

## 🚫 Erreurs fréquentes

| Erreur | Cause | Solution |
|---|---|---|
| `KeyError: 'BEK-XXX'` | Entrée absente de `registry.json` | Vérifier l'entrée + l'ordre alphabétique |
| `ImportError: cannot import name 'bek_xxx_action'` | Nom de fonction inexact | Vérifier le `def` dans le `.py` |
| `ModuleNotFoundError: No module named 'bek_core.xxx'` | `__init__.py` manquant | Créer un `__init__.py` vide |
| `ValueError: paramètre requis manquant` | Kwarg absent dans `BekCPU.execute(...)` | Vérifier `"params"` dans `registry.json` |
| Brique invisible dans `BekCPU.list()` | JSON invalide (virgule manquante) | Valider avec `python -m json.tool registry.json` |

---

## 🔗 Voir aussi

- `bek_core/README.md` — Documentation du CPU
- `docs/BEK_LVC.md` — Référentiel universel
- `docs/BEK_CPU.md` — Documentation technique
- `docs/brevets/BREVET_TEMPLATE.md` — Template de brevet
- `bek_core/registry.json` — Registre des briques
- `demo.py` — Démonstration complète

---

**Signature :** BEK Project
**Date :** 2026-09-26