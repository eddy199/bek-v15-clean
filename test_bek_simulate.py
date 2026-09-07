from bek_simulate import run_simulation_scenario

def test_simulation_run():
    scenario = "Test de robustesse technique"
    turns = [
        {"query": "Comment configurer Linux ?", "response": "Voici les étapes pour configurer Linux proprement."},
        {"query": "Erreur critique", "response": "Une exception critique est survenue dans le système."},
        {"query": "Statut base de données", "response": "La base Neon DB est connectée et opérationnelle."}
    ]
    
    result = run_simulation_scenario(scenario, turns)
    assert result["passed_all"] is False
    assert result["details"][1]["evaluation"]["passed"] is False
    assert result["details"][0]["evaluation"]["passed"] is True

if __name__ == "__main__":
    print("🧪 Lancement de la simulation...")
    test_simulation_run()
    print("✅ Simulation validée avec succès !")