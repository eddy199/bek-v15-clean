def delete_from_memory(record_id: str = "", keyword: str = "") -> dict:
    """Supprime un souvenir de Pinecone, ChromaDB et de la table sync_log Neon."""
    result = {"pinecone": False, "chroma": False, "neon_sync": False}
    
    # 1. Suppression Pinecone Cloud
    index = get_pinecone_index()
    if index is not None and record_id:
        try:
            index.delete(ids=[record_id])
            result["pinecone"] = True
            logger.info("Souvenir supprimé de Pinecone | id=%s", record_id)
        except Exception as exc:
            logger.warning("Échec suppression Pinecone : %s", exc)

    # 2. Suppression ChromaDB Local
    chroma_coll = get_chroma_collection()
    if chroma_coll is not None:
        try:
            if record_id:
                chroma_coll.delete(ids=[record_id])
            elif keyword:
                # Recherche par mot-clé pour suppression locale si l'ID est inconnu
                results = chroma_coll.get()
                ids_to_delete = []
                for idx, doc in enumerate(results.get("documents", [])):
                    if keyword.lower() in doc.lower():
                        ids_to_delete.append(results["ids"][idx])
                if ids_to_delete:
                    chroma_coll.delete(ids=ids_to_delete)
            result["chroma"] = True
            logger.info("Souvenir supprimé de ChromaDB local")
        except Exception as exc:
            logger.warning("Échec suppression ChromaDB : %s", exc)

    # 3. Suppression dans la table de compensation sync_log (Neon DB)
    conn = get_db_connection()
    if conn:
        cur = None
        try:
            cur = conn.cursor()
            if record_id:
                cur.execute("DELETE FROM sync_log WHERE id = %s;", (record_id,))
            elif keyword:
                cur.execute("DELETE FROM sync_log WHERE content LIKE %s;", (f"%{keyword}%",))
            conn.commit()
            result["neon_sync"] = True
        except Exception as exc:
            logger.warning("Échec suppression sync_log Neon : %s", exc)
            conn.rollback()
        finally:
            if cur:
                cur.close()
            conn.close()

    return result