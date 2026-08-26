# web_agent.py - Agent Web Ultra-Puissant & Responsable pour BEK-v15.2
import os
import re
import logging
import requests
from bs4 import BeautifulSoup
from typing import List, Dict
from sqlalchemy import text

from memory import get_db_connection, save_to_memory

logger = logging.getLogger(__name__)

class WebAgent:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7'
        }

    def normalize_email(self, email: str) -> str:
        return email.strip().lower() if email else ""

    def normalize_phone(self, phone: str) -> str:
        if not phone:
            return ""
        return re.sub(r"\D", "", phone)  # Garde uniquement les chiffres (format E.164 simplifié)

    def strip_title(self, title: str) -> str:
        return title.strip().title() if title else ""

    def map_company_name(self, company: str) -> str:
        if not company:
            return "Indépendant / Non spécifié"
        company = company.strip().title()
        suffixes = [" Inc", " LLC", " Ltd", " Sarl", " Sas", " Eurl"]
        for suf in suffixes:
            if company.endswith(suf):
                company = company[:-len(suf)]
        return company.strip()

    def fetch_and_parse_duckduckgo(self, query: str, limit: int = 5) -> List[Dict]:
        """Node Fetcher & Parser : Recherche propre et extraction via DuckDuckGo Lite (sans contournement de protection)."""
        print(f"[WebAgent] Recherche web autonome pour : {query}")
        try:
            url = "https://lite.duckduckgo.com/lite/"
            data = {'q': query}
            response = requests.post(url, data=data, headers=self.headers, timeout=15)
            if response.status_code != 200:
                logger.error(f"Erreur HTTP DuckDuckGo: {response.status_code}")
                return []

            soup = BeautifulSoup(response.text, 'html.parser')
            extracted_items = []
            
            for row in soup.find_all('tr'):
                link_tag = row.find('a', class_='result-link')
                snippet_tag = row.find_next_sibling('tr')
                if link_tag:
                    title_text = link_tag.get_text(strip=True)
                    snippet_text = snippet_tag.get_text(strip=True) if snippet_tag else ""
                    
                    # Extraction basique d'emails potentiels dans le snippet pour alimenter le CRM
                    emails = re.findall(r"[\w\.-]+@[\w\.-]+\w+", snippet_text)
                    email = emails[0] if emails else f"prospect_{abs(hash(title_text))%10000}@web-lead.local"
                    
                    extracted_items.append({
                        "first_name": title_text.split()[0] if title_text else "Prospect",
                        "last_name": " ".join(title_text.split()[1:]) if len(title_text.split()) > 1 else "Web",
                        "email": email,
                        "phone": "",
                        "title": title_text[:50],
                        "company": "Source Web Autonome",
                        "source": "DuckDuckGo_Lite_Agent"
                    })
                if len(extracted_items) >= limit:
                    break
            return extracted_items
        except Exception as e:
            logger.error(f"Erreur d'exécution du WebAgent : {str(e)}")
            return []

    def dedup_and_upsert_neon(self, records: List[Dict]) -> int:
        """Node Deduper & UpsertDB : Insère ou met à jour les prospects dans Neon DB (table contacts)."""
        conn = get_db_connection()
        if not conn:
            logger.error("Connexion Neon DB indisponible pour l'agent web.")
            return 0
        
        inserted_count = 0
        try:
            cur = conn.cursor()
            for rec in records:
                if not rec.get("email"):
                    continue
                
                # Vérifie l'existence par email
                cur.execute("SELECT id FROM contacts WHERE email = %s LIMIT 1;", (rec["email"],))
                exists = cur.fetchone()
                
                if exists:
                    cur.execute("""
                        UPDATE contacts 
                        SET first_name = %s, last_name = %s, title = %s, company = %s, phone = %s, source = %s
                        WHERE email = %s;
                    """, (rec["first_name"], rec["last_name"], rec["title"], rec["company"], rec["phone"], rec["source"], rec["email"]))
                else:
                    cur.execute("""
                        INSERT INTO contacts (name, email, phone) 
                        VALUES (%s, %s, %s);
                    """, (f"{rec['first_name']} {rec['last_name']}".strip(), rec["email"], rec["phone"]))
                    inserted_count += 1
            
            conn.commit()
            cur.close()
            conn.close()
            return inserted_count
        except Exception as db_err:
            if conn:
                conn.rollback()
                conn.close()
            logger.error(f"Erreur Base de données Neon (WebAgent) : {db_err}")
            return 0

    def embed_and_store_memory(self, records: List[Dict]):
        """Node Embedder : Stocke un résumé textuel dans la mémoire vectorielle de l'agent."""
        for rec in records:
            text_to_embed = f"Prospect Web: {rec['first_name']} {rec['last_name']}, Poste: {rec['title']}, Entreprise: {rec['company']}"
            try:
                save_to_memory(f"PROSPECT_{rec['email']}", text_to_embed)
            except Exception as mem_err:
                logger.warning(f"Impossible d'indexer le prospect en mémoire vectorielle : {mem_err}")

    def run_pipeline(self, query: str = "Directeurs SaaS CRM 2026") -> dict:
        """Exécution complète du pipeline LangGraph simplifié (Fetcher -> Normalizer -> Deduper -> Upsert -> Embedder)."""
        print(f"[WebAgent Pipeline] Lancement de l'essaim pour la requête : '{query}'")
        
        # 1. Fetch & Parse
        raw_data = self.fetch_and_parse_duckduckgo(query, limit=3)
        if not raw_data:
            return {"status": "success", "inserted": 0, "message": "Aucune nouvelle donnée trouvée sur le web."}

        # 2. Normalizer
        normalized_data = []
        for item in raw_data:
            normalized_data.append({
                "first_name": self.normalize_email(item["first_name"]), # ou formatage standard
                "last_name": item["last_name"],
                "email": self.normalize_email(item["email"]),
                "phone": self.normalize_phone(item["phone"]),
                "title": self.strip_title(item["title"]),
                "company": self.map_company_name(item["company"]),
                "source": item["source"]
            })

        # 3. Deduper & Upsert DB
        new_count = self.dedup_and_upsert_neon(normalized_data)

        # 4. Embedder (Mémoire Vectorielle)
        self.embed_and_store_memory(normalized_data)

        print(f"[WebAgent Pipeline] Terminé ! {new_count} nouveaux contacts synchronisés dans Neon DB.")
        return {
            "status": "success",
            "inserted": new_count,
            "total_processed": len(normalized_data),
            "data": normalized_data
        }

# Instance globale pour le serveur Flask
web_agent_instance = WebAgent()
