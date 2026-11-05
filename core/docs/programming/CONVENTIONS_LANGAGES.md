# BEK — Conventions par Langage
## Mapping 13 Langages

**Version :** 1.0
**Date :** 2026-09-23
**Auteur :** BEK Project

---

## 1. PRINCIPE

Un même concept BEK se traduit dans 13 langages avec la même sémantique, mais la syntaxe native de chaque langage.

---

## 2. LES 13 LANGAGES SUPPORTÉS

| # | Langage | Version min | Statut |
|---|---|---|---|
| 1 | Python | 3.10+ | ✅ Supporté |
| 2 | Java | 17+ | ✅ Supporté |
| 3 | Kotlin | 1.9+ | ✅ Supporté |
| 4 | Swift | 5.9+ | ✅ Supporté |
| 5 | JavaScript | ES2022+ | ✅ Supporté |
| 6 | TypeScript | 5.0+ | ✅ Supporté |
| 7 | Rust | 1.75+ | ✅ Supporté |
| 8 | Go | 1.21+ | ✅ Supporté |
| 9 | C | C17+ | ✅ Supporté |
| 10 | C++ | C++20+ | ✅ Supporté |
| 11 | Zig | 0.11+ | ✅ Supporté |
| 12 | Nim | 2.0+ | ✅ Supporté |
| 13 | PHP | 8.2+ | ✅ Supporté |

---

## 3. TABLEAU DE CORRESPONDANCE COMPLET

### 3.1 — Fonctions

| Langage | Convention | Exemple |
|---|---|---|
| Python | `snake_case` | `bek_rex_route()` |
| Java | `camelCase` | `bekRexRoute()` |
| Kotlin | `camelCase` | `bekRexRoute()` |
| Swift | `camelCase` | `bekRexRoute()` |
| JavaScript | `camelCase` | `bekRexRoute()` |
| TypeScript | `camelCase` | `bekRexRoute()` |
| Rust | `snake_case` | `bek_rex_route()` |
| Go | `PascalCase` | `BekRexRoute()` |
| C | `snake_case` | `bek_rex_route()` |
| C++ | `snake_case` | `bek_rex_route()` |
| Zig | `snake_case` | `bek_rex_route()` |
| Nim | `snake_case` | `bek_rex_route()` |
| PHP | `snake_case` | `bek_rex_route()` |

### 3.2 — Constantes

**Tous les langages :** `BEK_<ABREV>_<NOM>` (SCREAMING_SNAKE_CASE)

### 3.3 — Classes

| Langage | Convention | Exemple |
|---|---|---|
| Python | `PascalCase` | `BekRexRouter` |
| Java | `PascalCase` | `BekRexRouter` |
| Kotlin | `PascalCase` | `BekRexRouter` |
| Swift | `PascalCase` | `BekRexRouter` |
| JavaScript | `PascalCase` | `BekRexRouter` |
| TypeScript | `PascalCase` | `BekRexRouter` |
| Rust | `PascalCase` | `BekRexRouter` |
| Go | `PascalCase` | `BekRexRouter` |
| C | `struct PascalCase` | `BekRexRouter` |
| C++ | `PascalCase` | `BekRexRouter` |
| Zig | `PascalCase` | `BekRexRouter` |
| Nim | `PascalCase` | `BekRexRouter` |
| PHP | `PascalCase` | `BekRexRouter` |

---

## 4. EXEMPLES PAR LANGAGE

### 4.1 — Python

```python
from bek_core.rex import BekRexRouter

BEK_REX_DEFAULT_CONFIDENCE = 0.6

def bek_rex_route(query: str, options: dict = None) -> dict:
    """Route une requête vers le tier optimal."""
    return BekRexRouter.route(query, options)