"""
tests/test_diary.py
====================
Regression tests for the Digital Diary CRUD layer (core/diary.py).

Covers:
  1. create_entry persists an encrypted entry and returns decrypted content.
  2. list_entries returns entries in reverse-chronological order.
  3. update_entry changes content and updates updated_at.
  4. delete_entry removes the row from SQLite.
  5. Date-range filtering in list_entries.
"""

import sys
import os
import uuid
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.database import init_db
from core.diary import create_entry, list_entries, get_entry, update_entry, delete_entry


def setup():
    init_db()


# ── Test 1: create and retrieve ───────────────────────────────────────────────

def test_create_and_get_entry():
    setup()
    uid = f"test_user_{uuid.uuid4().hex[:6]}"
    content = "Today I finished the project milestone and felt really proud."
    entry_dt = datetime.utcnow()

    result = create_entry(content=content, entry_date=entry_dt, user_id=uid, mood="😊 Good")

    assert result["id"] is not None
    assert result["content"] == content
    assert result["mood"] == "😊 Good"
    assert result["user_id"] == uid

    fetched = get_entry(result["id"], user_id=uid)
    assert fetched is not None
    assert fetched["content"] == content
    print(f"✅ test_create_and_get_entry  id={result['id'][:8]}")


# ── Test 2: list_entries reverse-chronological ────────────────────────────────

def test_list_entries_order():
    setup()
    uid = f"test_user_{uuid.uuid4().hex[:6]}"
    now = datetime.utcnow()

    e1 = create_entry("Older entry", entry_date=now - timedelta(days=2), user_id=uid)
    e2 = create_entry("Newer entry", entry_date=now - timedelta(days=1), user_id=uid)
    e3 = create_entry("Newest entry", entry_date=now, user_id=uid)

    entries = list_entries(user_id=uid)
    ids = [e["id"] for e in entries]

    assert ids.index(e3["id"]) < ids.index(e2["id"]) < ids.index(e1["id"]), \
        "Entries should be newest-first"
    print("✅ test_list_entries_order")


# ── Test 3: update_entry ──────────────────────────────────────────────────────

def test_update_entry():
    setup()
    uid = f"test_user_{uuid.uuid4().hex[:6]}"
    original = "I went for a walk today."
    entry = create_entry(original, entry_date=datetime.utcnow(), user_id=uid)

    updated = update_entry(entry["id"], content="I went for a long run today.", user_id=uid)

    assert updated is not None
    assert updated["content"] == "I went for a long run today."
    assert updated["updated_at"] >= entry["updated_at"]
    print("✅ test_update_entry")


# ── Test 4: delete_entry ──────────────────────────────────────────────────────

def test_delete_entry():
    setup()
    uid = f"test_user_{uuid.uuid4().hex[:6]}"
    entry = create_entry("Temporary entry to delete.", entry_date=datetime.utcnow(), user_id=uid)

    result = delete_entry(entry["id"], user_id=uid)
    assert result is True

    fetched = get_entry(entry["id"], user_id=uid)
    assert fetched is None, "Deleted entry should not be retrievable"
    print("✅ test_delete_entry")


# ── Test 5: date-range filtering ──────────────────────────────────────────────

def test_list_entries_date_filter():
    setup()
    uid = f"test_user_{uuid.uuid4().hex[:6]}"
    now = datetime.utcnow()

    create_entry("Old entry", entry_date=now - timedelta(days=10), user_id=uid)
    create_entry("Recent entry", entry_date=now - timedelta(days=1), user_id=uid)
    create_entry("Today entry", entry_date=now, user_id=uid)

    # Only entries from the last 3 days
    entries = list_entries(
        user_id=uid,
        date_from=now - timedelta(days=3),
        date_to=now + timedelta(hours=1),
    )
    contents = [e["content"] for e in entries]
    assert "Recent entry" in contents
    assert "Today entry" in contents
    assert "Old entry" not in contents
    print("✅ test_list_entries_date_filter")


# ── Test 6: user isolation ────────────────────────────────────────────────────

def test_user_isolation():
    setup()
    uid_a = f"user_a_{uuid.uuid4().hex[:6]}"
    uid_b = f"user_b_{uuid.uuid4().hex[:6]}"

    create_entry("Alice's private entry", entry_date=datetime.utcnow(), user_id=uid_a)
    create_entry("Bob's private entry",   entry_date=datetime.utcnow(), user_id=uid_b)

    alice_entries = list_entries(user_id=uid_a)
    bob_entries   = list_entries(user_id=uid_b)

    alice_contents = [e["content"] for e in alice_entries]
    bob_contents   = [e["content"] for e in bob_entries]

    assert "Alice's private entry" in alice_contents
    assert "Bob's private entry"   not in alice_contents
    assert "Bob's private entry"   in bob_contents
    assert "Alice's private entry" not in bob_contents
    print("✅ test_user_isolation")


# ── runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_create_and_get_entry()
    test_list_entries_order()
    test_update_entry()
    test_delete_entry()
    test_list_entries_date_filter()
    test_user_isolation()
    print("\n🎉 All diary tests passed.")
