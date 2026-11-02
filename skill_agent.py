# skill_agent.py
import json
import logging
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger("bek.skill_agent")

class SkillAgent:
    def __init__(self, index_path: str = "skills_index.json"):
        self.index_path = Path(index_path)
        self.skills_db = self._load_index()

    def _load_index(self) -> List[Dict[str, Any]]:
        if not self.index_path.exists():
            logger.error(f"[SkillAgent] Index introuvable : {self.index_path}")
            return []
        with open(self.index_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _detect_category(self, query: str) -> str:
        """Détection basique de la catégorie basée sur la requête."""
        q = query.lower()
        if any(w in q for w in ["code", "fix", "refactor", "bug", "optimise", "optimize", "python", "javascript"]): 
            return "CODE"
        if any(w in q for w in ["security", "audit", "vulnerable", "pirate"]): 
            return "SECURITY"
        if any(w in q for w in ["data", "database", "sql", "migration"]): 
            return "DATA"
        if any(w in q for w in ["agent", "orchestre", "team", "skill"]): 
            return "AGENT"
        if any(w in q for w in ["web", "search", "scrape", "crawl"]): 
            return "WEB"
        if any(w in q for w in ["image", "video", "vision"]): 
            return "VISION"
        if any(w in q for w in ["test", "qa"]): 
            return "TESTING"
        if any(w in q for w in ["deploy", "docker", "kubernetes"]): 
            return "DEVOPS"
        return "OTHER"

    def find_skills(self, query: str) -> List[Dict[str, Any]]:
        """
        Recherche les compétences pertinentes via l'index JSON.
        Si aucun match, fait un fallback vers les top skills de la catégorie.
        """
        category = self._detect_category(query)
        logger.info(f"[SkillAgent] Catégorie détectée : {category}")
        
        # On garde uniquement les mots significatifs (>3 caractères)
        q_words = [w for w in query.lower().split() if len(w) > 3]
        
        # 1. Chercher les skills qui matchent les mots-clés
        matched = []
        for skill in self.skills_db:
            if skill.get("category") != category:
                continue
            
            text = f"{skill.get('name', '')} {skill.get('description', '')}".lower()
            score = sum(1 for w in q_words if w in text)
            
            if score > 0:
                matched.append((score, skill))
        
        # 2. FALLBACK : si aucun match, prendre les top skills de la catégorie
        if not matched:
            logger.warning(f"[SkillAgent] Aucun match pour '{query}' dans {category}. Fallback vers les top skills.")
            all_in_category = [s for s in self.skills_db if s.get("category") == category]
            
            # Priorité aux skills génériques et utiles
            priority_keywords = ["reviewer", "architect", "simplifier", "explorer", "resolver", "patterns", "standards"]
            
            def sort_key(s):
                name = s.get("name", "").lower()
                has_priority = any(k in name for k in priority_keywords)
                return (0 if has_priority else 1, len(name))
            
            all_in_category.sort(key=sort_key)
            matched = [(0, s) for s in all_in_category[:3]]
        
        # 3. Trier par score décroissant et prendre le top 3
        matched.sort(key=lambda x: x[0], reverse=True)
        return [m[1] for m in matched[:3]]

    def validate_security(self, skill: Dict[str, Any]) -> bool:
        """
        On connecte ça à ton SecurityGuard de Hermes.
        Pour l'instant, on bloque tout ce qui n'est pas L1 sans approbation.
        """
        risk = skill.get("risk_level", "L1")
        if risk == "L3":
            logger.warning(f"[SkillAgent] 🔒 La skill '{skill['name']}' nécessite une approbation manuelle (L3).")
            return False
        return True

    def get_action_plan(self, query: str) -> Dict[str, Any]:
        """
        Méthode principale appelée par l'Orchestrateur.
        """
        logger.info(f"[SkillAgent] Analyse de la requête : {query[:50]}...")
        
        # 1. Trouver les candidats
        candidates = self.find_skills(query)
        
        # 2. Valider la sécurité
        validated = []
        for skill in candidates:
            if self.validate_security(skill):
                validated.append(skill)
            else:
                logger.warning(f"[SkillAgent] Rejet de {skill['name']} pour raison de sécurité.")

        # 3. Retourner le plan d'action
        return {
            "query": query,
            "category": self._detect_category(query),
            "skills_found": len(validated),
            "selected_skills": validated
        }