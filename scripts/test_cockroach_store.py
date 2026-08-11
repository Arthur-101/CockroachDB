"""Quick smoke test for CockroachMemoryStore."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.memory.cockroach_store import CockroachMemoryStore

def run():
    print("Connecting to CockroachDB...")
    store = CockroachMemoryStore()

    sid = "smoke-test-session"

    # 1 — conversation
    cid = store.save_conversation(sid, "test-model", "Hello CockroachSRE!", "I am running on CockroachDB!", tokens_used=12, cost=0.0001)
    print(f"[1] Saved conversation: {cid}")
    hist = store.get_conversation_history(sid, limit=1)
    print(f"[2] Retrieved conversation: {hist[0]['user_message']}")

    # 2 — message
    mid = store.save_message(sid, "user", "Test message from cockroach_store", tags=["test", "smoke"])
    print(f"[3] Saved message: {mid}")
    msgs = store.get_messages(sid, limit=5)
    print(f"[4] Retrieved {len(msgs)} message(s). Tags: {msgs[0]['tags']}")

    # 3 — SRE incident
    iid = store.save_incident(
        "Database OOM on prod",
        "All pods crashing due to 90% memory usage",
        severity="P1",
        service_name="payments-api",
    )
    print(f"[5] Saved incident: {iid}")
    incidents = store.get_incidents(limit=1)
    print(f"[6] Retrieved incident: {incidents[0]['title']} [{incidents[0]['status']}]")

    # 4 — runbook
    rid = store.save_runbook(
        "OOM Recovery Playbook",
        "Step 1: Scale down non-critical pods\nStep 2: Increase memory limits\nStep 3: Restart affected pods",
        service_name="payments-api",
    )
    print(f"[7] Saved runbook: {rid}")

    # 5 — fix history
    fid = store.save_fix_history(iid, "Scaled memory from 512Mi to 2Gi via kubectl patch", runbook_id=rid, success=True)
    print(f"[8] Saved fix history: {fid}")
    fix = store.get_fix_history(incident_id=iid)
    print(f"[9] Retrieved fix: {fix[0]['action_taken']}")

    # 6 — user memories
    mem_id = store.save_user_memory("User is working on CockroachSRE hackathon project", tags=["project"])
    print(f"[10] Saved user memory: {mem_id}")
    mems = store.get_all_user_memories()
    print(f"[11] Retrieved {len(mems)} user memories")

    # cleanup
    store.delete_session(sid)
    print("[12] Session cleanup done.")
    print()
    print("All CockroachDB store tests passed!")
    store.close()

if __name__ == "__main__":
    run()
