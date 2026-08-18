# AegisDB — Autonomous AI SRE Copilot (CockroachDB + Amazon S3 Architecture)

<p align="center">
  <img src="icons/logo_horizontal.SVG" alt="AegisDB Logo" width="400" />
</p>

<p align="center">
  <strong>The Indestructible Autonomous Site Reliability Engineering Copilot for Distributed Cloud Systems.</strong><br>
  Built for the <em>CockroachDB × AWS Hackathon</em>.
</p>

---

## Project Overview

**AegisDB** is an intelligent, multi-model AI-powered SRE (Site Reliability Engineering) agent system designed to run continuously in the background. It monitors active microservices, parses telemetry and application logs, queries CockroachDB performance statistics, retrieves authoritative playbooks from Amazon S3, and executes terminal diagnostic runbooks autonomously.

The system uses **CockroachDB Cloud Serverless** as a consolidated relational memory layer and semantic vector store (via `pgvector`), and leverages **Amazon S3** (`cockroachsre-knowledge-base`) as the authoritative knowledge base for production runbooks and incident postmortems with automatic embedding pipelines.

---

## Technology Stack

The application is structured into a modular agent-host architecture:

### Backend
- **Core Engine**: Python 3.9+ (asyncio patterns)
- **API Server**: FastAPI (JSON-RPC over WebSockets/HTTP)
- **Consolidated Relational Memory**: CockroachDB Cloud Serverless (chat history, memories, role assignments, incidents, playbooks, API keys, and tool calls)
- **Semantic Vector Storage**: Inline `pgvector` columns directly inside CockroachDB tables, queried with native cosine distance operators (`<=>`)
- **Local Embedding Generation**: `SentenceTransformer('all-MiniLM-L6-v2')` executing 384-dimensional cosine matches locally (100% free, zero quota usage)
- **Knowledge Base Source of Truth**: Amazon S3 bucket (`cockroachsre-knowledge-base`, `ap-south-1`) with continuous dual-sync into CockroachDB
- **LLM Reasoning & Orchestration**: Google Gemini 2.0 Flash / AWS Bedrock (Claude 3.5 Sonnet) / OpenAI / Anthropic
- **Distributed Cache & Sync**: Redis (portable Redis v5.0 binary auto-started and terminated cleanly by the backend host)
- **Terminal Execution**: `pywinpty` for stateful native Windows PTY access with PSReadLine ANSI escape filtering

### Frontend
- **Desktop Application Shell**: Tauri (Rust backend wrapping system tray controls and IPC windows)
- **Web Interface**: React (TypeScript)
- **Theme and Components**: Ant Design (configured with customized dark-glassmorphism styles)

---

## Core Features

- **Consolidated CockroachDB Memory & pgvector Store**: Purged local SQLite and ChromaDB instances. Replaced with CockroachDB Cloud Serverless wire-compatible PostgreSQL connections. Added inline `embedding VECTOR(384)` columns to join messages and memories tables directly, conducting semantic vector lookups with native joins.
- **Amazon S3 Knowledge Base Pipeline**: Direct bidirectional synchronization between Amazon S3 and CockroachDB pgvector. Pulls markdown runbooks and JSON incident logs on demand or on app launch.
- **Tauri System Tray & Background Service**: Minimizes gracefully to the Windows System Tray on close. Features custom context menus (`🟢 AegisDB (Engine Active)`, `🖥️ Show Studio Window`, `➕ Start New Chat`, `⚡ Toggle AI Engine`, `❌ Quit AegisDB`) and left-click toggles.
- **Zero-Install Portable Redis Memory**: Spawns and manages a bundled portable Redis server on start. Implements distributed locks, assembled context caching, and Pub/Sub broadcasts with SQLite/CockroachDB fallbacks.
- **Smart Memory Curation & Auto-Consolidation**: Extracts enduring facts, user preferences, and system specs from conversation context. Curates fact bases dynamically via `UPDATE`, `ADD`, or `SKIP` evaluations.
- **Multi-Model Team Consensus**: Spawns parallel background workers (Coding, Reasoning, Multimodal) using `asyncio.gather()` and merges results using a `ConsensusAggregator` to resolve conflicting solutions.
- **Local MCP Client Host**: Boots stdio-based Model Context Protocol (MCP) servers as background subprocesses, conducts protocol handshakes, and exposes tools dynamically.
- **Multi-Format Attachment Processor**: Decodes PDFs, log sheets, source code files, and images. Compiles image base64 `data_url` targets and passes them directly to vision APIs.
- **Stateful PTY Terminal**: Implements stateful command-line interaction on Windows using `pywinpty` with PSReadLine ANSI escape splits to prevent typos and terminal overlaps.

---

## System Architecture

```mermaid
graph TD
    User([SRE Engineer / Alert Ingest]) -->|Trigger Alert/Incident| UI[Tauri React Desktop Client - AegisDB]
    
    subgraph Client App
        UI -->|IPC Calls| Rust[Tauri Rust Bridge]
        Rust -->|stdin/stdout JSON-RPC| PyAPI[Python Embedded Backend API]
    end

    subgraph Knowledge Base & Storage
        PyAPI -->|Sync Runbooks & Incidents| S3[(Amazon S3 Knowledge Base)]
        S3 -->|Embed & Index| CRDB[(CockroachDB Cloud Serverless)]
        PyAPI -->|Store chats, logs, incidents, keys| CRDB
        PyAPI -->|Cosine similarity search <=>| CRDB
        PyAPI -->|Broadcast PubSub / Locks| Redis[(Portable Redis Cache & Sync)]
    end

    subgraph LLM Orchestration & Tool Execution
        PyAPI -->|Orchestrate workflow| Brain[Google Gemini 2.0 Flash / AWS Bedrock]
        PyAPI -->|Expose local commands & logs| Terminal[Stateful PTY Terminal WinPTY]
        PyAPI -->|Discovered APIs & Context| MCP[MCP Servers Host Stdio/SSE]
    end
    
    PyAPI -->|Synthesize answers| Synthesizer[Consensus Synthesizer]
    Synthesizer -->|Render responses & update status| UI
```

---

## Installation and Configuration

### Prerequisites
- **Python 3.9+** (Python 3.12+ recommended)
- **Node.js v18+** and **npm**
- **Cargo / Rust** (Only required if compiling Tauri binaries from source)

### 1. Repository Setup

Clone this repository and set up a virtual environment:

```bash
git clone https://github.com/Arthur-101/CockroachDB.git AegisDB
cd AegisDB

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install Python backend packages
python -m pip install -r requirements.txt
```

Navigate to the `ui` directory and install front-end dependencies:

```bash
cd ui
npm install
```

### 2. Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Open `.env` and set the following parameters:

```env
# Database Connection (CockroachDB Serverless Cluster)
COCKROACH_DATABASE_URL=postgresql://username:password@your-cluster.cockroachlabs.cloud:26257/defaultdb?sslmode=verify-full

# Amazon S3 & AWS Configuration (Knowledge Base & Runbooks)
S3_BUCKET_NAME=cockroachsre-knowledge-base
AWS_ACCESS_KEY_ID=YOUR_AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY=YOUR_AWS_SECRET_ACCESS_KEY
AWS_REGION=ap-south-1

# Google AI Studio Configuration (Orchestrator & Vision)
GEMINI_API_KEY=YOUR_GEMINI_API_KEY

# CockroachDB MCP Integration
COCKROACH_MCP_URL=https://cockroachlabs.cloud/mcp
COCKROACH_MCP_CLUSTER_ID=YOUR_COCKROACH_MCP_CLUSTER_ID
```

### 3. Direct API Keys Configuration

Additional API keys (OpenAI, Anthropic, Groq, Mistral AI) can be configured dynamically within the application UI Settings Drawer (saved securely inside the CockroachDB `api_keys` table). No manual database inserting is required.

---

## Running the Application

### Backend Server (FastAPI JSON-RPC WebSocket)
To start the backend service:

```bash
python main.py
```
This initializes the CockroachDB connection, auto-starts the bundled portable Redis engine, downloads vector models, and boots the FastAPI WebSocket server.

### Desktop UI Mode (Tauri)
To launch the desktop interface:

```bash
cd ui
npm run tauri dev
```

---

## Security & User Controls
- **Zero Credential Leakage**: Strict `.env` isolation and verified zero committed secret tokens in code or Git history.
- **User-in-the-Loop Confirmation**: File writes, command executions, and model settings adjustments require interactive prompt approvals.
- **Budget Alerts**: Configurable limits monitor token expenses per model, issuing soft warnings and hard stops to prevent runaway resource consumption.
- **Metadata Catalog Testing**: Model validation calls verify API connectivity directly via model listing schemas instead of generating token completions.

