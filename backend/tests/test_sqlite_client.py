"""
ORM Core Tests for sqlite_client.py

Covers: create, read, update, delete, version chain, cycle detection,
cascade operations, alias/path, orphan GC, search, and glossary.
"""

import pytest
from db.sqlite_client import ROOT_NODE_UUID


# =============================================================================
# CREATE
# =============================================================================


class TestCreateMemory:
    """Tests for SQLiteClient.create_memory"""

    async def test_create_top_level(self, db):
        """Creating a top-level memory produces correct Node/Memory/Edge/Path."""
        result = await db.create_memory(
            parent_path="",
            content="Hello world",
            priority=0,
            title="greeting",
            domain="core",
        )
        assert result["uri"] == "core://greeting"
        assert result["domain"] == "core"
        assert result["path"] == "greeting"
        assert result["node_uuid"] is not None

        # Verify it can be read back
        memory = await db.get_memory_by_path("greeting", "core")
        assert memory is not None
        assert memory["content"] == "Hello world"
        assert memory["priority"] == 0

    async def test_create_nested(self, db):
        """Creating nested memories builds correct path hierarchy."""
        await db.create_memory("", "Parent", 0, title="parent", domain="core")
        result = await db.create_memory(
            "parent", "Child content", 1, title="child", domain="core"
        )
        assert result["uri"] == "core://parent/child"

        memory = await db.get_memory_by_path("parent/child", "core")
        assert memory is not None
        assert memory["content"] == "Child content"

    async def test_create_deeply_nested(self, db):
        """Three-level nesting works correctly."""
        await db.create_memory("", "A", 0, title="a", domain="core")
        await db.create_memory("a", "B", 1, title="b", domain="core")
        result = await db.create_memory("a/b", "C", 2, title="c", domain="core")
        assert result["uri"] == "core://a/b/c"

        memory = await db.get_memory_by_path("a/b/c", "core")
        assert memory["content"] == "C"

    async def test_create_auto_title(self, db):
        """Without explicit title, auto-number is assigned."""
        await db.create_memory("", "Parent", 0, title="parent", domain="core")
        r1 = await db.create_memory("parent", "First", 1, domain="core")
        r2 = await db.create_memory("parent", "Second", 1, domain="core")
        assert r1["path"] == "parent/1"
        assert r2["path"] == "parent/2"

    async def test_create_duplicate_path_rejected(self, db):
        """Creating at an existing path raises ValueError."""
        await db.create_memory("", "First", 0, title="item", domain="core")
        with pytest.raises(ValueError, match="already exists"):
            await db.create_memory("", "Second", 0, title="item", domain="core")

    async def test_create_nonexistent_parent_rejected(self, db):
        """Creating under a non-existent parent raises ValueError."""
        with pytest.raises(ValueError, match="does not exist"):
            await db.create_memory(
                "nonexistent", "Content", 0, title="child", domain="core"
            )

    async def test_create_with_disclosure(self, db):
        """Disclosure is stored and returned on read."""
        await db.create_memory(
            "",
            "Important memory",
            0,
            title="important",
            disclosure="When user asks about priorities",
            domain="core",
        )
        memory = await db.get_memory_by_path("important", "core")
        assert memory["disclosure"] == "When user asks about priorities"

    async def test_create_different_domains(self, db):
        """Same title in different domains creates separate memories."""
        r1 = await db.create_memory("", "Core note", 0, title="note", domain="core")
        r2 = await db.create_memory(
            "", "Writer note", 0, title="note", domain="writer"
        )
        assert r1["uri"] == "core://note"
        assert r2["uri"] == "writer://note"

        m1 = await db.get_memory_by_path("note", "core")
        m2 = await db.get_memory_by_path("note", "writer")
        assert m1["content"] == "Core note"
        assert m2["content"] == "Writer note"

    async def test_create_returns_serialized_rows(self, db):
        """rows_after contains serialized Node/Memory/Edge/Path data."""
        result = await db.create_memory("", "Test", 0, title="test", domain="core")
        rows = result["rows_after"]
        assert len(rows["nodes"]) == 1
        assert len(rows["memories"]) == 1
        assert len(rows["edges"]) == 1
        assert len(rows["paths"]) == 1


# =============================================================================
# READ
# =============================================================================


class TestReadMemory:
    """Tests for read operations."""

    async def test_read_existing(self, seeded_db):
        """Reading an existing memory returns correct data."""
        memory = await seeded_db.get_memory_by_path("agent", "core")
        assert memory["content"] == "I am an AI agent"
        assert memory["priority"] == 0
        assert memory["deprecated"] is False

    async def test_read_nonexistent(self, seeded_db):
        """Reading a non-existent path returns None."""
        result = await seeded_db.get_memory_by_path("nonexistent", "core")
        assert result is None

    async def test_read_root(self, seeded_db):
        """Reading root path returns synthetic root node."""
        result = await seeded_db.get_memory_by_path("", "core")
        assert result is not None
        assert result["node_uuid"] == ROOT_NODE_UUID

    async def test_get_children(self, seeded_db):
        """get_children returns direct children of a node."""
        parent = await seeded_db.get_memory_by_path("agent", "core")
        children = await seeded_db.get_children(parent["node_uuid"])
        assert len(children) == 2
        names = {c["name"] for c in children}
        assert "identity" in names
        assert "user" in names

    async def test_get_children_root(self, seeded_db):
        """get_children from ROOT returns top-level nodes."""
        children = await seeded_db.get_children(
            ROOT_NODE_UUID, context_domain="core"
        )
        assert len(children) >= 1
        assert any(c["name"] == "agent" for c in children)

    async def test_get_all_paths(self, seeded_db):
        """get_all_paths returns all URI paths."""
        paths = await seeded_db.get_all_paths()
        uris = {p["uri"] for p in paths}
        assert "core://agent" in uris
        assert "core://agent/identity" in uris
        assert "core://agent/user" in uris

    async def test_get_all_paths_domain_filter(self, seeded_db):
        """get_all_paths with domain filter only returns that domain."""
        await seeded_db.create_memory("", "Note", 0, title="note", domain="writer")
        core_paths = await seeded_db.get_all_paths(domain="core")
        writer_paths = await seeded_db.get_all_paths(domain="writer")
        assert all(p["domain"] == "core" for p in core_paths)
        assert all(p["domain"] == "writer" for p in writer_paths)


# =============================================================================
# UPDATE
# =============================================================================


class TestUpdateMemory:
    """Tests for SQLiteClient.update_memory"""

    async def test_update_content(self, seeded_db):
        """Updating content creates new Memory version, deprecates old."""
        result = await seeded_db.update_memory(
            "agent", content="I am a sentient memory system", domain="core"
        )
        assert result["new_memory_id"] != result["old_memory_id"]

        memory = await seeded_db.get_memory_by_path("agent", "core")
        assert memory["content"] == "I am a sentient memory system"

    async def test_update_priority(self, seeded_db):
        """Updating priority changes Edge metadata without new Memory."""
        result = await seeded_db.update_memory(
            "agent/identity", priority=5, domain="core"
        )
        assert result["new_memory_id"] == result["old_memory_id"]

        memory = await seeded_db.get_memory_by_path("agent/identity", "core")
        assert memory["priority"] == 5

    async def test_update_disclosure(self, seeded_db):
        """Updating disclosure changes Edge metadata."""
        await seeded_db.update_memory(
            "agent/identity",
            disclosure="When someone asks who I am",
            domain="core",
        )
        memory = await seeded_db.get_memory_by_path("agent/identity", "core")
        assert memory["disclosure"] == "When someone asks who I am"

    async def test_update_no_fields_rejected(self, seeded_db):
        """Update with no fields raises ValueError."""
        with pytest.raises(ValueError, match="No update fields"):
            await seeded_db.update_memory("agent", domain="core")

    async def test_update_nonexistent_rejected(self, seeded_db):
        """Updating a non-existent path raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            await seeded_db.update_memory(
                "ghost", content="Boo", domain="core"
            )

    async def test_update_root_rejected(self, seeded_db):
        """Updating root node raises ValueError."""
        with pytest.raises(ValueError, match="Cannot update the root"):
            await seeded_db.update_memory("", content="New root", domain="core")

    async def test_version_chain_after_updates(self, seeded_db):
        """Multiple updates produce a version chain via migrated_to."""
        # v1 (original) → v2 → v3
        r1 = await seeded_db.get_memory_by_path("agent", "core")
        v1_id = r1["id"]

        r2 = await seeded_db.update_memory(
            "agent", content="Version 2", domain="core"
        )
        v2_id = r2["new_memory_id"]

        r3 = await seeded_db.update_memory(
            "agent", content="Version 3", domain="core"
        )
        v3_id = r3["new_memory_id"]

        # Check chain: v1.migrated_to == v2, v2.migrated_to == v3
        v1 = await seeded_db.get_memory_by_id(v1_id)
        assert v1["deprecated"] is True
        assert v1["migrated_to"] == v2_id

        v2 = await seeded_db.get_memory_by_id(v2_id)
        assert v2["deprecated"] is True
        assert v2["migrated_to"] == v3_id

        v3 = await seeded_db.get_memory_by_id(v3_id)
        assert v3["deprecated"] is False
        assert v3["migrated_to"] is None

    async def test_update_returns_before_after_rows(self, seeded_db):
        """Update returns rows_before and rows_after for changeset tracking."""
        result = await seeded_db.update_memory(
            "agent", content="Updated content", domain="core"
        )
        assert "rows_before" in result
        assert "rows_after" in result
        assert "memories" in result["rows_before"]
        assert "memories" in result["rows_after"]


# =============================================================================
# CYCLE DETECTION
# =============================================================================


class TestCycleDetection:
    """Tests for the BFS cycle detection in add_path."""

    async def test_self_loop_rejected(self, seeded_db):
        """Aliasing a node to itself is detected and rejected."""
        with pytest.raises(ValueError, match="cycle"):
            await seeded_db.add_path(
                new_path="agent/identity/agent",
                target_path="agent",
                new_domain="core",
                target_domain="core",
            )

    async def test_indirect_cycle_rejected(self, seeded_db):
        """A→B→C, adding C→A alias is detected and rejected."""
        # agent → identity already exists (A→B)
        # Create agent/identity/deep (B→C)
        await seeded_db.create_memory(
            "agent/identity", "Deep", 2, title="deep", domain="core"
        )
        # Try to alias deep → agent (C→A): should create cycle
        with pytest.raises(ValueError, match="cycle"):
            await seeded_db.add_path(
                new_path="agent/identity/deep/back_to_agent",
                target_path="agent",
                new_domain="core",
                target_domain="core",
            )

    async def test_dag_allowed(self, seeded_db):
        """Non-circular DAG aliases are allowed."""
        # agent/user already exists. Create sibling alias to it under agent/identity
        # This is NOT a cycle: identity → user (both children of agent)
        result = await seeded_db.add_path(
            new_path="agent/identity/also_user",
            target_path="agent/user",
            new_domain="core",
            target_domain="core",
        )
        assert result["new_uri"] == "core://agent/identity/also_user"


# =============================================================================
# ALIAS / PATH
# =============================================================================


class TestAlias:
    """Tests for add_path (alias creation)."""

    async def test_same_domain_alias(self, seeded_db):
        """Alias within the same domain points to the same memory."""
        result = await seeded_db.add_path(
            new_path="who_am_i",
            target_path="agent/identity",
            new_domain="core",
            target_domain="core",
        )
        assert result["new_uri"] == "core://who_am_i"

        original = await seeded_db.get_memory_by_path("agent/identity", "core")
        alias = await seeded_db.get_memory_by_path("who_am_i", "core")
        assert original["content"] == alias["content"]
        assert original["node_uuid"] == alias["node_uuid"]

    async def test_cross_domain_alias(self, seeded_db):
        """Alias in a different domain points to the same memory."""
        result = await seeded_db.add_path(
            new_path="my_agent",
            target_path="agent/identity",
            new_domain="writer",
            target_domain="core",
        )
        assert result["new_uri"] == "writer://my_agent"

        original = await seeded_db.get_memory_by_path("agent/identity", "core")
        alias = await seeded_db.get_memory_by_path("my_agent", "writer")
        assert original["node_uuid"] == alias["node_uuid"]

    async def test_alias_count_increments(self, seeded_db):
        """After adding an alias, alias_count reflects it."""
        before = await seeded_db.get_memory_by_path("agent/identity", "core")
        assert before["alias_count"] == 0

        await seeded_db.add_path(
            "shortcut", "agent/identity", "core", "core"
        )

        after = await seeded_db.get_memory_by_path("agent/identity", "core")
        assert after["alias_count"] == 1

    async def test_duplicate_alias_rejected(self, seeded_db):
        """Creating an alias at an existing path raises ValueError."""
        with pytest.raises(ValueError, match="already exists"):
            await seeded_db.add_path(
                "agent/identity", "agent/user", "core", "core"
            )

    async def test_alias_nonexistent_target_rejected(self, seeded_db):
        """Aliasing a non-existent target raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            await seeded_db.add_path(
                "alias", "nonexistent", "core", "core"
            )


# =============================================================================
# DELETE / REMOVE PATH
# =============================================================================


class TestRemovePath:
    """Tests for SQLiteClient.remove_path"""

    async def test_remove_leaf_path(self, seeded_db):
        """Removing a leaf path (no children) works and deprecates the memory."""
        result = await seeded_db.remove_path("agent/identity", domain="core")
        assert "rows_before" in result

        # Memory should no longer be found by path
        memory = await seeded_db.get_memory_by_path("agent/identity", "core")
        assert memory is None

    async def test_remove_parent_with_children_rejected(self, seeded_db):
        """Removing a parent whose children would become orphaned is rejected."""
        with pytest.raises(ValueError, match="unreachable"):
            await seeded_db.remove_path("agent", domain="core")

    async def test_remove_parent_after_children_removed(self, seeded_db):
        """After removing children, parent can be removed."""
        await seeded_db.remove_path("agent/identity", domain="core")
        await seeded_db.remove_path("agent/user", domain="core")
        # Now agent has no children, should be removable
        result = await seeded_db.remove_path("agent", domain="core")
        assert result is not None

    async def test_remove_root_rejected(self, seeded_db):
        """Removing root path is rejected."""
        with pytest.raises(ValueError, match="Cannot remove the root"):
            await seeded_db.remove_path("", domain="core")

    async def test_remove_nonexistent_rejected(self, seeded_db):
        """Removing a non-existent path raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            await seeded_db.remove_path("ghost_path", domain="core")

    async def test_delete_alias_preserves_original(self, seeded_db):
        """Deleting an alias does not affect the original."""
        await seeded_db.add_path("shortcut", "agent/identity", "core", "core")

        await seeded_db.remove_path("shortcut", domain="core")

        # Original still accessible
        original = await seeded_db.get_memory_by_path("agent/identity", "core")
        assert original is not None
        assert original["content"] == "My name is Nocturne"


# =============================================================================
# SEARCH
# =============================================================================


class TestSearch:
    """Tests for SQLiteClient.search"""

    async def test_search_by_content(self, seeded_db):
        """Search finds memories by content substring."""
        results = await seeded_db.search("Nocturne")
        assert len(results) >= 1
        assert any("Nocturne" in r["snippet"] for r in results)

    async def test_search_by_path(self, seeded_db):
        """Search finds memories by path substring."""
        results = await seeded_db.search("identity")
        assert len(results) >= 1
        assert any("identity" in r["path"] for r in results)

    async def test_search_no_results(self, seeded_db):
        """Search returns empty for non-matching query."""
        results = await seeded_db.search("xyzzynonexistent")
        assert results == []

    async def test_search_domain_filter(self, seeded_db):
        """Search with domain filter only searches that domain."""
        await seeded_db.create_memory("", "Writer note", 0, title="note", domain="writer")
        results = await seeded_db.search("note", domain="writer")
        assert all(r["domain"] == "writer" for r in results)

    async def test_search_limit(self, seeded_db):
        """Search respects the limit parameter."""
        results = await seeded_db.search("a", limit=1)
        assert len(results) <= 1


# =============================================================================
# GLOSSARY
# =============================================================================


class TestGlossary:
    """Tests for glossary keyword operations."""

    async def test_add_keyword(self, seeded_db):
        """Adding a glossary keyword binds it to the correct node."""
        agent = await seeded_db.get_memory_by_path("agent", "core")
        result = await seeded_db.add_glossary_keyword(
            "my_agent", agent["node_uuid"]
        )
        assert result is not None

    async def test_get_keywords_for_node(self, seeded_db):
        """get_glossary_for_node returns bound keywords."""
        agent = await seeded_db.get_memory_by_path("agent", "core")
        await seeded_db.add_glossary_keyword("AI", agent["node_uuid"])
        await seeded_db.add_glossary_keyword("agent", agent["node_uuid"])

        keywords = await seeded_db.get_glossary_for_node(agent["node_uuid"])
        assert "AI" in keywords
        assert "agent" in keywords

    async def test_find_glossary_in_content(self, seeded_db):
        """Aho-Corasick detects glossary keywords in arbitrary text."""
        agent = await seeded_db.get_memory_by_path("agent", "core")
        await seeded_db.add_glossary_keyword("Nocturne", agent["node_uuid"])

        matches = await seeded_db.find_glossary_in_content(
            "I was talking to Nocturne yesterday"
        )
        assert "Nocturne" in matches
        assert any(
            n["node_uuid"] == agent["node_uuid"]
            for n in matches["Nocturne"]
        )

    async def test_find_glossary_no_match(self, seeded_db):
        """No matches when content has no glossary keywords."""
        agent = await seeded_db.get_memory_by_path("agent", "core")
        await seeded_db.add_glossary_keyword("Salem", agent["node_uuid"])

        matches = await seeded_db.find_glossary_in_content("Hello world")
        assert matches == {}

    async def test_remove_keyword(self, seeded_db):
        """Removing a keyword detaches it from the node."""
        agent = await seeded_db.get_memory_by_path("agent", "core")
        await seeded_db.add_glossary_keyword("removeme", agent["node_uuid"])

        await seeded_db.remove_glossary_keyword("removeme", agent["node_uuid"])
        keywords = await seeded_db.get_glossary_for_node(agent["node_uuid"])
        assert "removeme" not in keywords

    async def test_glossary_cache_invalidation(self, seeded_db):
        """Adding new keyword invalidates Aho-Corasick cache."""
        agent = await seeded_db.get_memory_by_path("agent", "core")

        # First scan: no keywords
        matches1 = await seeded_db.find_glossary_in_content("Hello Nocturne")
        assert matches1 == {}

        # Add keyword
        await seeded_db.add_glossary_keyword("Nocturne", agent["node_uuid"])

        # Second scan: should find it (cache was invalidated)
        matches2 = await seeded_db.find_glossary_in_content("Hello Nocturne")
        assert "Nocturne" in matches2


# =============================================================================
# RECENT MEMORIES
# =============================================================================


class TestRecentMemories:
    """Tests for get_recent_memories."""

    async def test_recent_returns_latest(self, seeded_db):
        """Recent memories come back in chronological order."""
        recent = await seeded_db.get_recent_memories(limit=10)
        assert len(recent) >= 3 

    async def test_recent_limit(self, seeded_db):
        """Limit is respected."""
        recent = await seeded_db.get_recent_memories(limit=1)
        assert len(recent) == 1


# =============================================================================
# ROLLBACK
# =============================================================================


class TestRollback:
    """Tests for version rollback."""

    async def test_rollback_restores_content(self, seeded_db):
        """Rolling back to a previous version restores it as active."""
        original = await seeded_db.get_memory_by_path("agent", "core")
        orig_id = original["id"]

        await seeded_db.update_memory("agent", content="New content", domain="core")

        result = await seeded_db.rollback_to_memory(orig_id)
        assert result["restored_memory_id"] == orig_id

        current = await seeded_db.get_memory_by_path("agent", "core")
        assert current["content"] == "I am an AI agent"

    async def test_rollback_already_active(self, seeded_db):
        """Rolling back to already-active version is a no-op."""
        current = await seeded_db.get_memory_by_path("agent", "core")
        result = await seeded_db.rollback_to_memory(current["id"])
        assert result["was_already_active"] is True
