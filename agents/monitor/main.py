# FILE: agents/monitor/main.py
"""Monitor Agent entry point."""
import asyncio
import logging
import os

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from agent import MonitorAgent


async def main():
    agent = MonitorAgent()
    await agent.start()


if __name__ == "__main__":
    asyncio.run(main())
