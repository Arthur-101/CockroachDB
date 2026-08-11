# CockroachSRE — AI SRE Agent System (AWS Bedrock + CockroachDB Architecture)

CockroachSRE is an intelligent, multi-model AI-powered SRE (Site Reliability Engineering) agent system developed for the CockroachDB × AWS Hackathon. It is designed to run continuously in the background, monitoring active microservices, parsing application logs, querying database performance metrics, suggesting runbook actions, and executing terminal diagnostic playbooks.

The system utilizes **CockroachDB Cloud Serverless** as a consolidated relational memory layer and semantic vector store (via `pgvector`), and leverages **AWS Bedrock (Claude 3.5 Sonnet v2)** for orchestrating complex sub-agent execution pipelines and tool calling. The application completely bypasses OpenRouter in favor of direct REST and SDK provider integrations.

---

## Technology Stack

The application is structured into a modular agent-host architecture:

### Backend
- **Core Engine**: Python 3.9+ (asyncio patterns)
- **API Server**: FastAPI (JSON-RPC over WebSockets/HTTP)
- **Consolidated Relational Memory**: CockroachDB Cloud Serverless (chat history, memories, role assignments, incidents, playbooks, API keys, and tool calls)
- **Semantic Vector Storage**: Inline `pgvector` columns directly inside CockroachDB tables, queried with native cosine distance operators (`<=>`)
- **Local Embedding Generation**: `SentenceTransformer('all-MiniLM-L6-v2')` executing 384-dimensional cosine matches locally (100% free, zero quota usage)
- **AWS Bedrock Integration**: `boto3` Converse API client for direct, low-latency AWS Bedrock dispatching
- **Distributed Cache & Sync**: Redis (portable Redis v5.0 binary auto-started and terminated cleanly by the backend host)
- **Direct Provider Routers**: Direct API connections for Google AI Studio, OpenAI, Anthropic, Groq, and Mistral AI API endpoints
- **Terminal Execution**: `pywinpty` for stateful native Windows PTY access with PSReadLine ANSI escape filtering

### Frontend
- **Desktop Application Shell**: Tauri (Rust backend wrapping system tray controls and IPC windows)
- **Web Interface**: React (TypeScript)
- **Theme and Components**: Ant Design (configured with customized dark-glassmorphism styles)

---

## Core Features

- **Consolidated CockroachDB memory & pgvector Store**: Purged local SQLite and ChromaDB instances. Replaced with CockroachDB Cloud Serverless wire-compatible PostgreSQL connections. Added inline `embedding VECTOR(384)` columns to join messages and memories tables directly, conducting semantic vector lookups with native joins.
- **Direct AWS Bedrock Integration**: Wire-level boto3 Converse API client for direct Claude 3.5 Sonnet, Claude 3.5 Haiku, and Claude 3 Opus integration. Appends system instructions and structures messages directly to guarantee high fidelity.
- **Tauri System Tray Tray & Background Service**: Minimizes gracefully to the Windows System Tray on close. Features custom context menus (`🟢 AgenticAI (Engine Active)`, `🖥️ Show Studio Window`, `➕ Start New Chat`, `⚡ Toggle AI Engine`, `❌ Quit AgenticAI`) and left-click toggles.
- **Zero-Install Portable Redis memory**: Spawns and manages a bundled portable Redis server on start. Implements distributed locks, assembled context caching, and Pub/Sub broadcasts with SQLite/CockroachDB fallbacks.
- **Smart Memory Curation & Auto-Consolidation**: Extracts enduring facts, user preferences, and system specs from conversation context. Curates fact bases dynamically via `UPDATE`, `ADD`, or `SKIP` evaluations.
- **Multi-Model Team Consensus**: Spawns parallel background workers (Coding, Reasoning, Multimodal) using `asyncio.gather()` and merges results using a `ConsensusAggregator` to resolve conflicting solutions.
- **Local MCP Client Host**: Boots stdio-based Model Context Protocol (MCP) servers (e.g., Tavily, Spotify) as background subprocesses, conducts protocol handshakes, and exposes tools dynamically.
- **Multi-Format Attachment Processor**: Decodes PDFs, log sheets, source code files, and images. Compiles image base64 `data_url` targets and passes them directly to vision APIs (Gemini, GPT).
- **Stateful PTY Terminal**: Implements stateful command-line interaction on Windows using `pywinpty` with PSReadLine ANSI escape splits to prevent typos and terminal overlaps.

---

## System Architecture

```
                     ┌──────────────────┐
                     │    User Input    │
                     └────────┬─────────┘
                              │
                              ▼
                     ┌──────────────────┐
                     │   Orchestrator   │ (AWS Bedrock / Gemini 2.0)
                     └────────┬─────────┘
                              │ (Decomposes & Selects)
                              ▼
             ┌────────────────┼────────────────┐
             │                │                │
             ▼                ▼                ▼
      ┌────────────┐   ┌────────────┐   ┌────────────┐
      │ Sub-Agent  │   │ Sub-Agent  │   │ Cockroach  │
      │  (Coding)  │   │(Reasoning) │   │ MCP Server │
      └──────┬─────┘   └─────┬──────┘   └─────┬──────┘
             │                │                │
             └────────────────┼────────────────┘
                              │ (Submits Proposals)
                              ▼
                     ┌──────────────────┐
                     │    Synthesizer   │ (Consensus Aggregator)
                     └────────┬─────────┘
                              │ (Consensus Analysis)
                              ▼
                     ┌──────────────────┐
                     │   Final Output   │
                     └──────────────────┘
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
git clone https://github.com/Arthur-101/CockroachDB.git CockroachSRE
cd CockroachSRE

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
COCKROACH_DATABASE_URL=postgresql://saurav0142:YOUR_PASS@cockroachsre-dev-31720.j77.aws-ap-south-1.cockroachlabs.cloud:26257/defaultdb?sslmode=verify-full

# AWS Bedrock Configuration
AWS_ACCESS_KEY_ID=YOUR_AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY=YOUR_AWS_SECRET_ACCESS_KEY
AWS_REGION=ap-south-1

# Google AI Studio Configuration (Orchestrator fallback)
GEMINI_API_KEY=YOUR_GEMINI_API_KEY

# CockroachDB MCP Integration
COCKROACH_MCP_URL=https://cockroachlabs.cloud/mcp
COCKROACH_MCP_CLUSTER_ID=7f4a4a09-a2fd-4753-9d7a-7f213f73940c
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
- **User-in-the-Loop Confirmation**: File writes, command executions, and model settings adjustments require interactive prompt approvals.
- **Budget Alerts**: Configurable limits monitor token expenses per model, issuing soft warnings and hard stops to prevent runaway resource consumption.
- **Metadata Catalog Testing**: Model validation calls verify API connectivity directly via model listing schemas instead of generating token completions.
