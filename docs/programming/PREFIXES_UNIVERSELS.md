# BEK — Préfixes Universels
## Conventions de nommage inter-langages

**Version :** 1.0
**Date :** 2026-09-23
**Auteur :** BEK Project

---

## 1. PRINCIPE

Un développeur qui lit du code BEK en Python doit pouvoir reconnaître instantanément le même concept en Java, Rust, Go, ou JavaScript.

**Règle :** le nom change de casse selon le langage, mais **le préfixe BEK reste identique**.

---

## 2. LES 4 PRÉFIXES DE BASE

| Préfixe | Signification | Exemple |
|---|---|---|
| `bek_` | Fonction BEK | `bek_rex_route()` |
| `BEK_` | Constante BEK | `BEK_REX_TIERS` |
| `Bek` | Classe BEK | `BekRexRouter` |
| `bek` | Module/variable | `bek_core.rex` |

---

## 3. PRÉFIXES PAR CATÉGORIE

| Catégorie | Préfixe | Exemple |
|---|---|---|
| **Instruction principale** | `bek_<abrev>_` | `bek_rex_route()` |
| **Brique** | `bek_<abrev>_` | `bek_web_sync()` |
| **Agent** | `bek_agent_<nom>_` | `bek_agent_v18_chat()` |
| **Utilitaire** | `bek_util_` | `bek_util_log()` |
| **Test** | `test_bek_` | `test_bek_rex.py` |
| **Constante** | `BEK_<ABREV>_` | `BEK_REX_TIERS` |
| **Classe** | `Bek<Nom>` | `BekRexRouter` |

---

## 4. RÈGLES DE NOMMAGE

### 4.1 — Fonctions

**Format :** `bek_<abrev>_<action>`

**Exemples :**
```python
bek_rex_route()      # BEK-REX → route
bek_flux_run()       # BEK-FLUX → run
bek_mem_match()      # BEK-MEM → match
bek_loop_record()    # BEK-LOOP → record
bek_eco_optimize()   # BEK-ECO → optimize