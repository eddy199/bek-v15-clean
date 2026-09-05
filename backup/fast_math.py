 
import hashlib
import math
import re
from typing import Set, Tuple

class HyperLogLog:
    """
    Estimateur probabiliste de cardinalité (nombre d'éléments uniques)
    à très faible consommation mémoire et temps constant.
    """
    def __init__(self, b: int = 6):
        self.b = b
        self.m = 1 << b
        self.registers = [0] * self.m
        self.alpha_m = self._get_alpha(self.m)

    def _get_alpha(self, m: int) -> float:
        if m == 16:
            return 0.673
        elif m == 32:
            return 0.697
        elif m == 64:
            return 0.709
        return 0.7213 / (1.0 + 1.079 / m)

    def _hash(self, val: str) -> int:
        return int(hashlib.sha256(val.encode('utf-8')).hexdigest(), 16)

    def add(self, val: str):
        x = self._hash(val)
        j = x & (self.m - 1)
        w = x >> self.b
        rho = (w ^ (w - 1)).bit_length() if w != 0 else 64 - self.b
        self.registers[j] = max(self.registers[j], rho)

    def count(self) -> int:
        z = sum(2.0 ** (-reg) for reg in self.registers)
        e = self.alpha_m * (self.m ** 2) / z
        
        # Corrections pour petites valeurs
        if e <= 2.5 * self.m:
            v = self.registers.count(0)
            if v != 0:
                e = self.m * math.log(self.m / v)
        return int(e)


class MinHashSimilarity:
    """
    Calculateur de similarité instantanée MinHash avec contrôle adaptatif
    selon les seuils de la spécification BEK-v15.2.
    """
    def __init__(self, num_perm: int = 64):
        self.num_perm = num_perm
        self.prime = 4294967311
        self.perms = [
            ((i * 10007 + 12345) % self.prime, (i * 24681 + 6789) % self.prime)
            for i in range(self.num_perm)
        ]

    def _shingle(self, text: str) -> Set[str]:
        words = re.findall(r'\w+', text.lower())
        if not words:
            return set()
        if len(words) == 1:
            return {words[0]}
        return {' '.join(words[i:i+2]) for i in range(len(words) - 1)}

    def compute_signature(self, text: str) -> list:
        shingles = self._shingle(text)
        if not shingles:
            return [0] * self.num_perm

        signature = []
        for a, b in self.perms:
            min_val = float('inf')
            for s in shingles:
                h = int(hashlib.md5(s.encode('utf-8')).hexdigest()[:8], 16)
                val = (a * h + b) % self.prime
                if val < min_val:
                    min_val = val
            signature.append(min_val)
        return signature

    def estimate_similarity(self, sig1: list, sig2: list) -> float:
        if not sig1 or not sig2 or len(sig1) != len(sig2):
            return 0.0
        matches = sum(1 for a, b in zip(sig1, sig2) if a == b)
        return matches / len(sig1)

    def evaluate_route(self, similarity: float) -> Tuple[str, str]:
        """
        Application des seuils définis par le référentiel BEK-v15.2 :
        - > 0.9      : Traitement léger direct (Cache Spider)
        - 0.7 à 0.9  : Échantillonnage à 10%
        - <= 0.7     : Traitement exact à 100% (RAG + LLM complet)
        """
        if similarity > 0.9:
            return "LIGHT_DIRECT", "Similarité forte (>0.9) - Routage Cache Spider"
        elif similarity > 0.7:
            return "SAMPLE_10", "Similarité moyenne (0.7-0.9) - Échantillonnage 10%"
        else:
            return "EXACT_FULL", "Similarité faible (<=0.7) - Traitement exact 100%"


if __name__ == "__main__":
    print("--- TEST UNITAIRE FAST_MATH BEK-v15.2 ---")
    
    # 1. Test HyperLogLog
    hll = HyperLogLog()
    for word in ["contact", "deal", "task", "contact", "deal", "lead"]:
        hll.add(word)
    print(f"Estimation éléments uniques (HLL) : {hll.count()} (Attendu approx : 4)")

    # 2. Test MinHash
    minhash = MinHashSimilarity()
    text_a = "Ajoute un contact Karim avec email karim@mail.com"
    text_b = "Ajoute un contact Karim avec email karim@mail.com"
    text_c = "Crée un contrat deal de 15000 dollars"

    sig_a = minhash.compute_signature(text_a)
    sig_b = minhash.compute_signature(text_b)
    sig_c = minhash.compute_signature(text_c)

    sim_ab = minhash.estimate_similarity(sig_a, sig_b)
    route_ab, desc_ab = minhash.evaluate_route(sim_ab)
    print(f"Sim(A, B) : {sim_ab:.2f} -> {route_ab} ({desc_ab})")

    sim_ac = minhash.estimate_similarity(sig_a, sig_c)
    route_ac, desc_ac = minhash.evaluate_route(sim_ac)
    print(f"Sim(A, C) : {sim_ac:.2f} -> {route_ac} ({desc_ac})")