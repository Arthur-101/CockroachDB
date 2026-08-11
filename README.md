# CockroachAI

`This is another version of AgenticAI with the tech stack changes to match with the CockroachDB Hackathon`

AgenticAI is a multi-model AI agent system built on a modular Model Context Protocol (MCP) style architecture. Rather than relying on a single large language model for all tasks, AgenticAI dynamically orchestrates, selects, and routes tasks to specialized models optimized for speed, cost, reasoning, or multimodal capabilities.

Featuring a modern React and Ant Design dark glassmorphic UI wrapped in a native Windows Tauri system tray application, the system incorporates real-time multi-process synchronization, a robust shared memory layer, local MCP tool hosts, and multi-agent consensus pipelines.

---

## Technology Stack

The application is built using the following technologies:

### Backend
- **Core Language**: Python 3.9+
- **API Server**: FastAPI (streaming JSON-RPC over WebSockets/HTTP)
- **Primary Database (Relational)**: SQLite3 (for session history, configurations, API keys, and memory)
- **Vector Database (Semantic Search)**: ChromaDB (for document RAG and long-term memory embeddings)
- **Distributed Cache & Memory Sync**: Redis (portable Redis v5.0 automatically launched by the Python backend)
- **Direct REST/HTTP Handlers**: Custom provider router supporting OpenRouter, Google AI Studio, Anthropic, OpenAI, Groq, and Mistral AI API endpoints
- **Terminal Execution**: pywinpty for stateful native Windows PTY access with PSReadLine ANSI escape filtering

### Frontend
- **Desktop Application Shell**: Tauri (Rust backend wrapper for system tray and window state IPC management)
- **Web UI Library**: React (TypeScript)
- **UI Component Framework**: Ant Design (with custom dark-glassmorphism theme configurations)

---

## Core Features

- **Intelligent Heterogeneous Routing**: Automatically determines task complexity and routes sub-tasks to specialized models or lets users dynamically configure distinct models for specific workflow roles.
- **Tauri Desktop UI and Windows Tray Integration**: React-based front-end with an advanced glassmorphism theme that minimizes to the Windows System Tray, featuring left-click toggle visibility and native context menu commands.
- **Zero-Install Portable Redis Memory Sync**: Automatically spawns and manages a bundled portable Redis server on start for multi-process distributed locks, active session caching, and Pub/Sub communication with automatic SQLite fallbacks.
- **Smart Facts Curation and Consolidation**: Uses conversational history to automatically extract enduring facts, user preferences, and system specs. Synthesizes updates using a deterministic UPDATE, ADD, or SKIP evaluation loop, persisting memory in SQLite and indexing it in ChromaDB for high-accuracy RAG.
- **Multi-Model Team Collaboration and Consensus Aggregator**: Parallelized team reasoning using SubAgentManager (spawning specialized experts in coding, planning, and vision) combined with a ConsensusAggregator to resolve contradictions and output a unified master response.
- **Local MCP Client Host**: Thread-safe host architecture that loads data/mcp_config.json, manages stdio-based MCP servers (e.g., Tavily, Spotify) as background subprocesses, exposes them dynamically, and streams logs to the UI settings drawer.
- **Multi-Format Attachment Processor and Image Lightbox**: Attachment manager that processes PDFs, Code, Log files, and Images (rendering them as base64 in the UI and routing them natively via provider-level vision APIs like Gemini and OpenAI).
- **Stateful Terminal Manager**: Real Windows native PTY control using pywinpty with prompt-cleaning ANSI filter.
- **Direct Provider REST APIs**: Leverages native, zero-quota REST dispatchers for direct API calls, with automatic failover fallback to OpenRouter.

---

## System Architecture

### Pipeline Flow

```
                     ┌──────────────────┐
                     │    User Input    │
                     └────────┬─────────┘
                              │
                              ▼
                     ┌──────────────────┐
                     │   Orchestrator   │
                     └────────┬─────────┘
                              │ (Decomposes & Selects)
                              ▼
             ┌────────────────┼────────────────┐
             │                │                │
             ▼                ▼                ▼
      ┌────────────┐   ┌────────────┐   ┌────────────┐
      │ Sub-Agent  │   │ Sub-Agent  │   │ Local MCP  │
      │  (Coding)  │   │(Reasoning) │   │   Tools    │
      └──────┬─────┘   └─────┬──────┘   └─────┬──────┘
             │                │                │
             └────────────────┼────────────────┘
                              │ (Submits Proposals)
                              ▼
                     ┌──────────────────┐
                     │    Synthesizer   │
                     └────────┬─────────┘
                              │ (Consensus Analysis)
                              ▼
                     ┌──────────────────┐
                     │   Final Output   │
                     └──────────────────┘
```

### Dedicated Model Roles

Model assignments can be mapped to specialized system roles under the UI Settings panel:

| Role | Primary Responsibility |
| :--- | :--- |
| **Orchestrator** | Session supervisor, intent classifier, and router. |
| **Cheap Fast Model** | Simple chats, standard inquiries, and text-only queries. |
| **Reasoning Engine** | Complex algorithmic design, planning, math, and workflows. |
| **Coding Specialist** | Code generation, debugging, refactoring, and AST scanning. |
| **Multimodal Processor** | Image inspection, video parsing, PDF scanning, and audio OCR. |
| **Memory / Summarizer** | Fact extraction, database pruning, context summarization. |
| **Speech-to-Text (STT)**| Micro-button voice dictation to chat box. |
| **Text-to-Speech (TTS)**| Speech synthesis voice response. |

---

## Directory Structure

```
AgenticAI/
├── src/
│   ├── api/             # FastAPI endpoints & WebSocket communication
│   ├── controller/      # Model routers, prompt templates & context assembly
│   ├── models/          # Direct HTTP client wrappers & OpenRouter bindings
│   ├── memory/          # SQLite stores, ChromaDB indexes, & Redis sync
│   ├── processors/      # Image base64 generators & file parsing utilities
│   ├── tools/           # Terminal manager, file explorer, & MCP hosts
│   ├── aggregators/     # Sub-agent managers & consensus combiners
│   └── utils/           # Configuration managers and cost trackers
├── ui/
│   ├── src-tauri/       # Tauri configuration & Rust window-tray IPC handles
│   └── src/             # React + Ant Design glassmorphic UI components
├── bin/
│   └── redis/           # Portable pre-compiled Redis binaries
└── data/
    ├── sqlite/          # Main SQLite storage files
    ├── chroma/          # Vector embeddings index databases
    └── documents/       # Local cached documents & media files
```

---

## Installation and Configuration

### Prerequisites

- **Python 3.9+**
- **Node.js v18+** and **npm**
- **Cargo / Rust** (Only required if compiling Tauri binaries from source)

### 1. Repository Setup

Clone this repository and set up a virtual environment:

```bash
git clone <repository-url>
cd AgenticAI

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Python backend packages
pip install -r requirements.txt
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

Open `.env` and set the following basic parameters:
```env
# OpenRouter API Key (required for orchestrator routing and fallbacks)
OPENROUTER_API_KEY=your_key_here

# Local Database Configuration (optional overrides)
SQLITE_DB_PATH=data/agenticai.db
CHROMA_DB_PATH=data/chroma
```

### 3. Direct API Keys Configuration

For direct API providers (Google AI Studio, OpenAI, Anthropic, Groq, Mistral AI), API keys are entered directly and stored securely in the SQLite database (`api_keys` table) using the Settings interface within the application.

You do not need to add these keys to your `.env` file. To configure keys:
1. Launch the Tauri application.
2. Open the **Settings Modal** (via the gear icon in the UI or tray menu).
3. Navigate to the **Keys & Model Settings** tab.
4. Input your provider keys and click **Test Connection** to verify zero-quota connectivity.
5. Save changes. Keys will be dynamically loaded mid-session.

---

## Running the Application

You can run AgenticAI in CLI mode or launch the Tauri Desktop UI wrapper.

### CLI Mode

To interact directly from the terminal:

```bash
# Start an interactive CLI chat
python main.py chat

# Show system statistics and costs
python main.py stats

# List available models
python main.py models

# Show conversation history
python main.py history
```

### Desktop UI Mode (Tauri)

To launch the desktop interface:

```bash
cd ui
npm run tauri dev
```

This starts the Ant Design dark glassmorphic window, boots the dynamic Python backend, spins up the portable Redis database, and creates a system tray icon on Windows.

---

## Security and Cost Management

- **User-in-the-Loop Permissions**: Operations modifying files, writing to directories, or launching sub-agent tool runs require interactive confirmation or desktop notification consent.
- **Budget Protection**: Configurable in settings, supporting alert thresholds (e.g., 75% warn) and hard caps (100% block/auto-downgrade) to prevent runaway charges.
- **Zero-Quota API Checks**: Model settings screen queries catalog endpoint models directly rather than executing dummy text completions, avoiding unnecessary cost or quota exceptions.
