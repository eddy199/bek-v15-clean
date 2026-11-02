DECISION_TABLE_PROMPT = """
# 🎯 QUAND EXÉCUTER UNE ACTION
- Image/logo → `generate_image`
- Vidéo → `generate_video`
- News/Info fraîche → `web_sync`
- "Souviens-toi de..." → `save_memory`
- "Quel est mon... ?" → `search_memory`
- Tâche complexe explicite → `orchestrate`
- Nouveau code/script → `codex_agent`
- Modifier un fichier existant → `codex_editor` (avec `target_file`)
❌ PAS D'ACTION pour : salutations, explications, avis, plans, questions meta.
"""
def get_decision_table_prompt() -> str: return DECISION_TABLE_PROMPT.strip()