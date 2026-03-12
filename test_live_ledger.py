import asyncio
from src.tools.web import start_deep_research

async def main():
    print("Triggering deep research with intention test parameter...")
    res = await start_deep_research("Quantum physics", max_depth=1, intention="Testing Generative Artifact Ledger")
    print("Tool Output:", res)

if __name__ == "__main__":
    asyncio.run(main())
