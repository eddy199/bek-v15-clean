import os

def load_project_documentation(docs_dir: str = None) -> str:
    """
    Charge les documentations officielles du projet (Architecture Système & CRM)
    pour initialiser le contexte global des agents.
    """
    if docs_dir is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        docs_dir = os.path.join(base_dir, "docs")

    files_to_load = [
        "referentiel_bek15.md",
        "architecture_crm_bek.md"
    ]

    master_context = "=== RÉFÉRENTIEL GLOBAL OFFICIEL (BEK-v15.2 & CRM) ===\n\n"

    for filename in files_to_load:
        file_path = os.path.join(docs_dir, filename)
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    master_context += f"--- [DOCUMENT : {filename}] ---\n"
                    master_context += f"{content}\n"
                    master_context += f"--- [FIN DU DOCUMENT : {filename}] ---\n\n"
            except Exception as e:
                master_context += f"[ERREUR LECTURE {filename}] : {str(e)}\n\n"
        else:
            master_context += f"[AVERTISSEMENT] Document introuvable : {filename}\n\n"

    return master_context

if __name__ == "__main__":
    context = load_project_documentation()
    print(f"Chargement terminé : {len(context)} caractères chargés.")