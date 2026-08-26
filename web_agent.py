# web_agent.py - Agent Web pour la recherche live et l'enrichissement CRM
import os
import requests
from bs4 import BeautifulSoup

class WebAgent:
    def __init__(self):
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

    def search_and_extract(self, query: str) -> str:
        """Effectue une recherche simple et extrait le contenu pertinent des pages."""
        print(f"[WebAgent] Recherche en cours pour : {query}")
        try:
            # Exemple d'appel de recherche (ou intégration d'une API de search)
            # Ici, simulation d'un scraping propre ou d'une requête ciblée
            url = f"https://html.duckduckgo.com/html/?q={query}"
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                results = []
                for a in soup.find_all('a', class_='result__snippet', limit=3):
                    results.append(a.get_text())
                return "\n".join(results) if results else "Aucun résultat pertinent trouvé."
            return "Erreur lors de la connexion au web."
        except Exception as e:
            return f"Erreur WebAgent : {str(e)}"
