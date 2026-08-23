import time
import json
import threading
from queue import Queue
from typing import Dict, Any, Callable

class EventBusKafka:
    """
    Pipeline d'Ingestion & Asynchronisme (Spécification Kafka BEK-v15.2)
    Gère 4 topics découplés :
    1. web-cleaned    : Données nettoyées de l'Agent Web
    2. skills-index   : Indexation et compétences locales
    3. error-signals  : Radar rouge CRM/API et alertes
    4. vector-context : Contexte vectoriel Pinecone
    """
    VALID_TOPICS = {"web-cleaned", "skills-index", "error-signals", "vector-context"}

    def __init__(self):
        self.queues: Dict[str, Queue] = {t: Queue() for t in self.VALID_TOPICS}
        self.radar_red_active: bool = False
        self.subscribers: Dict[str, list] = {t: [] for t in self.VALID_TOPICS}
        self._running = True

        # Démarrage des consommateurs en tâche de fond
        self.worker_thread = threading.Thread(target=self._dispatch_loop, daemon=True)
        self.worker_thread.start()

    def publish(self, topic: str, payload: Dict[str, Any]):
        if topic not in self.VALID_TOPICS:
            raise ValueError(f"Topic inconnu : {topic}. Valides : {self.VALID_TOPICS}")

        event = {
            "topic": topic,
            "timestamp": time.time(),
            "payload": payload
        }
        
        # Déclenchement automatique du Radar Rouge sur signal d'erreur
        if topic == "error-signals":
            self.radar_red_active = True
            event["alert_level"] = "RED"

        self.queues[topic].put(event)

    def subscribe(self, topic: str, callback: Callable[[Dict[str, Any]], None]):
        if topic in self.VALID_TOPICS:
            self.subscribers[topic].append(callback)

    def _dispatch_loop(self):
        while self._running:
            for topic, q in self.queues.items():
                while not q.empty():
                    event = q.get()
                    for cb in self.subscribers[topic]:
                        try:
                            cb(event)
                        except Exception as e:
                            print(f"[EVENT_BUS ERROR] Erreur subscriber {topic} : {e}")
                    q.task_done()
            time.sleep(0.05)

    def get_radar_status(self) -> Dict[str, Any]:
        return {
            "radar_red": self.radar_red_active,
            "mode": "POLICE_ISOLATION" if self.radar_red_active else "NORMAL"
        }

    def reset_radar(self):
        self.radar_red_active = False


if __name__ == "__main__":
    print("--- TEST UNITAIRE EVENT_BUS (KAFKA-MOCK) BEK-v15.2 ---")
    bus = EventBusKafka()

    received_events = []

    # Souscription test sur skills-index et error-signals
    bus.subscribe("skills-index", lambda e: received_events.append(e["payload"]["name"]))
    bus.subscribe("error-signals", lambda e: print(f"🚨 RADAR ROUGE CAPTÉ : {e['payload']['msg']}"))

    # Publication nominale
    bus.publish("skills-index", {"name": "skill_crm_lead_v1", "version": "1.0"})
    time.sleep(0.1)
    print(f"Test nominal skills-index : Événement reçu = {received_events}")
    print(f"Statut Radar nominal : {bus.get_radar_status()}")

    # Publication anomalie
    bus.publish("error-signals", {"msg": "Tentative d'accès non certifié à Neon", "code": 500})
    time.sleep(0.1)
    print(f"Statut Radar après alerte : {bus.get_radar_status()}") 
