# -*- coding: utf-8 -*-
import asyncio
import os
import sys
from pathlib import Path

# Ajoute la racine du projet dans sys.path pour résoudre tous les modules
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from app import app
from event_bus_client import EventBusClient


def test_health_worker_endpoint():
    client = TestClient(app)
    response = client.get("/health/worker")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "ok"
    assert data.get("worker") == "running"


async def test_event_bus_pub_sub():
    bus = EventBusClient()
    received_messages = []

    async def sample_handler(msg):
        received_messages.append(msg)

    bus.subscribe("test.channel", sample_handler)
    await bus.publish("test.channel", {"unit_test": "pass", "code": 16})
    assert len(received_messages) == 1
    assert received_messages[0]["unit_test"] == "pass"


if __name__ == "__main__":
    test_health_worker_endpoint()
    asyncio.run(test_event_bus_pub_sub())
    print("\n✅ Tous les tests d'intégration ont réussi avec succès.")