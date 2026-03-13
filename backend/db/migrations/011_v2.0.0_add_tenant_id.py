"""
Migration 011: Add tenant_id to edges and paths tables.

Enables multi-tenant isolation. Existing data gets tenant_id='default'.

Refs: OPT-5.1
"""

from sqlalchemy import text


async def migrate(engine):
    """Add tenant_id column to edges and paths tables."""
    async with engine.begin() as conn:
        # ---------- edges table ----------
        # Check if column already exists
        if engine.url.drivername.startswith("sqlite"):
            result = await conn.execute(text("PRAGMA table_info(edges)"))
            columns = [row[1] for row in result.fetchall()]
        else:
            result = await conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='edges' AND column_name='tenant_id'"
                )
            )
            columns = [row[0] for row in result.fetchall()]
            columns = columns or []

        if "tenant_id" not in columns:
            await conn.execute(
                text("ALTER TABLE edges ADD COLUMN tenant_id VARCHAR(64) NOT NULL DEFAULT 'default'")
            )
            await conn.execute(
                text("CREATE INDEX ix_edges_tenant_id ON edges (tenant_id)")
            )
            # Drop old unique constraint and create new one with tenant_id
            # SQLite doesn't support DROP CONSTRAINT, so we skip this for SQLite
            # The application layer handles uniqueness with tenant_id

        # ---------- paths table ----------
        if engine.url.drivername.startswith("sqlite"):
            result = await conn.execute(text("PRAGMA table_info(paths)"))
            columns = [row[1] for row in result.fetchall()]
        else:
            result = await conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='paths' AND column_name='tenant_id'"
                )
            )
            columns = [row[0] for row in result.fetchall()]
            columns = columns or []

        if "tenant_id" not in columns:
            await conn.execute(
                text("ALTER TABLE paths ADD COLUMN tenant_id VARCHAR(64) NOT NULL DEFAULT 'default'")
            )
            await conn.execute(
                text("CREATE INDEX ix_paths_tenant_id ON paths (tenant_id)")
            )
