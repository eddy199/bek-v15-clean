import asyncio
from event_bus_client import event_bus

async def main():
    received = []

    async def on_skill(msg):
        received.append(msg)

    event_bus.subscribe("skills-index", on_skill)

    await event_bus.publish("skills-index", {"name": "test_skill", "v": "1.0"})
    await asyncio.sleep(1.0)

    print("Mode bus :", event_bus.mode)
    print("Reçu     :", received)
    await event_bus.close()

if __name__ == "__main__":
    asyncio.run(main())