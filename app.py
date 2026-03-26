"""
qurl-bot-slack — entry: Slack OAuth (file store) + Socket Mode + aiohttp OAuth routes.
"""

import asyncio

import sqlite3_bootstrap

sqlite3_bootstrap.ensure_sqlite3()

from adapters.slack_app import run_slack

if __name__ == "__main__":
    asyncio.run(run_slack())
