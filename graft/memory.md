---
covers: []
---
# memory.py

- _env · function · L29-L30 — def _env(key, default="")
- clean_string · function · L58-L61 — def clean_string(text: str) -> str
- get_embedding · function · L63-L89 — def get_embedding(text: str) -> list
- get_pinecone_index · function · L91-L104 — def get_pinecone_index()
- search_memory · function · L106-L132 — def search_memory(query: str, top_k: int = 2) -> str
- save_to_memory · function · L134-L162 — def save_to_memory(user_query: str, agent_response: str)
- get_db_connection · function · L164-L177 — def get_db_connection()
