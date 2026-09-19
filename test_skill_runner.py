import asyncio
from skill_runner import execute_skill_async

async def main():
    result = await execute_skill_async("test_echo", {"msg": "bonjour"}, timeout_seconds=10)
    print("Résultat :", result)

if __name__ == "__main__":
    asyncio.run(main())