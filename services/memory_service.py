# services/memory_service.py
import lancedb
import duckdb
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd

class OptimizedMemoryService:
    def __init__(self, base_path: str = "./data"):
        """
        Initialise la brique de mémoire locale (LanceDB + DuckDB) conforme à l'ADR-001.
        Conçu pour tourner efficacement sur des conteneurs à ressources limitées (Render).
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # 1. Base vectorielle locale (Zéro round-trip réseau)
        self.lancedb_path = str(self.base_path / "lancedb")
        self.db = lancedb.connect(self.lancedb_path)
        
        # 2. Base analytique et cache local (Orientée colonnes, zéro-copy)
        self.duck_conn = duckdb.connect(str(self.base_path / "analytics.duckdb"))
        
        self._init_storage()

    def _init_storage(self):
        """Initialise les tables de base si elles n'existent pas."""
        if "agent_memory" not in self.db.table_names():
            # Initialisation d'une table vectorielle de base (ex: dimension 1536)
            initial_data = [{
                "vector": [0.0] * 1536, 
                "text": "genesis_anchor",
                "metadata": "{}"
            }]
            self.db.create_table("agent_memory", data=initial_data)

    def fast_vector_search(self, query_vector: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        """
        Recherche vectorielle locale instantanée. Remplace les appels réseau Pinecone fréquents.
        """
        table = self.db.open_table("agent_memory")
        results = table.search(query_vector).limit(limit).to_pandas()
        return results.to_dict(orient="records")

    def upsert_vector(self, vector: List[float], text: str, metadata: Dict[str, Any]):
        """Ajoute ou met à jour une donnée vectorielle en local sans bloquer le système."""
        table = self.db.open_table("agent_memory")
        data = [{"vector": vector, "text": text, "metadata": str(metadata)}]
        table.add(data)

    def analytical_query(self, sql_query: str) -> pd.DataFrame:
        """
        Exécute des requêtes de synchronisation ou d'historique via DuckDB en mémoire/disque.
        """
        return self.duck_conn.execute(sql_query).fetchdf()

    def close(self):
        self.duck_conn.close()
