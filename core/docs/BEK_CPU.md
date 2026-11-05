# 🖥️ BEK CPU LOGIQUE VIRTUEL (v18.6)

> Document décrivant le CPU Logique Virtuel de BEK-v18.

## 🎯 PRÉSENTATION

Le BEK CPU est une couche d'abstraction au-dessus des LLM qui permet
d'exécuter des actions cognitives complexes (routing, cache, mémoire,
apprentissage) de manière unifiée.

## 🧱 LES 6 BRIQUES FONDAMENTALES

| Brique | Rôle |
|---|---|
| BEK-REX | Routage intelligent (5 tiers : TIER_0 → TIER_4) |
| BEK-FLUX | Parallélisation DAG |
| BEK-MEM | Mémoire par prototypes |
| BEK-LOOP | Apprentissage continu (latences) |
| BEK-ECO | Économie de calcul (cache) |
| BEK-STAIR | Anti-hallucination (validation ToC) |

## 🆕 NOUVELLES BRIQUES v18.6

| Brique | Fichier | Rôle |
|---|---|---|
| HINDSIGHT | hindsight_memory.py | Mémoire structurée long-terme |
| MEMORY COORDINATOR | memory_coordinator.py | Orchestration 4 couches |
| FEEDBACK MEMORY | feedback_memory.py | Apprentissage utilisateur |

## 🏗️ ARCHITECTURE GLOBALE

    UTILISATEUR
        ↓
    routers/chat.py
        ↓ coordinate_memories_async()
    streaming.py (v1.3.3)
        - BEK-REX : routage
        - BEK-ECO : cache
        - LLM : génération
        - BEK-LOOP : feedback
        - HINDSIGHT : retain
        ↓
    4 couches MÉMOIRE (via Coordinator)
        - Pinecone, ChromaDB, Supabase, Hindsight

## 🔌 API

### BekCPU

```python
from bek_core import BekCPU
result = BekCPU.execute('BEK-REX', 'bek_rex_action', query='Bonjour')
```

### BEK-REX

```python
from bek_core import rex
tier = rex.route('Bonjour')
```

### BEK-ECO

```python
from bek_core import eco
cached = eco.check_cache('Bonjour')
```

### BEK-LOOP

```python
from bek_core import loop
loop.record_episode(query='Bonjour', tier='TIER_0', success=True, time_ms=1200)
```

### BEK-MEM

```python
from bek_core import mem
mem.store_prototype(query='...', method='...', result={...})
```

## 📊 FLUX

    1. UTILISATEUR envoie requête
    2. routers/chat.py : coordinate_memories_async + goap_planner
    3. streaming.py : BEK-REX.route + BEK-ECO.check_cache + LLM
    4. finally : BEK-LOOP.record + HINDSIGHT.retain
    5. RÉPONSE à l'utilisateur

## 🔧 CONFIG (env.txt)

    BEK_ECO_CACHE_ENABLED=true
    BEK_MEM_ENABLED=true
    BEK_LOOP_ENABLED=true
    BEK_FIX_SPACING_ENABLED=true
    BEK_HINDSIGHT_ENABLED=true

## 📈 MÉTRIQUES

| Métrique | Valeur |
|---|---|
| Réponse cache HIT | < 1s |
| Réponse cache MISS | 3-15s |
| Temps Coordinator | 2-15s |
| Skills chargés | 5193 |
| Outils Hermes | 33 |
| Nerfs actifs | 12 |

## 📚 RÉFÉRENCES

- bek_core/ : implémentation briques
- memory_coordinator.py
- hindsight_memory.py
- feedback_memory.py
- docs/MEMORY_ARCHITECTURE.md
- docs/FEEDBACK_SYSTEM.md

---

Version : 18.6
Date : 2026-09-29
Auteur : BEK Project
