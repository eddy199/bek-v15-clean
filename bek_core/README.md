# 🏛️ BEK-Core — Le CPU Logique Virtuel

> **BEK-CPU-v1.0** — Une abréviation devient un appel de fonction exécutable.

---

## 🎯 En 30 secondes

**BEK-Core** est le cœur du référentiel **BEK-LVC**. Il transforme une **abréviation** (`BEK-REX`) en **appel Python exécutable**.

```python
from bek_core import BekCPU

result = BekCPU.execute("BEK-REX", "bek_rex_route", query="Cherche Bitcoin")
# → {"tier": "TIER_2", "confidence": 0.95, ...}