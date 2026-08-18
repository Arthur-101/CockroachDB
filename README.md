# AegisDB — Autonomous AI SRE Copilot (CockroachDB + Amazon S3)

<p align="center">
  <img src="icons/logo_horizontal.SVG" alt="AegisDB Logo" width="520" />
</p>

<p align="center">
  <strong>The Indestructible Autonomous Site Reliability Engineering Copilot with Persistent CockroachDB Memory & Amazon S3 Runbook Automation.</strong><br>
  <em>Built for the CockroachDB × AWS Hackathon (August 2026).</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/CockroachDB-pgvector_384d-6933FF?logo=cockroachlabs&logoColor=white" alt="CockroachDB" />
  <img src="https://img.shields.io/badge/Amazon_S3-Knowledge_Base-FF9900?logo=amazons3&logoColor=white" alt="Amazon S3" />
  <img src="https://img.shields.io/badge/CockroachDB_MCP-Managed_Server-00D4B2?logo=cockroachlabs&logoColor=white" alt="CockroachDB MCP" />
  <img src="https://img.shields.io/badge/Model_Routing-Dynamic_Multi--Model-blueviolet" alt="Multi-Model" />
  <img src="https://img.shields.io/badge/Tauri_v2-Desktop_Tray-24C8D8?logo=tauri&logoColor=white" alt="Tauri" />
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/React-19_TypeScript-61DAFB?logo=react&logoColor=black" alt="React" />
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License" />
</p>

---

## 🎬 Project Highlights & Links

- **Repository**: [https://github.com/Arthur-101/CockroachDB](https://github.com/Arthur-101/CockroachDB)
- **Demo Video (3 Minutes)**: [Watch on YouTube](https://youtu.be/placeholder) *(Replace with your video link)*
- **Architecture**: Distributed Multi-Model Agent + CockroachDB Cloud Serverless (`pgvector`) + Amazon S3 (`cockroachsre-knowledge-base`) + Tauri Native Desktop UI.

---

## 🏆 Devpost Judging Criteria Mapping

| Judging Criteria | How AegisDB Delivers |
|---|---|
| **🧠 Agentic Memory Design** | **CockroachDB Serverless** acts as the high-availability, always-on system of record. It stores conversational history, active incidents, resolution logs, role configurations, and 384-dimensional dense vector embeddings (`pgvector`) with cosine distance queries (`<=>`), surviving node crashes and multi-region failovers with zero data loss. |
| **⚙️ Technical Implementation** | Built with native **CockroachDB Cloud Managed MCP Server** integration (`https://cockroachlabs.cloud/mcp`), local zero-quota `SentenceTransformer` vector indexing, autonomous **Amazon S3 (`boto3`)** tool calling, and a Tauri v2 desktop application with background system tray daemon. |
| **💥 Real-World Impact** | Autonomous database incident triage and automated remediation for production microservices. Eliminates 3 AM panic by matching telemetry alerts to Amazon S3 playbooks, executing diagnostic scripts, and recording postmortems with zero human toil. |
| **🛡️ Production Readiness** | Includes a persistent **SRE Guardrails & Policy Engine** preventing destructive DDLs, UPSERT-based deduplication, interactive permission controls, zero hardcoded model fallbacks, and multi-process state synchronization with bundled portable Redis. |
| **✨ Creativity & Originality** | Features a **Heterogeneous Multi-Model SRE Collaboration Team** (Reasoning, Coding, Multimodal Specialists) with Consensus Synthesis, paired with an autonomous bidirectional Amazon S3 ⇄ CockroachDB knowledge pipeline. |

---

## 📖 The Problem: Agents Need Memory That Never Goes Down

When a distributed production database experiences transaction contention, latency spikes, or node failovers at 3 AM, every second of downtime costs revenue. Human SREs must manually correlate telemetry alarms, search through scattered Wiki runbooks, and test remediation commands.

Traditional AI agents fail in production because their memory is either ephemeral (lost on crashes/reboots) or locked in fragile local files that cannot survive node failures. **An AI SRE agent whose memory goes down doesn't degrade gracefully — it stops.**

**AegisDB** solves this by providing **indestructible, production-grade agentic memory**:
1. **Relational System of Record**: CockroachDB Cloud Serverless stores chat history, SRE operational policies, active incidents, and fix histories with ACID guarantees.
2. **Inline Vector Memory (`pgvector`)**: Native 384-dimensional cosine vector search (`<=>`) inside CockroachDB powers semantic RAG over runbooks, incident logs, and past fixes with zero external vector database silos.
3. **Authoritative Cloud Knowledge Base**: Amazon S3 (`cockroachsre-knowledge-base`) acts as the single source of truth for production runbooks with real-time autonomous indexing into CockroachDB.
4. **Autonomous Triage & Remediation**: Ingests alerts, queries matching runbooks via pgvector, executes diagnostic scripts inside a stateful Windows PTY terminal, and auto-resolves incidents.

---

## 🏗️ System Architecture

```mermaid
graph TB
    %% TIER 1: CLIENT & INGESTION
    subgraph T1["1. Client & Ingestion Layer"]
        User["SRE Engineer / Production Telemetry Alerts"]
        UI["AegisDB Desktop Studio (Tauri v2 + React 19 Glassmorphic UI)"]
        Tray["Windows System Tray Background Service"]
        User -->|Natural Language / Alerts| UI
        UI <-->|Tray Events & Background Daemon| Tray
    end

    %% TIER 2: AGENT ENGINE & ROUTING
    subgraph T2["2. Dynamic Multi-Model SRE Collaboration Engine"]
        Bridge["IPC JSON-RPC Bridge"]
        Router["Dynamic Multi-Model Router<br/>(Google Gemini, AWS Bedrock Claude, OpenAI, DeepSeek)"]
        subgraph Team["Collaborative Sub-Agent Team"]
            Reasoning["🧠 Reasoning Specialist (Architecture & Triage)"]
            Coding["💻 Coding Specialist (SQL / Remediation)"]
            Vision["👁️ Multimodal Specialist (Screenshots / Logs)"]
            Synth["🤝 Consensus Synthesizer (Master Plan)"]
        end
        UI -->|Desktop IPC| Bridge
        Bridge --> Router
        Router --> Reasoning & Coding & Vision
        Reasoning & Coding & Vision --> Synth
    end

    %% TIER 3: INDESTRUCTIBLE MEMORY (COCKROACHDB + AMAZON S3)
    subgraph T3["3. Indestructible Memory & Knowledge Tier"]
        direction LR
        S3[("📦 Amazon S3 Knowledge Base<br/>(s3://cockroachsre-knowledge-base)<br/>runbooks/ & incident-logs/")]
        CRDB_REL[("🪳 CockroachDB Relational Store<br/>(incidents, runbooks, fix_history, api_keys, user_memories)")]
        CRDB_VEC[("⚡ CockroachDB pgvector Store<br/>(384d Dense Vector Search <=>)")]
        Redis[("⚡ Bundled Redis Cache<br/>(Pub/Sub, Distributed Locks, Session State)")]
        
        S3 <-->|Autonomous Bidirectional Sync Pipeline| CRDB_VEC
        S3 <-->|Relational Sync & Deduplication| CRDB_REL
    end

    %% TIER 4: DIAGNOSTIC & EXECUTION TOOLCHAIN
    subgraph T4["4. Diagnostic & Execution Toolchain"]
        direction LR
        WinPTY["🖥️ Stateful WinPTY Terminal<br/>(Diagnostic Scripts & Fixes)"]
        MCP["🔌 CockroachDB Cloud MCP Server<br/>(Live Cluster Observability & Stats)"]
        S3Tools["☁️ Autonomous S3 Tools<br/>(List, Fetch, Index, Upload)"]
        SREStore["📋 SRE Lifecycle Skills<br/>(Ingest, Match, Auto-Resolve)"]
    end

    %% CONNECTIONS BETWEEN TIERS
    Team -->|Fetch Runbooks / Query Vector| CRDB_VEC
    Team -->|Read / Write State & Incidents| CRDB_REL
    Team -->|Sync & Cache Context| Redis
    Team -->|Run Diagnostic Commands| WinPTY
    Team -->|Query Cluster Metrics & Schema| MCP
    Team -->|Sync & Upload Runbooks / Logs| S3Tools
    Team -->|Execute SRE Triage Actions| SREStore

    %% FEEDBACK LOOP
    SREStore -->|Auto-Resolve & Log Root Cause| CRDB_REL
    SREStore -->|Embed Resolution Vector| CRDB_VEC
    S3Tools -->|Upload Postmortem JSON| S3
    WinPTY -->|Return Diagnostic Outputs| Team
```

---

## 🪳 CockroachDB Tools & Features Used

### 1. Distributed Vector Indexing (`pgvector` / `VECTOR(384)`)
- Stores dense 384-dimensional vector embeddings directly in CockroachDB's `documents`, `messages`, and `user_memories` tables.
- Executes native SQL cosine distance queries (`SELECT ... ORDER BY embedding <=> %s::VECTOR LIMIT 5`).
- Powered by local `SentenceTransformer('all-MiniLM-L6-v2')` model for **100% free, zero-quota, ultra-fast vector embeddings**.
- Implements atomic scoped wipe-and-replace transactions (`DELETE WHERE source = %s` followed by chunk insertion) to prevent ghost chunks.

### 2. CockroachDB Cloud Serverless Relational Memory Layer
- PostgreSQL wire-compatible ACID storage across core relational tables:
  - `incidents`: Tracks active production incidents, severity levels (P1–P4), affected services, and root causes.
  - `runbooks`: Stores operational playbooks indexed from Amazon S3.
  - `fix_history`: Stores executed remediation actions, engineering notes, and verification outcomes.
  - `user_memories`: Houses persistent SRE operational policies and cluster guardrails.
  - `api_keys` & `role_assignments`: Dynamic multi-provider API keys and role hot-swaps.
  - `sessions` & `messages`: Multi-turn conversational history.
- **Application-Level UPSERT Deduplication**: Ensures clean, duplicate-free syncs across both S3 and relational tables.

### 3. CockroachDB Cloud Managed MCP Server
- Connects directly to `https://cockroachlabs.cloud/mcp` using the Model Context Protocol (MCP).
- Exposes real-time database observability tools directly to the agent:
  - Statement statistics & slow query identification (`crdb_internal.statement_statistics`).
  - Cluster node health, range lease distribution, and CPU load inspection.
  - Database schema, table constraints, and index inspection.
  - Live query plan analysis (`EXPLAIN`).

### 4. CockroachDB SRE Management Console
- Built-in React 19 management tab featuring:
  - Real-time persistent cluster memory explorer.
  - Interactive incident lifecycle manager (Open, In Progress, Resolved).
  - Playbook reader with one-click Amazon S3 synchronization.
  - Live MCP server connection status and real-time process logs inspector.

---

## ☁️ AWS Services Used

### 1. Amazon S3 (`cockroachsre-knowledge-base`, Region: `ap-south-1`)
- **Authoritative Single Source of Truth**: Houses all verified SRE playbooks (`runbooks/<name>.md`) and structured incident lifecycle logs (`incident-logs/<date>/<incident_id>.json`).
- **Autonomous S3 Tool Calling Suite**:
  - `s3_list_knowledge_base`: Lists all playbooks and past incident logs in S3.
  - `s3_fetch_and_index_runbook`: Fetches playbooks from S3 on-the-fly and indexes them into CockroachDB pgvector in real time.
  - `s3_upload_knowledge_base_object`: Uploads newly generated runbooks or post-incident resolution logs directly to Amazon S3.
  - `s3_sync_knowledge_base`: Executes a full bidirectional synchronization between Amazon S3 and CockroachDB.
- **Direct Python SDK Integration (`boto3`)**: Connects directly via IAM credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`), requiring zero external CLI dependencies.

---

## 🤖 Dynamic Multi-Model SRE Collaboration Team

AegisDB utilizes a dynamic heterogeneous multi-agent team architecture with on-the-fly hot swapping:

```
                          ┌────────────────────────┐
                          │   SRE User / Alert     │
                          └──────────┬─────────────┘
                                     │
                                     ▼
                          ┌────────────────────────┐
                          │    Main Orchestrator   │
                          │ (Gemini 2.5 / GPT-4o)  │
                          └──────────┬─────────────┘
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         ▼                           ▼                           ▼
┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│  Reasoning Agent │       │   Coding Agent   │       │ Multimodal Agent │
│(Claude 3.5 / Pro)│       │ (DeepSeek / Coder│       │ (Gemini 2.0 / 4o)│
└────────┬─────────┘       └────────┬─────────┘       └────────┬─────────┘
         │ (Architecture Plan)      │ (Implementation)         │ (Media Analysis)
         └───────────────────────────┼───────────────────────────┘
                                     ▼
                          ┌────────────────────────┐
                          │  Consensus Synthesizer │
                          │ (Gemini / Qwen Flash)  │
                          └──────────┬─────────────┘
                                     │
                                     ▼
                          ┌────────────────────────┐
                          │ Unified Master Output  │
                          └────────────────────────┘
```

1. **Orchestrator Role**: Coordinates triage, delegates sub-tasks, and invokes system tools.
2. **Reasoning Specialist**: Decomposes complex cluster failures, analyzes range leasing physics, and drafts architectural plans.
3. **Coding Specialist**: Generates production-grade SQL DDLs, connection pooling logic, and Python remediation scripts.
4. **Multimodal Specialist**: Analyzes attached metric dashboards, architecture screenshots, and PDF runbooks.
5. **Consensus Synthesizer**: Merges parallel sub-agent outputs, eliminates conflicting recommendations, and delivers a unified Master Remediation Plan.

> **Strict User Control Guarantee**: AegisDB contains **zero hardcoded fallback models**. All model assignments are configured directly by the user in the Settings UI and persisted in CockroachDB and Redis.

---

## 🛡️ SRE Guardrails & Operational Knowledge

AegisDB features a persistent **SRE Policy Engine** stored in CockroachDB and retrieved semantically on every turn:
- **Destructive DDL Protection**: Strictly prohibits unconfirmed `DROP TABLE`, `DROP DATABASE`, or `TRUNCATE` operations without explicit human confirmation and verified backups.
- **Topology Awareness**: Enforces multi-region deployment awareness (e.g. AWS `ap-south-1` primary with `us-east-1` follower reads).
- **Connection Governance**: Enforces client connection pooling and exponential backoff retry for CockroachDB transaction serialization conflicts (`SQLSTATE 40001`).

---

## 🚀 Installation & Quickstart

### Prerequisites
- **Python 3.10+** (Python 3.12 recommended)
- **Node.js v18+** & **npm**
- **Rust / Cargo** (Only required if building the native desktop app from source)

---

### 1. Clone & Setup Backend

```bash
# Clone the repository
git clone https://github.com/Arthur-101/CockroachDB.git AegisDB
cd AegisDB

# Create and activate virtual environment
python -m venv .venv
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

---

### 2. Configure Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# CockroachDB Cloud Serverless Connection
COCKROACH_DATABASE_URL=postgresql://username:password@your-cluster.cockroachlabs.cloud:26257/defaultdb?sslmode=verify-full

# Amazon S3 Knowledge Base Configuration
S3_BUCKET_NAME=cockroachsre-knowledge-base
AWS_ACCESS_KEY_ID=YOUR_AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY=YOUR_AWS_SECRET_ACCESS_KEY
AWS_REGION=ap-south-1

# LLM Provider API Keys (Configure any provider you wish to use)
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
OPENAI_API_KEY=YOUR_OPENAI_API_KEY
ANTHROPIC_API_KEY=YOUR_ANTHROPIC_API_KEY
GROQ_API_KEY=YOUR_GROQ_API_KEY
MISTRAL_API_KEY=YOUR_MISTRAL_API_KEY
OPENROUTER_API_KEY=YOUR_OPENROUTER_API_KEY

# Optional: CockroachDB Cloud Managed MCP Server
COCKROACH_MCP_URL=https://cockroachlabs.cloud/mcp
COCKROACH_MCP_CLUSTER_ID=YOUR_COCKROACH_MCP_CLUSTER_ID
```

---

### 3. Launch Desktop Studio (Tauri + React)

```bash
# Navigate to UI directory
cd ui
npm install

# Launch the desktop app in development mode
npm run tauri dev
```

*(Alternatively, run in headless backend mode with `python main.py`)*

---

## 🧪 Verification & Automated Tests

Run the test suite to verify CockroachDB relational storage, pgvector semantic search, S3 tools, and multi-model routing:

```bash
# 1. Test CockroachDB Relational Tables & Session Storage
python scripts/test_cockroach_store.py

# 2. Test pgvector Cosine Distance Search (<=>) & Dense Embeddings
python scripts/test_vector_store.py

# 3. Test Amazon S3 Knowledge Base Sync & Ingestion
python scripts/seed_s3_runbooks.py

# 4. Test SRE Incident Lifecycle & Fix History
python scripts/test_sre_tools.py

# 5. Compile Frontend Production Bundle
cd ui && npm run build
```

---

## 💡 Feedback on CockroachDB AI Tools & Features

As part of the hackathon experience, our team compiled the following constructive feedback for the CockroachDB AI product team:

1. **`pgvector` Native Performance**: CockroachDB's `VECTOR(384)` and cosine distance operator (`<=>`) worked seamlessly with standard PostgreSQL `psycopg2` drivers. Eliminating external vector database silos significantly simplified our architecture.
2. **CockroachDB Cloud Managed MCP Server**: Having a native MCP server for CockroachDB is a game-changer for agentic workflows. We suggest adding pre-built MCP tools for **automatic index recommendation** and **one-click range lease rebalancing** to make autonomous database operations even more seamless.
3. **Agent Skills Ecosystem**: The ability to build reusable agent skills on top of CockroachDB state tables enables truly resilient, enterprise-grade AI automation that never loses its context.

---

## 🔒 Security & Safety Controls

- **Zero Credential Leakage**: Strict `.env` isolation; zero hardcoded secrets in source code or Git history.
- **Interactive Execution Guardrails**: Destructive terminal actions and SQL DDL operations require explicit confirmation.
- **Zero-Quota API Validation**: API key testing uses lightweight model listing metadata checks without consuming generation token quotas.

---

## 📄 License

Distributed under the **MIT License**. See [`LICENSE`](file:///E:/Codes/CockroachAI/LICENSE) for more information.

---

<p align="center">
  <strong>AegisDB — Built with ❤️ for the CockroachDB × AWS Hackathon 2026.</strong>
</p>
