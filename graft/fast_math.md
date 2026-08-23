---
covers: []
---
# fast_math.py

- HyperLogLog · class · L7-L46 — class HyperLogLog
- __init__ · method · L12-L16 — def __init__(self, b: int = 6)
- _get_alpha · method · L18-L25 — def _get_alpha(self, m: int) -> float
- _hash · method · L27-L28 — def _hash(self, val: str) -> int
- add · method · L30-L35 — def add(self, val: str)
- count · method · L37-L46 — def count(self) -> int
- MinHashSimilarity · class · L49-L104 — class MinHashSimilarity
- __init__ · method · L54-L60 — def __init__(self, num_perm: int = 64)
- _shingle · method · L62-L68 — def _shingle(self, text: str) -> Set[str]
- compute_signature · method · L70-L84 — def compute_signature(self, text: str) -> list
- estimate_similarity · method · L86-L90 — def estimate_similarity(self, sig1: list, sig2: list) -> float
- evaluate_route · method · L92-L104 — def evaluate_route(self, similarity: float) -> Tuple[str, str]
