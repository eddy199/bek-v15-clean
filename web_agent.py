# web_agent.py - Agent Web Multi-Moteurs & Résilient pour BEK-v15
import os
import re
import asyncio
import logging
import urllib.parse
import requests
from bs4 import BeautifulSoup
from typing import List, Dict

from memory import get_db_connection, save_to_memory

logger = logging.getLogger(__name__)

class WebAgent:
    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://html.duckduckgo.com/',
        }

    def normalize_email(self, email: str) -> str:
        return email.strip().lower() if email else ""

    def normalize_phone(self, phone: str) -> str:
        if not phone:
            return ""
        return re.sub(r"\D", "", phone)

    def strip_title(self, title: str) -> str:
        return title.strip() if title else ""

    def map_company_name(self, company: str) -> str:
        if not company:
            return "Indépendant / Source Web"
        company = company.strip()
        suffixes = [" Inc", " LLC", " Ltd", " Sarl", " Sas", " Eurl"]
        for suf in suffixes:
            if company.endswith(suf):
                company = company[:-len(suf)]
        return company.strip()

    def _fetch_duckduckgo_html(self, query: str, limit: int = 5) -> List[Dict]:
        """Scraping via DuckDuckGo HTML standard."""
        try:
            url = "https://html.duckduckgo.com/html/"
            payload = {'q': query, 'b': ''}
            response = self.session.post(url, data=payload, headers=self.headers, timeout=12)
            if response.status_code != 200:
                return []

            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            for result in soup.find_all('div', class_='result'):
                title_elem = result.find('a', class_='result__a')
                snippet_elem = result.find('a', class_='result__snippet')
                
                if title_elem:
                    title_text = title_elem.get_text(strip=True)
                    raw_href = title_elem.get('href', '')
                    
                    clean_url = raw_href
                    if "uddg=" in raw_href:
                        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(raw_href).query)
                        if 'uddg' in parsed:
                            clean_url = parsed['uddg'][0]

                    snippet_text = snippet_elem.get_text(strip=True) if snippet_elem else ""
                    
                    emails = re.findall(r"[\w\.-]+@[\w\.-]+\w+", snippet_text)
                    email = emails[0] if emails else f"source_{abs(hash(title_text)) % 10000}@bek-intel.local"
                    
                    results.append({
                        "title": title_text,
                        "url": clean_url,
                        "snippet": snippet_text,
                        "first_name": title_text.split()[0] if title_text else "Source",
                        "last_name": " ".join(title_text.split()[1:4]) if len(title_text.split()) > 1 else "Web",
                        "email": email,
                        "phone": "",
                        "company": "Veille Web Autonome",
                        "source": "DuckDuckGo_HTML"
                    })
                if len(results) >= limit:
                    break
            return results
        except Exception as e:
            logger.warning(f"Échec fetch DDG HTML : {e}")
            return []

    def _fetch_duckduckgo_lite(self, query: str, limit: int = 5) -> List[Dict]:
        """Scraping alternatif via DuckDuckGo Lite."""
        try:
            url = "https://lite.duckduckgo.com/lite/"
            payload = {'q': query}
            response = self.session.post(url, data=payload, headers=self.headers, timeout=12)
            if response.status_code != 200:
                return []

            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            for row in soup.find_all('tr'):
                link_tag = row.find('a', class_='result-link')
                snippet_tag = row.find_next_sibling('tr')
                if link_tag:
                    title_text = link_tag.get_text(strip=True)
                    raw_href = link_tag.get('href', '')
                    clean_url = raw_href
                    if "uddg=" in raw_href:
                        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(raw_href).query)
                        if 'uddg' in parsed:
                            clean_url = parsed['uddg'][0]

                    snippet_text = snippet_tag.get_text(strip=True) if snippet_tag else ""
                    emails = re.findall(r"[\w\.-]+@[\w\.-]+\w+", snippet_text)
                    email = emails[0] if emails else f"source_{abs(hash(title_text)) % 10000}@bek-intel.local"

                    results.append({
                        "title": title_text,
                        "url": clean_url,
                        "snippet": snippet_text,
                        "first_name": title_text.split()[0] if title_text else "Source",
                        "last_name": " ".join(title_text.split()[1:4]) if len(title_text.split()) > 1 else "Web",
                        "email": email,
                        "phone": "",
                        "company": "Veille Web Autonome",
                        "source": "DuckDuckGo_Lite"
                    })
                if len(results) >= limit:
                    break
            return results
        except Exception as e:
            logger.warning(f"Échec fetch DDG Lite : {e}")
            return []

    def _fetch_wikipedia_fallback(self, query: str, limit: int = 3) -> List[Dict]:
        """Fallback garanti via l'API Wikipédia."""
        try:
            search_url = f"https://fr.wikipedia.org/w/api.php?action=opensearch&search={urllib.parse.quote(query)}&limit={limit}&namespace=0&format=json"
            res = requests.get(search_url, timeout=10)
            if res.status_code == 200:
                data = res.json()
                titles = data[1] if len(data) > 1 else []
                snippets = data[2] if len(data) > 2 else []
                urls = data[3] if len(data) > 3 else []
                
                results = []
                for title, snippet, link in zip(titles, snippets, urls):
                    results.append({
                        "title": title,
                        "url": link,
                        "snippet": snippet or f"Synthèse encyclopédique sur {title}.",
                        "first_name": title.split()[0] if title else "Wiki",
                        "last_name": "Archive",
                        "email": f"wiki_{abs(hash(title)) % 10000}@bek-intel.local",
                        "phone": "",
                        "company": "Wikipédia Knowledge Base",
                        "source": "Wikipedia_Fallback"
                    })
                return results
        except Exception as e:
            logger.error(f"Fallback Wikipedia échoué : {e}")
        return []

    def fetch_and_parse(self, query: str, limit: int = 4) -> List[Dict]:
        """Sélectionne le meilleur moteur avec cascade de fallbacks."""
        print(f"[WebAgent] Recherche web autonome pour : {query}")
        
        results = self._fetch_duckduckgo_html(query, limit=limit)
        if not results:
            print("[WebAgent] Bascule sur DuckDuckGo Lite...")
            results = self._fetch_duckduckgo_lite(query, limit=limit)
        if not results:
            print("[WebAgent] Bascule sur Fallback Encyclopédique...")
            results = self._fetch_wikipedia_fallback(query, limit=limit)
            
        return results

    def dedup_and_upsert_neon(self, records: List[Dict]) -> int:
        """Insère ou met à jour les données dans Neon DB."""
        conn = get_db_connection()
        if not conn:
            return 0
        
        inserted_count = 0
        try:
            cur = conn.cursor()
            for rec in records:
                if not rec.get("email"):
                    continue
                
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
                try: conn.rollback()
                except Exception: pass
                try: conn.close()
                except Exception: pass
            logger.error(f"Erreur Base de données Neon (WebAgent) : {db_err}")
            return 0

    def embed_and_store_memory(self, records: List[Dict]):
        """Indexe les extraits textuels dans Pinecone et ChromaDB."""
        for rec in records:
            text_to_embed = f"Veille Web sur '{rec['title']}': {rec['snippet']} (Source: {rec.get('url', 'N/A')})"
            try:
                try:
                    save_to_memory(text_to_embed)
                except TypeError:
                    save_to_memory(f"WEB_{abs(hash(rec['title']))}", text_to_embed)
            except Exception as mem_err:
                logger.warning(f"Impossible d'indexer en mémoire vectorielle : {mem_err}")

    def run_pipeline(self, query: str = "Architectures multi-agents 2026") -> str:
        """Exécute la recherche, enregistre dans les bases et retourne le rapport Markdown."""
        print(f"[WebAgent Pipeline] Lancement de la collecte pour : '{query}'")
        
        raw_data = self.fetch_and_parse(query, limit=3)
        if not raw_data:
            return f"ℹ️ Aucune information trouvée sur le Web pour : '{query}'."

        normalized_data = []
        for item in raw_data:
            normalized_data.append({
                "title": self.strip_title(item["title"]),
                "url": item.get("url", ""),
                "snippet": item.get("snippet", ""),
                "first_name": item["first_name"],
                "last_name": item["last_name"],
                "email": self.normalize_email(item["email"]),
                "phone": self.normalize_phone(item["phone"]),
                "company": self.map_company_name(item["company"]),
                "source": item["source"]
            })

        new_count = self.dedup_and_upsert_neon(normalized_data)
        self.embed_and_store_memory(normalized_data)

        report_lines = [
            f"### 🌐 Résultats de la recherche web : *{query}*",
            f"*{len(normalized_data)} sources synchronisées dans Neon DB et la mémoire vectorielle*\n"
        ]
        
        for idx, item in enumerate(normalized_data, 1):
            url_display = f"<{item['url']}>" if item['url'] else "N/A"
            snippet = item['snippet'] if item['snippet'] else "Extrait non disponible."
            report_lines.append(f"**{idx}. {item['title']}**")
            report_lines.append(f"- **Lien :** {url_display}")
            report_lines.append(f"- **Extrait :** {snippet}\n")

        print(f"[WebAgent Pipeline] Terminé avec succès.")
        return "\n".join(report_lines)

web_agent_instance = WebAgent()