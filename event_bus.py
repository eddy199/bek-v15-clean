# ==============================================================================
# event_bus.py — PIPELINE D'INGESTION & TRAÇABILITÉ A2A (BEK-v15.3)
# ==============================================================================

import time
import json
import threading
import uuid
from queue import Queue
from typing import Dict, Any, Callable, List, Optional

class EventBusKafka:
    """
    Pipeline d'Ingestion & Asynchronisme (Spécification Kafka BEK-v15.3 A2A)
    Gère 4 topics découplés avec traçabilité par correlation_id :
    1. web-cleaned    : Données nettoyées de l'Agent Web
    2. skills-index   : Indexation et compétences locales
    3. error-signals  : Radar rouge CRM/API et alertes
    4. vector-context : Contexte vectoriel Pinecone
    """
    VALID_TOPICS = {"web-cleaned", "skills-index", "error-signals", "vector-context"}

    def __init__(self):
        self.queues: Dict[str, Queue] = {t: Queue() for t in self.VALID_TOPICS}
        self.radar_red_active: bool = False
        self.subscribers: Dict[str, List[Callable[[Dict[str, Any]], None]]] = {t: [] for t in self.VALID_TOPICS}
        self._running = True
        self._event_counter: int = 0
        self._lock = threading.RLock()

        # Démarrage des consommateurs en tâche de fond
        self.worker_thread = threading.Thread(target=self._dispatch_loop, daemon=True)
        self.worker_thread.start()

    def publish(self, topic: str, payload: Dict[str, Any]) -> str:
        if topic not in self.VALID_TOPICS:
            raise ValueError(f"Topic inconnu : {topic}. Valides : {self.VALID_TOPICS}")

        correlation_id = payload.get("correlation_id", f"corr_{uuid.uuid4().hex[:12]}")
        payload["correlation_id"] = correlation_id

        with self._lock:
            self._event_counter += 1
            current_id = self._event_counter

        event = {
            "id": current_id,
            "topic": topic,
            "timestamp": time.time(),
            "correlation_id": correlation_id,
            "payload": payload
        }
        
        if topic == "error-signals":
            self.radar_red_active = True
            event["alert_level"] = "RED"

        self.queues[topic].put(event)
        return correlation_id

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
            "mode": "POLICE_ISOLATION" if self.radar_red_active else "NORMAL",
            "total_events_processed": self._event_counter
        }

    def reset_radar(self):
        self.radar_red_active = False

    def stop(self):
        """Arrêt propre du thread de dispatch."""
        self._running = False


if __name__ == "__main__":
    print("--- TEST UNITAIRE EVENT_BUS (KAFKA-MOCK) BEK-v15.3 A2A ---")
    bus = EventBusKafka()

    received_events = []

    bus.subscribe("skills-index", lambda e: received_events.append((e["payload"]["name"], e["correlation_id"])))
    bus.subscribe("error-signals", lambda e: print(f"🚨 RADAR ROUGE CAPTÉ [Corr: {e['correlation_id']}] : {e['payload']['msg']}"))

    corr = bus.publish("skills-index", {"name": "skill_crm_lead_v1", "version": "1.0"})
    time.sleep(0.1)
    print(f"Test nominal skills-index : Événement reçu = {received_events}")
    print(f"Statut Radar nominal : {bus.get_radar_status()}")

    bus.publish("error-signals", {"msg": "Tentative d'accès non certifié à Neon", "code": 500})
    time.sleep(0.1)
    print(f"Statut Radar après alerte : {bus.get_radar_status()}")