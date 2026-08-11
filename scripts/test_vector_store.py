"""Smoke test for VectorMemoryStore (pgvector inline in CockroachDB)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from src.memory.vector_store import VectorMemoryStore

def run():
    print("Connecting to database and cleaning up test keys...")
    url = os.environ.get("COCKROACH_DATABASE_URL")
    conn = psycopg2.connect(url)
    conn.autocommit = True
    cur = conn.cursor()
    
    # Pre-insert some user memories and documents so we can test updating their embeddings
    cur.execute("DELETE FROM user_memories WHERE id = 'test-memory-1';")
    cur.execute("INSERT INTO user_memories (id, content) VALUES ('test-memory-1', 'Saurav likes coding in Python and building CockroachDB SRE agents.');")
    
    cur.execute("DELETE FROM documents WHERE source = 'test_runbook.txt';")
    
    conn.close()

    print("Initializing VectorMemoryStore...")
    vstore = VectorMemoryStore()

    # Test 1: add user memory embedding
    print("\n[1] Testing user memory vector update...")
    vstore.add_user_memory('test-memory-1', 'Saurav likes coding in Python and building CockroachDB SRE agents.')
    
    # Test 2: search user memories
    print("\n[2] Testing user memory semantic search...")
    res = vstore.search_user_memories('What programming language does Saurav like?', limit=1)
    if res:
        print(f"✅ Found match: {res[0]['content']} (distance: {res[0]['distance']})")
    else:
        print("❌ No matches found!")
        sys.exit(1)

    # Test 3: add document chunks
    print("\n[3] Testing document chunking and upsert...")
    doc_content = (
        "Runbook for high CPU usage in payment services:\n"
        "1. Check transaction throughput spikes.\n"
        "2. Locate payment-db CPU stats.\n"
        "3. Scale up replica nodes if transaction queue is backed up.\n"
        "4. Patch the database connection pool limit in production settings."
    )
    vstore.add_document('test_runbook.txt', doc_content, chunk_size=100, chunk_overlap=20)

    # Test 4: search documents
    print("\n[4] Testing document semantic search...")
    docs = vstore.search_documents('How to resolve high CPU in payment API?', limit=2)
    if docs:
        print("✅ Found document matches:")
        for doc in docs:
            print(f" - Content: {doc['content']}")
            print(f"   Metadata: {doc['metadata']}")
            print(f"   Distance: {doc['distance']}")
    else:
        print("❌ No document matches found!")
        sys.exit(1)

    # Test 5: add message
    print("\n[5] Testing message vector insert...")
    msg_id = 'test-msg-1'
    vstore.add_message('test-session', 'user', 'What is the default port for CockroachDB connections? 26257 is the default.', message_id=msg_id)

    # Test 6: search similar messages
    print("\n[6] Testing similar message semantic search...")
    msgs = vstore.search_similar_messages('port for CockroachDB', session_id='test-session', limit=1)
    if msgs:
        print(f"✅ Found message: {msgs[0]['content']} (distance: {msgs[0]['distance']})")
    else:
        print("❌ No similar messages found!")
        sys.exit(1)

    # Cleanup test records
    print("\n[7] Cleaning up test records...")
    conn = psycopg2.connect(url)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("DELETE FROM user_memories WHERE id = 'test-memory-1';")
    cur.execute("DELETE FROM documents WHERE source = 'test_runbook.txt';")
    cur.execute("DELETE FROM messages WHERE id = 'test-msg-1';")
    conn.close()

    print("\n🎉 All CockroachDB VectorMemoryStore tests passed successfully!")
    vstore.close()

if __name__ == "__main__":
    run()
