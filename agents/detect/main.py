"""Detect Agent entry point."""
import asyncio
import logging
from dotenv import load_dotenv
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
from agent import DetectAgent
async def main():
    agent = DetectAgent()
    await agent.start()
if __name__ == "__main__":
    asyncio.run(main())
