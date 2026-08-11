import os
import sys
import json
from pathlib import Path

# Add project root to python path to import src modules
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.tools.basic_tools import ToolManager
from src.memory.vector_store import VectorMemoryStore
from dotenv import load_dotenv

def run_test():
    load_dotenv()
    print("=== Testing SRE Tools and pgvector Integration ===")
    
    # Initialize ToolManager (handles SQLite and VectorMemoryStore connections internally)
    tm = ToolManager()
    
    # 1. Test Ingestion of a new Incident
    print("\n1. Testing Ingestion of a new Incident...")
    incident_payload = {
        "title": "auth-service: HTTP 504 gateway timeout",
        "description": "Requests to /api/auth are failing with gateway timeouts under high thread pool loads.",
        "severity": "P1",
        "service_name": "auth-service",
        "status": "NEW",
        "metadata": json.dumps({"thread_dump": "locked on pool-auth-4", "active_connections": 150})
    }
    
    ingest_res = tm.execute_tool("ingest_incident", incident_payload)
    print(f"Response: {ingest_res}")
    
    if not ingest_res.get("success"):
        print("❌ Incident ingestion failed!")
        sys.exit(1)
        
    incident_id = ingest_res["result"]["incident_id"]
    print(f"🟢 Incident ingested successfully. ID: {incident_id}")
    
    # 2. Test Saving a Runbook Playbook
    print("\n2. Testing Saving a Runbook Playbook...")
    runbook_payload = {
        "title": "Mitigating thread pool exhaustion in auth-service",
        "content": "To resolve pool leaks in auth-service, increase maximum connections: scale connection pools to 300, clear active session handles in redis, and restart authorization pods using 'kubectl rollout restart deployment/auth-service'.",
        "service_name": "auth-service",
        "author": "Ops-Manager"
    }
    
    runbook_res = tm.execute_tool("save_runbook", runbook_payload)
    print(f"Response: {runbook_res}")
    
    if not runbook_res.get("success"):
        print("❌ Runbook saving failed!")
        sys.exit(1)
        
    runbook_id = runbook_res["result"]["runbook_id"]
    print(f"🟢 Runbook saved successfully. ID: {runbook_id}")
    
    # 3. Test Querying Incidents and Runbooks lists
    print("\n3. Testing Retrieval queries...")
    incidents_list = tm.execute_tool("get_incidents", {"service_name": "auth-service", "limit": 5})
    print(f"Recent incidents query: {incidents_list}")
    
    runbooks_list = tm.execute_tool("get_runbooks", {"service_name": "auth-service", "limit": 5})
    print(f"Recent runbooks query: {runbooks_list}")
    
    # 4. Test Recording a Fix Action and checking status updates
    print("\n4. Testing Recording a Fix Action...")
    fix_payload = {
        "incident_id": incident_id,
        "action_taken": "Scaled connection pool parameters, cleared session locks, and triggered kubectl restart on auth deployment.",
        "success": 1,
        "engineer_notes": "Scale connections resolved the issue. CPU usage stabilized back under 40%.",
        "runbook_id": runbook_id
    }
    
    fix_res = tm.execute_tool("record_fix_action", fix_payload)
    print(f"Response: {fix_res}")
    
    if not fix_res.get("success"):
        print("❌ Fix action recording failed!")
        sys.exit(1)
        
    fix_id = fix_res["result"]["fix_id"]
    print(f"🟢 Fix action recorded successfully. ID: {fix_id}")
    
    # Verify that the incident was auto-resolved
    check_incidents = tm.execute_tool("get_incidents", {"status": "RESOLVED", "limit": 5})
    resolved_found = False
    for inc in check_incidents.get("result", []):
        if inc["id"] == incident_id:
            resolved_found = True
            print(f"🟢 Incident status correctly updated to RESOLVED in CockroachDB. Root cause logged: '{inc['root_cause']}'")
            break
            
    if not resolved_found:
        print("❌ Incident status was NOT auto-resolved in CockroachDB!")
        sys.exit(1)
        
    # Query Fix history
    fix_history_res = tm.execute_tool("get_fix_history", {"incident_id": incident_id})
    print(f"Fix history retrieve: {fix_history_res}")
    
    # 5. Semantic Vector RAG Search validation
    print("\n5. Testing Semantic Vector RAG Search...")
    vs = VectorMemoryStore()
    
    # We query about "connection exhaustion pool leaks" which matches our runbook instructions semantically!
    rag_res = vs.search_documents(query="thread pool leaks kubectl rollout", limit=10)
    print("Semantic RAG Search results matching 'thread pool leaks kubectl rollout':")
    for r in rag_res:
        print(f"  - Source: {r.get('metadata', {}).get('file_path')} (Distance: {r.get('distance')})")
        print(f"    Snippet: {r.get('content')[:140]}...")
        
    # Check if our runbook or incident shows up in RAG results
    matching_found = any(f"runbook:{runbook_id}" in r.get('metadata', {}).get('file_path', '') for r in rag_res)
    if matching_found:
        print("✅ Success: Semantic vector search retrieved our new runbook segment from pgvector on CockroachDB!")
    else:
        print("❌ Error: Semantic vector search could NOT retrieve the runbook document!")
        sys.exit(1)
        
    print("\n=== All SRE Tool and pgvector Integration Tests Passed ===")

if __name__ == "__main__":
    run_test()
