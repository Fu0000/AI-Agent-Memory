"""
Shared test fixtures for Nocturne Memory backend tests.

Uses in-memory SQLite for complete test isolation — each test
gets a fresh database with all tables created.
"""

import os
import sys
import pytest
import pytest_asyncio

# Ensure backend/ is on sys.path so we can import db.sqlite_client etc.
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from db.sqlite_client import SQLiteClient, Base, Node, ROOT_NODE_UUID


@pytest_asyncio.fixture
async def db():
    """Provide a fresh in-memory SQLite client for each test.

    Tables are created via metadata.create_all (no migration runner needed).
    The ROOT_NODE sentinel is pre-inserted so FK constraints pass
    when creating top-level edges.
    The client is closed after the test completes.
    """
    client = SQLiteClient("sqlite+aiosqlite:///:memory:")
    async with client.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Ensure the sentinel root node exists for FK integrity
    async with client.session() as session:
        session.add(Node(uuid=ROOT_NODE_UUID))
    yield client
    await client.close()


@pytest_asyncio.fixture
async def seeded_db(db):
    """Provide a database pre-populated with a small memory tree.

    Tree structure after seeding:
        core://agent           (priority=0, content="I am an AI agent")
        core://agent/identity  (priority=1, content="My name is Nocturne")
        core://agent/user      (priority=1, content="My user is Alice")

    Returns the db client (same object as `db` fixture).
    """
    await db.create_memory(
        parent_path="",
        content="I am an AI agent",
        priority=0,
        title="agent",
        disclosure="On every conversation start",
        domain="core",
    )
    await db.create_memory(
        parent_path="agent",
        content="My name is Nocturne",
        priority=1,
        title="identity",
        disclosure="When asked about my name",
        domain="core",
    )
    await db.create_memory(
        parent_path="agent",
        content="My user is Alice",
        priority=1,
        title="user",
        disclosure="When interacting with user",
        domain="core",
    )
    return db
