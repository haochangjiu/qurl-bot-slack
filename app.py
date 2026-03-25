"""
qurl-bot-slack — entry: Slack OAuth (SQLite) + Socket Mode + aiohttp OAuth routes.
"""

import asyncio

from adapters.slack_app import run_slack

if __name__ == "__main__":
    asyncio.run(run_slack())
