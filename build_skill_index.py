# build_skill_index.py
import json
import re
from pathlib import Path
from skill_registry import SkillRegistry
from collections import Counter

# 1. Initialiser le registre
registry = SkillRegistry()
registry.load_skills()
all_skills = registry.list_all_skills()

# 2. Mapping ULTRA-LARGE basé sur le NOM du fichier (qui contient des mots-clés)
CATEGORIES = {
    "CODE": [
        "code", "python", "js", "react", "angular", "vue", "swift", "kotlin",
        "java", "rust", "backend", "frontend", "pattern", "api", "dev",
        "coder", "developer", "engineering", "architecture", "refactor",
        "agentic", "design", "ui", "ux", "css", "html", "typescript",
        "django", "flask", "fastapi", "nodejs", "nestjs", "go-patterns",
        "rust-patterns", "java-coding", "kotlin", "swiftui", "flutter",
        "laravel", "php", "ruby", "rails", "vue-patterns", "react-native",
        "expo", "nextjs", "nuxt", "svelte", "solid", "remix", "astro"
    ],
    "SECURITY": [
        "security", "compliance", "scan", "audit", "harden", "vpn",
        "sandbox", "vulnerab", "hipaa", "gdpr", "defi", "pentest",
        "guard", "auth", "encryption", "crypto", "jwt", "oauth", "iam",
        "firewall", "waf", "zero-trust", "soc2", "pci"
    ],
    "DATA": [
        "database", "data", "sql", "migration", "logistic", "schema",
        "duckdb", "postgres", "mysql", "sqlite", "etl", "pipeline",
        "analytics", "bi", "warehouse", "snowflake", "bigquery", "dbt",
        "airflow", "kafka", "streaming", "data-science", "ml-", "pandas"
    ],
    "AGENT": [
        "agent", "orchestration", "team", "recursive", "context",
        "prompt", "memory", "skill", "swarm", "llm", "ai-",
        "cognitive", "reasoning", "planning", "multi-agent", "tool-use",
        "function-calling", "rag", "embedding", "vector", "retrieval"
    ],
    "DEVOPS": [
        "kubernetes", "docker", "homelab", "dns", "network", "deploy",
        "ci", "cd", "terraform", "ansible", "helm", "k8s", "linux",
        "gitops", "argocd", "flux", "prometheus", "grafana", "monitoring",
        "observability", "sre", "infrastructure", "cloud"
    ],
    "WEB": [
        "web", "search", "scrape", "crawl", "seo", "headless",
        "browser", "playwright", "puppeteer", "selenium", "scraping"
    ],
    "VISION": [
        "vision", "image", "video", "whisper", "agnes", "veo",
        "midjourney", "stable-diffusion", "multimodal", "ocr", "cv",
        "segmentation", "detection", "gan", "diffusion"
    ],
    "TESTING": [
        "test", "qa", "e2e", "unit", "integration", "playwright-test",
        "cypress", "jest", "pytest", "coverage", "mutation"
    ],
    "DOCS": [
        "doc", "readme", "wiki", "guide", "tutorial", "onboarding",
        "changelog", "spec", "rfc", "adr"
    ],
}

def get_category(skill_name: str, description: str) -> str:
    # On combine nom + description pour maximiser les chances
    text = f"{skill_name} {description}".lower()
    for cat, keywords in CATEGORIES.items():
        if any(k in text for k in keywords):
            return cat
    return "OTHER"

# 3. Construire l'index
index = []
for s in all_skills:
    index.append({
        "skill_id": s["skill_id"],
        "name": s["name"],
        "description": s["description"],
        "category": get_category(s["name"], s["description"]),
        "risk_level": s.get("risk_level", "L1"),
        "command": s.get("command", ""),
        "prompt": s.get("prompt", "")
    })

# 4. Sauvegarder
output_path = Path(__file__).resolve().parent / "skills_index.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(index, f, indent=2, ensure_ascii=False)

# 5. Stats
cats = Counter(s["category"] for s in index)
print(f"✅ Index généré avec {len(index)} skills dans {output_path}")
print(f"📊 Répartition : {dict(cats)}")