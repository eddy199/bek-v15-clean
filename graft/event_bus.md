---
covers: []
---
# event_bus.py

- EventBusKafka · class · L7-L69 — class EventBusKafka
- __init__ · method · L18-L26 — def __init__(self)
- publish · method · L28-L43 — def publish(self, topic: str, payload: Dict[str, Any])
- subscribe · method · L45-L47 — def subscribe(self, topic: str, callback: Callable[[Dict[str, Any]], None])
- _dispatch_loop · method · L49-L60 — def _dispatch_loop(self)
- get_radar_status · method · L62-L66 — def get_radar_status(self) -> Dict[str, Any]
- reset_radar · method · L68-L69 — def reset_radar(self)
