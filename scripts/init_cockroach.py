import os
import sys
from dotenv import load_dotenv

# Ensure we can import from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

COCKROACH_URL = os.getenv("COCKROACH_DATABASE_URL")

if not COCKROACH_URL:
    print("❌ COCKROACH_DATABASE_URL is not set in .env!")
    sys.exit(1)

print(f"Connecting to database at: {COCKROACH_URL.split('@')[-1]}")

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    print("❌ psycopg2-binary not installed in active environment! Run pip install psycopg2-binary")
    sys.exit(1)

def init_db():
    try:
        conn = psycopg2.connect(COCKROACH_URL)
        conn.autocommit = True
        cursor = conn.cursor()

        # Step 1: Enable vector extension (supported natively on CockroachDB Serverless)
        print("🔧 Enabling vector extension...")
        try:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            print("✅ Vector extension enabled successfully.")
        except Exception as e:
            print(f"⚠️ Vector extension creation warning: {e} (This is normal if already enabled or if permissions are restricted, proceeding...)")

        # Step 2: Create Core AgenticAI tables (migrating from SQLite)
        print("🧱 Creating Core AgenticAI tables...")
        
        # Conversations Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id VARCHAR(255) PRIMARY KEY,
            session_id VARCHAR(255),
            model_id VARCHAR(255),
            user_message TEXT,
            assistant_message TEXT,
            tokens_used INT DEFAULT 0,
            cost DOUBLE PRECISION DEFAULT 0.0,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Tool Executions Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tool_executions (
            id VARCHAR(255) PRIMARY KEY,
            conversation_id VARCHAR(255) REFERENCES conversations(id) ON DELETE CASCADE,
            tool_name VARCHAR(255) NOT NULL,
            parameters TEXT,
            result TEXT,
            success INT DEFAULT 1,
            execution_time DOUBLE PRECISION DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Documents Table (RAG text segments)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id VARCHAR(255) PRIMARY KEY,
            content TEXT NOT NULL,
            source VARCHAR(500),
            embedding_id VARCHAR(255),
            metadata TEXT,
            embedding VECTOR(384),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Cost Tracking Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS cost_tracking (
            id VARCHAR(255) PRIMARY KEY,
            model_id VARCHAR(255) NOT NULL,
            operation_type VARCHAR(100),
            tokens_input INT DEFAULT 0,
            tokens_output INT DEFAULT 0,
            cost DOUBLE PRECISION DEFAULT 0.0,
            latency DOUBLE PRECISION DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Messages Table (Raw context history, summaries & tags)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id VARCHAR(255) PRIMARY KEY,
            session_id VARCHAR(255), -- Foreign key dropped dynamically on migration
            role VARCHAR(50) NOT NULL,
            content_raw TEXT NOT NULL,
            content_summary TEXT,
            tags_json TEXT,
            model_id VARCHAR(255),
            tokens_used INT DEFAULT 0,
            embedding VECTOR(384),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # User Memories Table (Facts parsed from conversation)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_memories (
            id VARCHAR(255) PRIMARY KEY,
            content TEXT NOT NULL,
            tags_json TEXT,
            embedding VECTOR(384),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # API Keys Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id VARCHAR(255) PRIMARY KEY,
            provider VARCHAR(255) NOT NULL UNIQUE,
            label VARCHAR(255),
            key_value TEXT NOT NULL,
            is_active INT DEFAULT 1,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Role Assignments Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS role_assignments (
            role VARCHAR(255) PRIMARY KEY,
            provider VARCHAR(255) NOT NULL DEFAULT 'openrouter',
            model_id VARCHAR(255) NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Model Notes Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS model_notes (
            model_id VARCHAR(255) PRIMARY KEY,
            provider VARCHAR(255) NOT NULL DEFAULT 'openrouter',
            is_favorite INT DEFAULT 0,
            notes TEXT DEFAULT '',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Step 3: Create Custom SRE/DevOps brain tables
        print("🧱 Creating Custom SRE/DevOps tables...")

        # SRE Incidents Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            id VARCHAR(255) PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            description TEXT,
            severity VARCHAR(50) DEFAULT 'P3', -- P1 (Critical) to P4 (Low)
            service_name VARCHAR(255),          -- Affected microservice
            status VARCHAR(100) DEFAULT 'NEW',  -- NEW, INVESTIGATING, MITIGATED, RESOLVED
            root_cause TEXT,
            metadata TEXT,                      -- Log snippets, alert payloads
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP
        );
        """)

        # SRE Runbooks (Playbooks / Docs) Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS runbooks (
            id VARCHAR(255) PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            content TEXT NOT NULL,              -- Step-by-step resolution steps
            service_name VARCHAR(255),
            author VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Fix History / Resolution Actions
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS fix_history (
            id VARCHAR(255) PRIMARY KEY,
            incident_id VARCHAR(255) REFERENCES incidents(id) ON DELETE CASCADE,
            runbook_id VARCHAR(255) REFERENCES runbooks(id) ON DELETE SET NULL,
            action_taken TEXT NOT NULL,         -- Command run, PR merged, etc.
            engineer_notes TEXT,
            success INT DEFAULT 1,              -- 1 = resolved, 0 = failed/worsened
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Step 4: Create performance indexes
        print("⚡ Creating database indexes...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_created ON conversations(created_at);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_incidents_severity ON incidents(severity);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);")

        # Step 5: Test connection with a basic query
        cursor.execute("SELECT version();")
        db_version = cursor.fetchone()
        print(f"🎉 Successfully connected to CockroachDB!")
        print(f"💻 DB Version: {db_version[0]}")

        cursor.close()
        conn.close()
        print("✅ Database initialization completed successfully!")

    except Exception as e:
        print(f"❌ Error initializing CockroachDB: {e}")
        sys.exit(1)

if __name__ == "__main__":
    init_db()
