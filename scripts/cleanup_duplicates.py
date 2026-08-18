#!/usr/bin/env python3
"""
Clean up duplicate records in CockroachDB tables (runbooks, incidents, fix_history),
keeping only 1 distinct row for each title/identifier.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from src.memory.cockroach_store import SQLiteMemoryStore

def cleanup_duplicates():
    store = SQLiteMemoryStore()
    cur = store._cursor()

    # 1. Clean runbooks duplicates by title
    cur.execute("SELECT id, title, updated_at FROM runbooks ORDER BY updated_at DESC;")
    rows = cur.fetchall()
    seen_titles = set()
    to_delete_rb = []
    for r in rows:
        t = (r["title"] or "").strip().lower()
        if t in seen_titles:
            to_delete_rb.append(r["id"])
        else:
            seen_titles.add(t)

    for r_id in to_delete_rb:
        cur.execute("DELETE FROM runbooks WHERE id = %s;", (r_id,))
    print(f"Deduplicated runbooks table (deleted {len(to_delete_rb)} duplicates).")

    # 2. Clean incidents duplicates by title
    cur.execute("SELECT id, title, created_at FROM incidents ORDER BY created_at DESC;")
    rows = cur.fetchall()
    seen_inc = set()
    to_delete_inc = []
    for r in rows:
        t = (r["title"] or "").strip().lower()
        if t in seen_inc:
            to_delete_inc.append(r["id"])
        else:
            seen_inc.add(t)

    for i_id in to_delete_inc:
        cur.execute("DELETE FROM incidents WHERE id = %s;", (i_id,))
    print(f"Deduplicated incidents table (deleted {len(to_delete_inc)} duplicates).")

    # 3. Clean fix_history duplicates by incident_id + action_taken
    cur.execute("SELECT id, incident_id, action_taken, created_at FROM fix_history ORDER BY created_at DESC;")
    rows = cur.fetchall()
    seen_fix = set()
    to_delete_fix = []
    for r in rows:
        key = (r["incident_id"], (r["action_taken"] or "").strip().lower())
        if key in seen_fix:
            to_delete_fix.append(r["id"])
        else:
            seen_fix.add(key)

    for f_id in to_delete_fix:
        cur.execute("DELETE FROM fix_history WHERE id = %s;", (f_id,))
    print(f"Deduplicated fix_history table (deleted {len(to_delete_fix)} duplicates).")

    # Query remaining counts
    cur.execute("SELECT count(*) as cnt FROM runbooks;")
    rb_cnt = cur.fetchone()["cnt"]
    cur.execute("SELECT count(*) as cnt FROM incidents;")
    inc_cnt = cur.fetchone()["cnt"]
    cur.execute("SELECT count(*) as cnt FROM fix_history;")
    fix_cnt = cur.fetchone()["cnt"]

    print(f"\nRemaining clean records in CockroachDB:")
    print(f"  Runbooks: {rb_cnt}")
    print(f"  Incidents: {inc_cnt}")
    print(f"  Fix Records: {fix_cnt}")

if __name__ == "__main__":
    cleanup_duplicates()
