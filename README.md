# AegisDB — Autonomous AI SRE Copilot (CockroachDB + Amazon S3)

<p align="center">
  <img src="icons/logo_horizontal.SVG" alt="AegisDB Logo" width="480" />
</p>

<p align="center">
  <strong>The Indestructible Autonomous Site Reliability Engineering Copilot with Persistent CockroachDB Memory & Amazon S3 Runbook Automation.</strong><br>
  <em>Built for the CockroachDB × AWS Hackathon (August 2026).</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/CockroachDB-pgvector_384d-6933FF?logo=cockroachlabs&logoColor=white" alt="CockroachDB" />
  <img src="https://img.shields.io/badge/Amazon_S3-Knowledge_Base-FF9900?logo=amazons3&logoColor=white" alt="Amazon S3" />
  <img src="https://img.shields.io/badge/Model_Routing-Dynamic_Multi--Model-blueviolet" alt="Multi-Model" />
  <img src="https://img.shields.io/badge/Tauri_v2-Desktop_Tray-24C8D8?logo=tauri&logoColor=white" alt="Tauri" />
  <img src="https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/React-19_TypeScript-61DAFB?logo=react&logoColor=black" alt="React" />
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License" />
</p>

---

## The Problem: Agents Need Memory That Never Goes Down

When a distributed production service fails at 3 AM, every second of downtime counts. Human SREs must manually correlate telemetry alerts, search through scattered Wiki runbooks, and test remediation commands.

Traditional AI agents fail in production because their memory is either ephemeral (lost on crashes/reboots) or locked in fragile local stores that cannot survive failovers. **An AI SRE agent whose memory goes down doesn't degrade gracefully — it stops.**

**AegisDB** solves this by providing **indestructible, production-grade agentic memory**:
1. **Relational System of Record**: CockroachDB Cloud Serverless stores chat history, user facts, active incidents, and resolution histories with ACID guarantees.
2. **Inline Vector Memory (`pgvector`)**: Native 384-dimensional cosine vector search (`<=>`) inside CockroachDB powers semantic RAG over runbooks, incident logs, and past fixes with zero external vector database silos.
3. **Authoritative Knowledge Base**: Amazon S3 (`cockroachsre-knowledge-base`) acts as the single source of truth for production runbooks with automatic dual-sync into CockroachDB.
4. **Autonomous Triage & Remediation**: Ingests alerts, queries matching runbooks via pgvector, executes diagnostic scripts inside a stateful Windows PTY terminal, and auto-resolves incidents.

---

## System Architecture

```mermaid
graph TD
    User([SRE Engineer / Production Alert]) -->|Trigger Incident / Chat| UI[AegisDB Tauri Desktop Studio]
    
    subgraph Client App
        UI -->|IPC Bridge| Rust[Tauri Rust Layer & System Tray]
        Rust -->|stdin/stdout JSON-RPC| PyAPI[Embedded Python SRE Backend]
    end

    subgraph Knowledge Base & Storage Layer
        PyAPI -->|Dual-Sync Runbooks & Postmortems| S3[(Amazon S3 Knowledge Base)]
        S3 -->|Dense 384d Embeddings| CRDB[(CockroachDB Cloud Serverless)]
        PyAPI -->|Relational State: Incidents, Chats, Keys| CRDB
        PyAPI -->|Semantic RAG Search: <=> Cosine| CRDB
        PyAPI -->|Distributed Locks & PubSub| Redis[(Portable Bundled Redis Cache)]
    end

    subgraph Autonomous Engine & Tools
        PyAPI -->|Dynamic Model Orchestration| LLM[Dynamic Multi-Model Router]
        PyAPI -->|Stateful Command Execution| Terminal[WinPTY Stateful Terminal]
        PyAPI -->|Cluster Observability & Tools| MCP[CockroachDB Cloud MCP Server]
        PyAPI -->|Execute SRE Skills| Skills[Custom SRE Skills Registry]
    end
    
    PyAPI -->|Stream Responses & Incident Updates| UI
```

---

## CockroachDB & AWS Capabilities

### CockroachDB Services Used

1. **Distributed Vector Indexing (`pgvector` / `VECTOR(384)`)**:
   - Stores dense 384-dimensional embeddings directly in CockroachDB (`documents`, `messages`, `user_memories` tables).
   - Executes native SQL cosine distance queries (`SELECT ... ORDER BY embedding <=> %s::VECTOR LIMIT 5`).
   - Implements atomic scoped wipe-and-replace transactions (`DELETE WHERE source = %s` followed by chunk insertion) to prevent stale ghost chunks.

2. **CockroachDB Cloud Serverless (Relational State Store)**:
   - PostgreSQL wire-compatible ACID storage across 10 tables: `conversations`, `messages`, `user_memories`, `role_assignments`, `api_keys`, `tool_calls`, `model_notes`, `sre_incidents`, `sre_runbooks`, and `sre_fix_history`.

3. **CockroachDB Cloud Managed MCP Server & Agent Skills**:
   - Streamable MCP endpoint (`https://cockroachlabs.cloud/mcp`) for live database metrics and schema analysis.
   - Machine-executable SRE skills (`ingest_incident`, `save_runbook`, `record_fix_action`, `get_incidents`, `get_runbooks`, `get_fix_history`).

### AWS Services Used

1. **Amazon S3 (`cockroachsre-knowledge-base`, Region: `ap-south-1`)**:
   - Authoritative cloud storage for SRE runbooks (`.md`), incident postmortems, and telemetry logs.
   - Bidirectional sync pipeline (`src/tools/s3_tools.py`) with UI trigger (**"Sync from AWS S3"**).

---

## Core Features

- **Closed-Loop SRE Remediation**: Alert Ingest → S3 Runbook Match → Terminal Execution → CockroachDB Auto-Resolve → Vector Fix Embedding.
- **Tauri System Tray & Background Service**: Minimizes to the Windows System Tray with native menus (`AegisDB (Engine Active)`, `Show Studio Window`, `Start New Chat`, `Toggle AI Engine`, `Quit AegisDB`).
- **Zero-Install Bundled Redis**: Auto-starts a portable Redis v5.0 binary for distributed locks and session state caching with automatic fallback.
- **Smart Long-Term Memory Curation**: Auto-extracts enduring personal preferences and system specs, curating them via `UPDATE`, `ADD`, or `SKIP` evaluations in CockroachDB.
- **Multi-Model Team Collaboration**: Parallel background workers (Coding, Reasoning, Multimodal) merged via a `ConsensusAggregator`.
- **Stateful PTY Terminal**: Stateful Windows PTY terminal powered by `pywinpty` with ANSI escape sequence filtering.
- **Multi-Format Attachment Processor**: Decodes PDFs, log sheets, source code files, and images into Base64 Data URLs for vision LLMs.

---

## Installation & Quickstart

### Prerequisites
- **Python 3.9+** (Python 3.12 recommended)
- **Node.js v18+** & **npm**
- **Rust / Cargo** (Only if building Tauri desktop binaries from source)

### 1. Clone & Setup Backend

```bash
# Clone the repository
git clone https://github.com/Arthur-101/CockroachDB.git AegisDB
cd AegisDB

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install Python backend packages
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Set your configuration in `.env`:

```env
# CockroachDB Cloud Serverless Connection
COCKROACH_DATABASE_URL=postgresql://username:password@your-cluster.cockroachlabs.cloud:26257/defaultdb?sslmode=verify-full

# Amazon S3 Knowledge Base Configuration
S3_BUCKET_NAME=cockroachsre-knowledge-base
AWS_ACCESS_KEY_ID=YOUR_AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY=YOUR_AWS_SECRET_ACCESS_KEY
AWS_REGION=ap-south-1

# Google AI Studio Configuration
GEMINI_API_KEY=YOUR_GEMINI_API_KEY

# CockroachDB MCP Integration
COCKROACH_MCP_URL=https://cockroachlabs.cloud/mcp
COCKROACH_MCP_CLUSTER_ID=YOUR_COCKROACH_MCP_CLUSTER_ID
```

### 3. Install UI Dependencies & Launch Desktop App

```bash
cd ui
npm install

# Run Desktop Application (Tauri + React)
npm run tauri dev
```

*(Alternatively, run in headless backend mode with `python main.py`)*

---

## Verification & Test Suite

Run the full automated test suite to verify CockroachDB relational storage, pgvector semantic search, and SRE tools:

```bash
# 1. Test CockroachDB Relational Tables & Sessions
python scripts/test_cockroach_store.py

# 2. Test pgvector Cosine Search (<=>) & Document Lifecycle
python scripts/test_vector_store.py

# 3. Test SRE Incident Ingestion, Fix Actions & Semantic RAG
python scripts/test_sre_tools.py

# 4. Test MCP Protocol Tool Normalization
python src/tools/test_mcp_normalization.py

# 5. Compile Frontend Production Bundle
cd ui && npm run build
```

---

## Security & Privacy Controls

- **Zero Credential Leakage**: Strict `.env` isolation; zero hardcoded secrets in source code or Git commit history.
- **Interactive Prompt Confirmations**: File writes and destructive terminal actions require explicit user confirmation.
- **Zero-Quota Model Listing Checks**: API key validation checks endpoints without consuming generation token quotas.

---

## License

Distributed under the **MIT License**. See `LICENSE` for more information.

