# AGENTS.md - AgenticAI

### Important:
- Do not remove this "Important:" section.
- Update this AGENTS.md file with new info everytime we decide on something or update something.
- Always keep this file updated so that the future AIs can understand how much work is done and what else to do.
- Always update the notion page for the planning and executed tasks too.
- And also update the Notion page if required.

# AegisDB — Autonomous AI SRE Copilot (Amazon S3 + CockroachDB Architecture)

## Project Overview
AegisDB is an intelligent, multi-model AI-powered SRE (Site Reliability Engineering) agent system developed for the CockroachDB × AWS Hackathon. It utilizes CockroachDB Cloud Serverless for relational memory storage and RAG vector searches (pgvector), and Amazon S3 as the authoritative knowledge base and runbook repository with automated embedding pipelines.

## Goal
Create an intelligent SRE Copilot that runs continuously to monitor services, analyze logs, query CockroachDB performance statistics, suggest playbooks, and automate troubleshooting. The system supports semantic context retrieval, shared memory across sub-agents, local tool execution, and CockroachDB MCP server integration, completely bypassing OpenRouter in favor of direct provider integrations.

## Instructions
- Use phased approach: Phase 1 (CLI), Phase 2 (Background service + UI), Phase 3 (Advanced features)
- Language: Python (user preference), no Python avoidance
- Memory: Start with SQLite + ChromaDB, add Redis later
- File processing: Start with .py, PDF, TXT files, add images with OCR later
- Security: Managed access with permission prompts for read/write operations
- Cost management: Track usage and show warnings
- Model routing: Hybrid approach (rules + ML optimization)
- Primary use case: Personal assistant
- Priority: Low memory usage for now, advanced features for later
- User comfortable with Python, no Windows development experience

### Relevant files / directories
#### Created files:
- /mnt/e/Codes/AgenticAI/AGENTS.md - Project documentation and architecture decisions
- /mnt/e/Codes/AgenticAI/requirements.txt - Python dependencies
- /mnt/e/Codes/AgenticAI/.env.example - Environment variable template
- /mnt/e/Codes/AgenticAI/main.py - Main entry point
- /mnt/e/Codes/AgenticAI/setup.py - Python package setup
- /mnt/e/Codes/AgenticAI/test_system.py - System test script
- /mnt/e/Codes/AgenticAI/example_usage.py - Usage examples
- /mnt/e/Codes/AgenticAI/README.md - Project documentation
- /mnt/e/Codes/AgenticAI/INSTALL.md - Installation guide
- /mnt/e/Codes/AgenticAI/NOTION_TEMPLATE.md - Notion tracking template
#### Created source code directories:
- /mnt/e/Codes/AgenticAI/src/utils/config.py - Configuration management
- /mnt/e/Codes/AgenticAI/src/models/openrouter_client.py - OpenRouter API client
- /mnt/e/Codes/AgenticAI/src/controller/model_router.py - Model routing logic
- /mnt/e/Codes/AgenticAI/src/controller/chat_router.py - Chat routing with context assembly
- /mnt/e/Codes/AgenticAI/src/memory/sqlite_store.py - SQLite memory system with chat enhancements
- /mnt/e/Codes/AgenticAI/src/cli/main.py - CLI interface
- /mnt/e/Codes/AgenticAI/src/tools/basic_tools.py - Basic tool execution
- /mnt/e/Codes/AgenticAI/src/api/chat_server.py - FastAPI chat server backend
#### UI files (Phase 2):
- /mnt/e/Codes/AgenticAI/ui/package.json - UI dependencies
- /mnt/e/Codes/AgenticAI/ui/src/main.tsx - Main UI entry point with glass theme
- /mnt/e/Codes/AgenticAI/ui/src/App.tsx - App component
- /mnt/e/Codes/AgenticAI/ui/src/components/ChatPanel.tsx - Chat UI component
- /mnt/e/Codes/AgenticAI/ui/src/global.css - Glass theme CSS
- /mnt/e/Codes/AgenticAI/ui/src-tauri/Cargo.toml - Rust backend dependencies
- /mnt/e/Codes/AgenticAI/ui/src-tauri/src/lib.rs - Tauri commands for backend control
#### Directory structure created:
- /mnt/e/Codes/AgenticAI/src/ - Main source code
- /mnt/e/Codes/AgenticAI/src/controller/ - Routing logic
- /mnt/e/Codes/AgenticAI/src/models/ - Model wrappers
- /mnt/e/Codes/AgenticAI/src/memory/ - Memory systems
- /mnt/e/Codes/AgenticAI/src/tools/ - Tool definitions
- /mnt/e/Codes/AgenticAI/src/api/ - API server
- /mnt/e/Codes/AgenticAI/src/processors/ - (Empty - for Phase 2)
- /mnt/e/Codes/AgenticAI/src/aggregators/ - (Empty - for later)
- /mnt/e/Codes/AgenticAI/src/utils/ - Shared utilities
- /mnt/e/Codes/AgenticAI/ui/ - Tauri UI (Phase 2)
- /mnt/e/Codes/AgenticAI/data/ - Database and document storage

## Core Architecture

### Dynamic Multi-Model Selection Strategy
AegisDB employs dynamic heterogeneous model routing across all active providers (Google AI Studio Gemini variants, OpenAI, Anthropic, Groq, Mistral AI) with on-the-fly hot swapping:
1. **Orchestrator Role**: Dynamically selectable across Google Gemini variants (2.0 Flash, 2.5 Flash, 3.x), GPT-4o, and Claude.
2. **Coding Specialist**: Dynamically assigned (e.g. DeepSeek V4 Flash, Gemini 2.0 Flash, GPT-4o Mini).
3. **Reasoning Specialist**: Dynamically assigned (e.g. Claude 3.5 Sonnet, DeepSeek V4 Pro, Gemini 2.5 Pro).
4. **Multimodal Specialist**: Dynamically assigned (Gemini 2.0 Flash, GPT-4o Vision).
5. **Background Summarization & Memory**: Dynamically assigned (Gemini 2.5 Flash Lite, GPT-OSS).

**Environment Configuration**
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION` – AWS S3 credentials
- `GEMINI_API_KEY` – Google AI Studio key
- `COCKROACH_DATABASE_URL` – Cloud Serverless cluster URL

### Chat Enhancements
- **Persistent chat history**: SQLite stores raw user and assistant turns.
- **Compressed summaries**: After each turn, the free `gpt-oss-120b` model compacts the content to ≤ 400 tokens for efficient context.
- **Smart tags**: Automatic tag extraction (via optional LLM or heuristic) enables retrieval of related past turns when a new prompt mentions similar topics.
- **Default chat model**: Configurable via env `AGENTICAI_DEFAULT_CHAT_MODEL` (defaults to `qwen3.5-flash-02-23`).
- **System prompt**: Configurable via env `AGENTICAI_SYSTEM_PROMPT` to keep a consistent persona across all responses.

### Pipeline
```
User Input → Controller → Decision → Model/Tool → Aggregation → Output
```

## Technical Decisions

### 1. Stack Choice
- **Primary**: Python (LangChain ecosystem)
- **Memory**: SQLite + ChromaDB (RAG), Redis later
- **UI**: Tauri (Rust + TypeScript) for Windows tray app
- **File Processing**: .py, PDF, TXT initially

### 2. Phase Approach
**Phase 1**: Core CLI with model switching + basic memory
**Phase 2**: Background service + system tray UI + Document RAG
**Phase 3**: Tool Execution (MCP-style), Intelligent Routing, Advanced Redis Memory [COMPLETED] + Stateful Shared Terminal, System Tray polish, Gemini Audio/Video processing [IN PROGRESS]

### 3. Memory Architecture
- **Short-term**: In-memory conversation context
- **Medium-term**: SQLite (conversation history, tool logs)
- **Long-term**: ChromaDB (vector embeddings for RAG)
- **Future**: Redis for multi-process sync

### 4. Security Model
- Managed file system access with permission prompts
- Tool execution with user confirmation
- Read/write/update permissions configurable

### 5. Cost Management
- Track token usage per model
- Budget warnings at thresholds
- Performance/cost optimization

### 6. Model Routing Logic
- Hybrid approach: Rules + ML optimization
- Task type detection → model selection
- Cost/performance/latency tradeoffs

## Commands

- Install: `pip install -r requirements.txt`
- Dev: `python main.py` (CLI mode)
- Build: Tauri build for Windows
- Test: `pytest tests/`
- Lint: `ruff check src/`

## Testing

- Single test: `pytest tests/test_module.py`
- Watch mode: `pytest --watch`

## Project Structure

```
src/
├── controller/        # Main routing logic
├── models/           # OpenRouter model wrappers
├── memory/           # SQLite + ChromaDB memory
├── tools/            # Tool definitions & execution
├── processors/       # File processing (.py, PDF, TXT)
├── aggregators/      # Multi-model output combination
└── utils/           # Shared utilities

ui/
├── src-tauri/        # Rust backend (Tauri)
└── src/             # TypeScript frontend (React/Vue)

data/
├── sqlite/          # SQLite databases
├── chroma/          # Vector embeddings
└── documents/       # Processed files
```

- API keys in `.env` (never commit)
- AWS Bedrock permissions and direct provider keys required
- Windows background service via Tauri
- CockroachDB cloud-managed MCP-style tool architecture

### Amazon S3 Knowledge Base Integration (Aug 17, 2026):
- **AWS Pivot**: AWS Bedrock replaced with Amazon S3 (`cockroachsre-knowledge-base`, `ap-south-1`) as the required AWS service. Reason: AWS account not verified for Bedrock after 5 days. S3 is a better architectural fit — it is the source of truth for runbooks/incident logs with a direct indexing pipeline into CockroachDB.
- **S3 Knowledge Base Module (`src/tools/s3_tools.py`)**: Built `S3KnowledgeBase` class with `upload_runbook`, `upload_incident_log`, `upload_postmortem`, `fetch_runbook`, `fetch_object`, `list_runbooks`, `list_incident_logs`, `list_all`, `sync_to_vector_store`, `fetch_and_index`, and `test_connection`. Module-level `s3_kb` singleton. Credentials loaded from `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_REGION` env vars.
- **S3 → CockroachDB Vector Pipeline**: `sync_to_vector_store()` and `fetch_and_index()` pull content from S3 and immediately embed+store it into CockroachDB's `documents` table via `VectorMemoryStore.add_document()`. This creates the full `S3 → CockroachDB pgvector → Agent semantic search` pipeline.
- **Backend JSON-RPC Endpoints (`src/api/embedded_backend.py`)**: Added `s3_test_connection`, `s3_list_all`, `s3_upload_runbook`, `s3_fetch_runbook`, `s3_sync_to_cockroachdb`, `s3_upload_incident` routes and async handler methods using `run_in_executor` for non-blocking I/O.
- **Seed Script (`scripts/seed_s3_runbooks.py`)**: Uploads 5 SRE runbooks (`db-connection-failures.md`, `high-cpu-playbook.md`, `memory-leak-detection.md`, `incident-response-sop.md`, `cockroachdb-backup-restore.md`) and 2 incident logs (`INC-2026-001`, `INC-2026-002`) to S3, then indexes all 7 objects into CockroachDB pgvector. **Successfully verified — 7 objects in S3, all indexed.**
- **Env Config**: Added `S3_BUCKET_NAME=cockroachsre-knowledge-base` to `.env`. AWS credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION=ap-south-1`) now serve both S3 and any future Bedrock use. IAM user has `AmazonS3FullAccess` policy attached.
- **LLM Decision**: Agent brain is **Google Gemini 2.0 Flash** (free tier, 1500 req/day) configured via the existing UI API key input box in Settings. No AWS LLM required — the hackathon only requires at least 1 AWS service, not an AWS LLM.

### CockroachSRE Database, Vector Store, & Bedrock Purge:

- **CockroachDB Memory Store Migration (`src/memory/cockroach_store.py`)**: Migrated raw SQLite store to a fully PostgreSQL-wire-compatible CockroachDB memory layer. Created standard indexes, mapped chat history, global memories, role assignments, api keys, and tool calls. Dropped foreign key constraints from `messages` to allow flexible context payloads.
- **pgvector Vector Store Migration (`src/memory/vector_store.py`)**: Replaced local ChromaDB instance with an inline pgvector store. Added `embedding VECTOR(384)` columns directly to `documents`, `messages`, and `user_memories` tables to store and retrieve vectors with native database joins. Configured local `SentenceTransformer('all-MiniLM-L6-v2')` model to execute 384-dimensional cosine distance matches (`<=>`) with 100% zero-quota free local embeddings.
- **OpenRouter Purge & AWS Bedrock Dispatcher (`src/models/provider_router.py`)**: Completely purged OpenRouter connection clients, endpoint configurations, and silent pass-through fallbacks. Configured direct `boto3` client Converse API integrations to support AWS Bedrock reasoning models (e.g. Claude 3.5 Sonnet v2) with automatic key credential parsing and dynamic region matching. Added `bedrock` provider controls directly to Tauri UI settings drawer.

### Windows Native Migration, Terminal Fixes & Document RAG:
- **Terminal Manager (`src/tools/terminal_manager.py`)**: Migrated to `pywinpty` on Windows. Fixed PTY read signature (`read(blocking=False)`). Implemented `clean_ansi()` logic with PSReadLine cursor-positioning code splitting (`\x1b[row;colH`) and prompt-grouping line filters to eliminate all intermediate typing typos (`ccdcd`, `llsls`).
- **Web Search (`src/tools/basic_tools.py`)**: Updated dependencies to use `ddgs>=9.0.0` with fallback for `duckduckgo-search`.
- **Tauri Python Resolver (`ui/src-tauri/src/lib.rs`)**: Added dynamic ancestor traversal to locate project root and `.venv/Scripts/python.exe` reliably regardless of working directory.
- **Document RAG & Multi-Format Processor (`src/processors/file_processor.py`)**: Added support for `.py`, `.pdf`, `.txt`, `.md`, `.json`, `.csv`, `.js`, `.ts`, `.tsx`, `.html`, `.css`, `.rs`, `.log`, `.png`, `.jpg`, `.jpeg`, `.webp`, `.mp3`, `.mp4`, `.wav`, etc. Embedded base64 `data_url` generation for image files to bypass webview asset protocol origin restrictions. Integrated ChromaDB document chunk retrieval (`search_documents`) into `ChatRouter._assemble_context`.
- **Gemini / ChatGPT Style Attachment UI (`ui/src/components/ChatPanel.tsx`)**:
  - Rendered square rounded thumbnail cards (`68x68px`) with hover scale, zoom overlays, and close buttons for attached images in the draft input container.
  - Rendered attached thumbnail cards above user chat bubbles in message history.
  - Built full-screen **Image Lightbox Zoom Modal** for high-resolution image inspection.
  - Implemented auto-healing `onError` handler on `<img />` tags to dynamically fetch Base64 Data URLs from Python if asset protocol loading fails.
  - Updated `sendMessage` payload to automatically append file tags (`[Attached File: ...| Path: ...]`) to guarantee 100% RAG retrieval even for non-semantic prompts.
- **Windows System Tray & Background Service (`ui/src-tauri/src/lib.rs` & `ui/src/components/ChatPanel.tsx`)**:
  - Intercepted `CloseRequested` window event to minimize the app to the Windows System Tray on close instead of exiting.
  - Built native System Tray Context Menu (`🟢 AgenticAI (Engine Active)`, `🖥️ Show Studio Window`, `➕ Start New Chat`, `⚡ Toggle AI Engine`, `❌ Quit AgenticAI`).
  - Added left-click toggle on the System Tray icon to instantly hide/unhide and focus the app window.
  - Connected `trigger-new-chat` and `trigger-toggle-engine` IPC event triggers from Tauri to React.
- **MCP Configuration & Notion Master Project Tracker**:
  - Configured Notion MCP server integration globally in settings.
  - Successfully connected to Notion workspace via MCP tools (`call_mcp_tool`).
  - Created and updated standalone top-level Notion page: `🚀 AgenticAI - Master Project Tracker & Executed Status` (Page ID: `341c8b7b-66a5-80ed-b7ba-dddb5d3ea0d9`).
  - Populated Notion page with project overview, model routing architecture, completed Phase 1/2/3 milestones, active tasks, and future roadmap.
- **Advanced Redis Memory Synchronization & Auto-Start (`src/memory/redis_store.py`)**:
  - Bundled portable Redis v5.0 binary at `bin/redis/redis-server.exe` — zero install required.
  - Auto-starts bundled Redis on app launch, stores data in `data/redis/dump.rdb`.
  - Registers `atexit` hook to cleanly terminate Redis when the app quits.
  - Uses `protocol=2` (RESP2) for redis-py v5+ compatibility with bundled Redis v5.0.
  - Implemented retry loop (10x × 0.5s) to wait for Redis to fully bind port 6379 before connecting.
  - Implemented multi-process Pub/Sub message broadcasting (`publish_message`, `subscribe_events`).
  - Implemented active session state and assembled context caching (`cache_assembled_context`, `get_assembled_context`).
  - Implemented distributed locking (`acquire_lock`, `release_lock`) for multi-process concurrency control.
  - Added auto-reconnection and graceful SQLite fallback when Redis is offline.
- **Global Memory & Persona System UI (`ui/src/components/ChatPanel.tsx` & `src/api/embedded_backend.py`)**:
  - Fixed memory loading invoke call (`get_all_memories`).
  - Fixed Tauri IPC parameter names (`messageId`, `memoryId`) for `update_memory` and `delete_memory` so editing and deleting entries work cleanly.
  - Added automatic memory fetching whenever the Settings modal opens.
  - Built **Add New Global Memory** form allowing manual entry creation.
  - Implemented `add_memory` endpoint across JSON-RPC backend (`embedded_backend.py`), Tauri IPC (`lib.rs`), SQLite (`sqlite_store.py`), and ChromaDB vector store.
  - Full support for viewing, adding, editing, deleting, and auto-extracting conversational facts globally.
- **Smart Memory Curation & Auto-Consolidation (`src/models/openrouter_client.py` & `src/controller/chat_router.py`)**:
  - Refined memory extraction system prompt to strictly filter out transient commentary ("they fixed it", "duration was 5 mins", "ran a terminal command") and extract ONLY enduring personal facts, user preferences, and system specs.
  - Built `consolidate_memory_actions` engine: Compares new facts against existing memories to automatically `UPDATE`, `ADD`, or `SKIP` entries in both SQLite and ChromaDB vector database.
- **Dark Glass Modal & App-Wide Theme System (`ui/src/main.tsx`, `ui/src/global.css`, `ui/src/components/ChatPanel.tsx`)**:
  - Configured `ConfigProvider` with `algorithm: theme.darkAlgorithm` globally in `main.tsx` so all Ant Design components (Modals, Cards, Popconfirms, Inputs, Tooltips, Lists) default to dark mode.
  - Applied dark glassmorphic CSS overrides (`rgba(15, 23, 42, 0.95)`, `20px` backdrop blur, cyan focus outlines, dark input controls) matching the overall app design.
- **Multi-Model Sub-Agent Collaboration & Output Aggregator (`src/aggregators/sub_agent_manager.py` & `src/aggregators/consensus_aggregator.py`)**:
  - Built `SubAgentManager`: Spawns parallel background workers (`deepseek/deepseek-v4-flash` for coding, `deepseek/deepseek-v4-pro` for reasoning/architecture, and `google/gemini-2.5-flash-lite` for multimodal attachments) using `asyncio.gather()`.
  - Built `ConsensusAggregator`: Synthesizes sub-agent outputs via `google/gemini-2.5-flash-lite` or `qwen/qwen3.5-flash-02-23` to eliminate duplicates, resolve conflicting suggestions, and output a unified master response.
  - Added **🤝 Multi-Model Team** option to the model selection dropdown in `ui/src/components/ChatPanel.tsx`.
- **Model & API Configuration Manager (`src/models/provider_router.py`, `src/memory/sqlite_store.py`, `src/memory/redis_store.py`, `ui/src/components/ChatPanel.tsx`)**:
  - Built `ProviderRouter`: Direct HTTP / SDK dispatching for OpenRouter, OpenAI, Google AI Studio, and Anthropic APIs.
  - Multi-provider API Key storage in SQLite `api_keys` table with `.env` fallback. Added `test_api_key` verification endpoint.
  - Dynamic Role Model Swapping: Update model assignment for any role (Orchestrator, Coding, Reasoning, Multimodal, Synthesizer) directly in Settings. Hot-reloaded into Redis (`set_role_model` / `get_role_model`) and takes effect from the very next prompt mid-session!
  - Added **Key & Model Settings** tab to Settings modal with role assignment cards, API key form, and live key testing.
  - Fixed `SQLiteMemoryStore` class method scope so `save_role_assignment`, `get_role_assignments`, `save_api_key`, `get_api_keys`, `get_api_key_by_provider`, and `delete_api_key` are properly located on `SQLiteMemoryStore` instead of `SessionManager`.
  - Updated Google AI Studio test model target from deprecated `gemini-2.5-flash` to active `gemini-2.0-flash` to resolve HTTP 404 test failures.
  - Multi-Provider Heterogeneous Model Selection & Live Cost Badges: Users can pick a distinct provider (OpenRouter, Google AI Studio, OpenAI, Anthropic) per role card (*Orchestrator, Coding, Reasoning, Multimodal, Synthesizer*). Model dropdowns feature live token cost badges (e.g. `$0.10/1M in, $0.40/1M out`) and automatically grey out (`disabled: true`) deprecated/unsupported models.
  - Zero-Quota API Key Verification: Replaced generation test prompts in `test_provider_key` with lightweight model catalog metadata checks (`/v1beta/models` for Google, `/v1/models` for OpenAI). Eliminates `429 RESOURCE_EXHAUSTED` / token quota errors entirely when verifying keys.
  - Dynamic Orchestrator Resolution: Updated `ChatRouter._select_model` and `_get_assistant_response` to dynamically query Redis (`redis_store.get_role_model("orchestrator")`) and SQLite (`role_assignments`) on every turn so Orchestrator model swaps (e.g. to `qwen3.7-flash`) take effect instantly in chat bubbles.
  - Expanded Google AI Studio Catalog & Fixed Direct API Dispatching: Expanded Google AI Studio model catalog to all 13 active Gemini models (`gemini-3.6-flash`, `gemini-3.5-flash`, `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`, `gemini-3.1-pro`, `gemini-3-flash`, `gemini-2.5-flash`, `gemini-2.5-flash-lite`, `gemini-2.5-pro`, `gemini-2.0-flash`, `gemini-2.0-flash-lite`, `gemini-1.5-flash`, `gemini-1.5-pro`). Routed all main chat responses via `ProviderRouter` so Google AI Studio models execute directly on Google's API (`generativelanguage.googleapis.com`) using `GEMINI_API_KEY`, resolving OpenRouter HTTP `400 Bad Request` errors.
  - Gemini Tool Schema Fix (`items` field validation): Fixed `basic_tools.py` array parameter schemas (`file_paths`) and `ToolManager.get_openai_tools_schema()` by guaranteeing `items: {"type": "string"}` is set on all array parameters, resolving Google Gemini API's strict JSON Schema `GenerateContentRequest.tools[0]...file_paths.items: missing field` error.
  - Strict Provider Routing & Key Check Enforcement: Preserved `provider:model` tuple formatting across Redis (`redis_store`), SQLite (`role_assignments`), and `ChatRouter._select_model` so `ProviderRouter.generate` routes directly to native provider REST APIs (Google AI Studio, OpenAI, Anthropic). If a direct provider is selected without an API key registered, the system prompts the user to add their key in Settings instead of silently falling back to OpenRouter.
  - Eliminated Duplicate Chat Router Methods & Colon Delimiter Parsing: Removed duplicate legacy `_get_assistant_response` method in `chat_router.py` that was shadowing `ProviderRouter`. Enhanced `openrouter_client.py` to automatically parse `provider:model_id` formatted strings and convert colon delimiters to valid OpenRouter slashes (`google/gemini-3.5-flash-lite`), eliminating OpenRouter `400 Bad Request: google:gemini-3.5-flash-lite is not a valid model ID` errors.
  - Background Summarizer & Memory Role Configuration: Added 6th Role Card (**🧠 Background Summarizer & Memory**) in `ChatPanel.tsx` and connected `_summarize_messages`, `extract_memory_facts`, and `consolidate_memory_actions` to route background tasks dynamically through `ProviderRouter`. Users can now configure background summarization and memory extraction to use Google AI Studio (`gemini-2.5-flash-lite`), OpenRouter (`openai/gpt-oss-120b`), OpenAI, or Anthropic.
  - Groq & Mistral AI Provider Support: Implemented direct HTTP REST API dispatching, key verification (`test_provider_key`), and live model catalog retrieval for Groq (`https://api.groq.com/openai/v1`) and Mistral AI (`https://api.mistral.ai/v1`).
  - STT & TTS Role Cards: Added 7th & 8th Role Cards (**🎙️ Speech-to-Text Dictation** & **🔊 Text-to-Speech Voice**) to the Settings modal for configuring transcription and speech synthesis models.
  - Model Catalog & Tracker Tab with SQLite Notes: Created Tab 3 (**📊 Model Catalog & Tracker**) in Settings UI rendering an interactive searchable `<Table>` with ⭐ Favorite model toggles, provider badges, pricing tags, call usage counts, and an inline editable 📝 **Notes** field persisted in SQLite `model_notes` table.
  - Groq Cloudflare HTTP 403 Fix: Added browser `User-Agent` header to all Groq and Mistral HTTP requests in `provider_router.py`, resolving Cloudflare error 1010 during key verification and catalog fetching.
  - Favorite Models Top Sorting: Updated `_handle_get_model_tracker_data` in `embedded_backend.py` and `dataSource` sorting in `ChatPanel.tsx` so ⭐ Favorite models always render at the very top of the Model Catalog & Tracker table.
  - Role Assignment Selection Persistence: Sanitized stored model IDs (`cleanModelId`) and injected fallback options in `ChatPanel.tsx` so background summarizer, STT, TTS, and orchestrator selections persist cleanly without de-selecting when opening Settings.
  - Dedicated STT/TTS Dropdown Filtering: Applied strict keyword filtering to STT and TTS role cards in `ChatPanel.tsx` to display only audio transcription (`whisper`, `stt`, `transcribe`) and speech synthesis (`tts`, `voice`) models. If no TTS/STT models exist for a selected provider, the dropdown renders empty cleanly instead of showing non-audio models.
  - OpenRouter `:free` Model ID Parsing Fix (`openrouter_client.py` & `provider_router.py`): Updated colon-splitting logic in `chat_completion` and `generate` to check if the prefix before `:` is a valid provider name (without `/`). Prevents OpenRouter free model IDs like `nvidia/nemotron-3-ultra-550b-a55b:free` from getting truncated to `"free"`, resolving HTTP 502 Bad Gateway errors.
  - Role Models Unpacking Fix (`ChatPanel.tsx`): Updated `loadRoleModels()` to check `res?.role_models` when loading assignments from backend, ensuring Background Summarizer, STT, and TTS selections persist cleanly upon reopening settings.
  - Option Value Normalization Fix (`ChatPanel.tsx`): Applied `getCleanModelId(m.id, currentProvider)` to option values in `<Select>` so models with provider prefixes like Groq `compound` and `compound-mini` match cleanly without displaying `(Active Assignment)` fallbacks.
  - Sub-Agent Messages Array Restoration (`basic_tools.py`): Restored `messages` prompt construction block in `ask_expert_model`. Resolves `NameError: name 'messages' is not defined` when invoking `pr.generate(...)`.
  - Sub-Agent Role & Model UI Label Rendering (`chat_router.py` & `ChatPanel.tsx`): Updated `chat_router.py` tool log payload to include exact `role` and `model` metadata (`REASONING (Groq: compound)`). Updated UI purple card footer in `ChatPanel.tsx` to render `Role / Model: REASONING (google:gemini-3.6-flash)` below sub-agent tool call cards.
  - Fix Orchestrator & Sub-Agent Name Rendering (`chat_router.py` & `ChatPanel.tsx`): Resolved React state `model_id` key-mapping mismatch (checking `response.model` from JSON-RPC) to correctly display orchestrator model names dynamically. Updated sub-agent execution logs to format role and resolved model name (e.g. `CODING (deepseek/deepseek-v4-flash)`) instead of falling back to default "sub-agent" strings in SQLite and live logs.
  - Fix Redis Status Badge on Reload & Connection Self-Healing (`embedded_backend.py`, `lib.rs`, `redis_store.py` & `ChatPanel.tsx`): Appended `redis_connected` boolean to JSON-RPC health check payload. Added a new `get_backend_health` Tauri command to query Redis status immediately on React app initialization/reload. Optimized `redis_store.py` to support dynamic fast reconnection and limit slow background Redis auto-start subprocess spawning to a single attempt, resolving the `Redis ...` loading and persistent `Off` issues.
  - Multi-line User Input Box & Newline Rendering (`ChatPanel.tsx`): Replaced the single-line input field in the chat panel with a dynamic auto-sizing `Input.TextArea` that supports inserting newlines using `Shift+Enter` and sending messages instantly on pressing `Enter`. Added `whiteSpace: 'pre-wrap'` styling to UI chat bubbles to correctly preserve and render newlines entered by the user or outputted by models.
  - Custom File Explorer Tools (`src/tools/file_explorer_tool.py` & `src/tools/basic_tools.py`): Built file explorer tool class supporting recursive text tree printing (`get_file_tree`), wildcard glob path finder (`find_files`), recursive content search (`grep_search`), and native folder highlights (`open_in_explorer`). Registered all four tools dynamically inside the global `ToolManager` registry.
  - Sub-Agent Tool Execution Loops (`src/aggregators/sub_agent_manager.py` & `src/tools/basic_tools.py`): Upgraded both collaborative pipeline sub-agents and manually-delegated expert agents to support dynamic tool execution loops (up to 5 turns). Injected system directives dynamically telling the sub-agents they have direct access to all system tools.
  - General stdio-based MCP Client Host Integration (`src/tools/mcp_manager.py` & `src/api/embedded_backend.py`): Designed and implemented a thread-safe local MCP Client Host manager that reads config from `data/mcp_config.json`, spawns servers as background subprocesses, conducts formal protocol handshakes, and exposes dynamic tools under the `mcp_[server]_[tool]` namespace prefix. Exposes JSON-RPC endpoints to fetch, add, update, delete servers, and query real-time stderr/stdout logs.
  - Settings Tab 4 🔌 MCP Servers UI (`ui/src/components/ChatPanel.tsx` & `ui/src-tauri/src/lib.rs`): Built a dedicated MCP Settings tab with connection status badges, discovered tool parameter schema listings, a live circular console logs drawer, and CRUD forms to manage server configs dynamically. Integrated Tauri Rust IPC endpoints to relay calls to the FastAPI backend.

  - Automatic OpenRouter Pass-Through Fallback (`provider_router.py`): Enhanced `ProviderRouter.generate` so that if a direct provider (Google AI Studio, Groq, OpenAI, Anthropic, Mistral) is missing a direct API key or encounters an HTTP/network failure, the system automatically routes the user's **exact requested model** (`google/gemini-3.5-flash`, `openai/gpt-oss-120b`, etc.) through OpenRouter using the active OpenRouter key. Eliminates silent Qwen model fallbacks entirely when user-selected models are specified.
  - Dynamic Synthesizer Model Resolution (`consensus_aggregator.py`): Updated `ConsensusAggregator` to dynamically resolve assigned synthesizer models from Redis/SQLite instead of using a hardcoded default model.
  - Unified Database Path Configuration (`config.py`, `.env`, `embedded_backend.py`): Pointed `SQLITE_DB_PATH` in `.env` and `config.py` to `data/agenticai.db` across all backend services, CLI tools, and diagnostic scripts.
  - Pydantic `Message` Content Union & Extraction (`openrouter_client.py`, `provider_router.py`): Updated `Message.content` type annotation to `Optional[Union[str, List[Any], Dict[str, Any]]]` and added `extract_text_content` helper. Allows reasoning models (e.g. DeepSeek R1, Gemini Thinking, Claude 3.7 Sonnet) returning list-based thinking and text blocks to validate cleanly without throwing `pydantic.ValidationError` string type errors.
  - Direct Provider HTTP Exception Handling & Google Payload Fix (`provider_router.py`): Wrapped `urllib.request.urlopen` in `try...except urllib.error.HTTPError` across all direct API dispatchers (`_generate_google_direct`, `_generate_openai_direct`, `_generate_anthropic_direct`, `_generate_groq_direct`, `_generate_mistral_direct`). Formatted Google AI Studio system prompts into top-level `"systemInstruction"` payload objects and merged consecutive same-role turns to avoid Google API consecutive turn rejections.
  - OpenRouter Model Alias Translation (`provider_router.py`): Added `openrouter_aliases` mapping in `_fallback_to_openrouter` (`google/gemini-2.0-flash` -> `google/gemini-2.5-flash`), guaranteeing seamless OpenRouter fallback execution when direct API limits or endpoint deprecations occur.
  - Mistral AI Prefix Alias Resolution (`provider_router.py`): Added `mistralai` and `codestral` prefix alias resolution in `get_api_key_for_provider` and `generate` (`mistralai/mistral-medium-2505`, `mistralai/codestral-2501`). Resolves "No Mistral API Key found" errors when sub-agents or tool calls reference `mistralai/` model IDs.
  - Mistral AI Strict 9-Char Alphanumeric `tool_call_id` Sanitization (`provider_router.py`): Added `_sanitize_mistral_tool_call_id` in `_generate_mistral_direct`. Deterministically hashes OpenAI-style tool IDs (`call_9823478932`) to 9-character alphanumeric strings matching Mistral API's strict regex `^[a-zA-Z0-9]{9}$`. Resolves `HTTP 400 Bad Request: Tool call id was ... but must be a-z, A-Z, 0-9, with a length of 9` errors when using tools or sub-agents with Mistral models.
  - File Attachment Direct Send & IPC Parameter Fix (`ChatPanel.tsx`, `lib.rs`, `embedded_backend.py`): Resolved issue where attached files were blocked from sending when the text input box was empty by updating `sendMessage` guard check to `(!input.trim() && attachedFiles.length === 0)`. Auto-generates file context payload when sending attachments without prompt text. Added dual IPC parameter support (`filePath`/`file_path`, `sessionId`/`session_id`, `model`/`model_override`) across Tauri Rust and Python JSON-RPC backend handlers.
  - Mistral/Provider API Key Provider Alias Mismatch Fix (`sqlite_store.py`): `get_api_key_by_provider` was doing an exact SQL `WHERE provider = 'mistral'` match, but keys saved by the UI were stored under `'mistralai'`. Updated to use an alias group set (`{'mistral', 'mistralai', 'codestral'}`) and `WHERE provider IN (...)` query, so any stored variant is found correctly. Same fix covers `google`/`gemini`, `anthropic`/`claude`.
  - `pixtral` Model ID Prefix Fix (`provider_router.py`): Added `"pixtral"` to Mistral/Codestral model name checks in both the OpenRouter fallback `_fallback_to_openrouter()` and the OpenRouter dispatch section so Pixtral vision models get correctly prefixed as `mistralai/pixtral-...` on OpenRouter. Previously, pixtral model IDs fell through all prefix checks and were sent unprefixed, causing HTTP 400 errors.
  - MultiModal Sub-Agent File Attachment Forwarding (`sub_agent_manager.py`, `chat_router.py`): Fixed two-layer issue: (1) `chat_router.py` was detecting attachments via `[Attached Image:]` tag only — updated to parse `[Attached File: name | Path: ...]` regex and extract file paths. (2) `SubAgentManager._call_agent()` now accepts `file_paths` parameter, reads image files from disk, base64-encodes them, and constructs OpenAI-compatible `image_url` content blocks before sending to the multimodal agent. Non-image files are embedded as text content.
  - Google AI Studio `inlineData` Vision Support (`provider_router.py`): Rewrote `_generate_google_direct()` to convert OpenAI-style `image_url` content blocks into Gemini's native `inlineData: {mimeType, data}` format. Previously, `extract_text_content()` stripped all image data from content lists before building the Gemini API payload.
  - OpenAI Direct API Vision Content Block Preservation (`provider_router.py`): Updated `_generate_openai_direct()` to preserve `image_url` and `text` typed content blocks when message content is a list, instead of stripping them to plain text via `extract_text_content()`.
- **Spotify MCP Server & Windows CLI Autolaunch Patches (`data/mcp-spotify-server/`, `auth.js`, `logger.js`)**:
  - Pre-installed the `@darrenjaws/spotify-mcp` package locally to run offline and bypass Node v24 npx peer dependency bugs.
  - Patched `auth.js` to replace Windows browser launch commands with `cmd.exe /c start` utilizing `{ shell: true }` and outer quotes, resolving `cmd.exe` command-line argument truncation bugs at `&` characters.
  - Wrapped dynamic `child_process.spawn` calls in robust `try...catch` and dynamic import Promise `.catch()` handlers to eliminate fatal unhandled promise rejections that crash the Node.js process.
  - Patched `logger.js` to catch JS `Error` instances and print their full message/stack trace instead of serializing to empty JSON `{}` logs.
  - Created a manual OAuth authentication script (`data/test_spotify_auth.py`) that boots the server and holds the callback listener open for up to 5 minutes to allow stress-free manual browser authorization.
- **Sub-Agent Output Truncation & Persisted Reload Fixes (`sub_agent_manager.py` & `chat_router.py`)**:
  - Fixed sub-agent output truncation in Multi-model team mode by streaming the full response text instead of limiting the payload to 300 characters.
  - Implemented database persistence for all sub-agent runs in Multi-model team mode, saving each expert's output as a `role="sub_agent"` message in the SQLite database on turn completion.
  - Implemented database persistence for all standard system tool calls in "Auto" mode, compiling detailed tool execution cards (tool name, arguments, and truncated result output) and saving them to the database. These additions allow all purple tool/sub-agent bubbles to reload and display correctly on app/session refreshes.
- **Model Configuration & Routing Cleanup (`config.py` & `model_router.py`)**:
  - Updated `model_qwen` default to `"qwen/qwen3.7-flash"` to match `.env`.
  - Added support for `model_deepseek` and `model_gemini_pro` settings fields to load from corresponding `.env` keys.
  - Aligned `model_deepseek_flash` to use the `model_deepseek` override value if specified.
  - Replaced legacy `model_deepseek` attribute reference in `model_router.py` with standard `model_deepseek_flash`.
  - Resolved complexity routing bug by changing config range keys from (`7-10`, `11-12`) to (`7-9`, `10-12`) to match the keys queried by `ModelRouter`.
- **Tavily MCP Search Integration**:
  - Pre-installed and integrated the Tavily search client server as a local MCP server, providing robust fallback web search capability.
- **Professional Project Documentation Rewrite**:
  - Rewrote the main project `README.md` to professionally highlight the core features, modular system architecture (heterogeneous routing, sub-agent consensus aggregation, local MCP server hosting), zero-dependency portable Redis memory configuration, installation prerequisites, and setup instructions.
- **Antigravity Skills Vault & Global Skills Integration**:
  - Cloned the open-source [`rmyndharis/antigravity-skills`](https://github.com/rmyndharis/antigravity-skills) repository to `E:\Codes\AgenticAI\antigravity-skills-temp`.
  - Installed a curated collection of 11 developer skills (`python-pro`, `fastapi-pro`, `async-python-patterns`, `uv-package-manager`, `ai-engineer`, `rag-implementation`, `vector-database-engineer`, `embedding-strategies`, `react-state-management`, `frontend-developer`, and the global `antigravity-skills-manager`) directly into the global customizations directory (`C:\Users\SAURAV\.gemini\config\skills/`).
  - These skills are now available globally and automatically loaded on-demand by Antigravity using progressive disclosure to optimize token usage.
- **CockroachDB Cloud Managed MCP Streamable HTTP Transport (`src/tools/mcp_manager.py`, `data/mcp_config.json`)**:
  - Resolved HTTP `405 Method Not Allowed` when connecting to `https://cockroachlabs.cloud/mcp`.
  - Migrated `HttpMcpClient` from SSE (`sse_client` over HTTP GET) to Streamable HTTP transport (`streamable_http_client` with `create_mcp_http_client` over HTTP POST).
  - Updated `data/mcp_config.json` command for `cockroach` server from `"sse"` to `"http"`.
  - Added intelligent header resolution for `mcp-cluster-id` and Bearer token parsing from `COCKROACH_MCP_API_KEY` / `COCKROACH_CLOUD_API_KEY` / `.env` / database.

- **UI & Role Configuration Cleanup (`ui/src/components/ChatPanel.tsx`)**:
  - Removed "Model Catalog & Tracker" tab from Settings modal to streamline agent configuration.
  - Removed Speech-to-Text (STT) and Text-to-Speech (TTS) role cards from agent role settings.
  - Retained core 6 active agent roles: Main Orchestrator, Coding Sub-Agent, Reasoning Sub-Agent, Multimodal Specialist, Consensus Synthesizer, Background Summarizer & Memory.

- **Complete Codebase Emoji Purge (`ui/`, `src/`, `scripts/`)**:
  - Purged all emojis from the user interface (`ChatPanel.tsx`, `lib.rs` native Windows system tray menu, modal titles, dropdown items).
  - Purged all emojis from backend Python source files (`consensus_aggregator.py`, `sub_agent_manager.py`, `provider_router.py`, `basic_tools.py`, `file_explorer_tool.py`, `config.py`, `test_mcp_client.py`, `test_mcp_normalization.py`, `scripts/init_cockroach.py`, `scripts/seed_s3_runbooks.py`, `scripts/test_sre_tools.py`, `scripts/test_vector_store.py`).
  - Replaced emojis with clean, structured standard tags (`[INFO]`, `[SUCCESS]`, `[WARNING]`, `[ERROR]`, `[TEAM]`, `[SUB-AGENT]`, `[SECURITY]`, `[DIR]`, `[FILE]`, `[ROOT]`). Verified with repo-wide regex scanner: 0 emojis remaining.

- **Google AI Studio Schema Sanitizer & Tool Translation (`src/models/provider_router.py`)**:
  - Fixed Google AI Studio HTTP 400 `Proto field is not repeating, cannot start list` error caused by nested tool schemas containing array types (e.g. `type: ["object", "null"]`), `$defs`, and `$ref` references (e.g. from MCP tools like Notion).
  - Implemented `_sanitize_schema_for_gemini`: recursively inlines `$ref` from `$defs`/`definitions`, simplifies `anyOf`/`oneOf`/`allOf`, converts array types to single scalar strings with `nullable: true`, enforces mandatory `items` for array types, and strips unsupported metadata fields.
  - Implemented tool name normalization mapping non-alphanumeric characters (e.g. `API-post-search` -> `API_post_search`) with bidirectional translation on emitted function calls.
- **SRE Console 1st Tab & Direct AWS S3 Synchronization (`ui/src/components/ChatPanel.tsx`, `ui/src-tauri/src/lib.rs`)**:
  - Reordered Settings modal tabs to prioritize operations: **1st Tab: SRE Console**, **2nd Tab: MCP Servers**, **3rd Tab: Models & API Keys**, **4th Tab: Memories & Persona**.
  - Added dedicated **"Sync from AWS S3"** action button in the SRE Console header with live spinner, invoking `s3_sync_to_cockroachdb` via Tauri IPC and refreshing incident/runbook/fix tables.
  - Configured automatic SRE data preloading in `initializeBackend` on app startup so all active incidents, playbooks, and resolution histories are immediately rendered with zero lag.
- **Atomic Clean Wipe-and-Replace Vector Lifecycle (`src/memory/vector_store.py`)**:
  - Upgraded `VectorMemoryStore.add_document()` to use atomic transaction scoped replacement (`DELETE FROM documents WHERE source = %s` followed by fresh chunk `INSERT`s) eliminating stale "ghost chunks" when documents are shortened or modified.
  - Added `delete_document(file_path)` to remove all chunks for a specific document/S3 key.
  - Added `clear_all_documents()` for full knowledge base vector purges and resets.
- **Security & Credential Leakage Audit for CockroachDB x AWS Hackathon (Aug 18, 2026)**:
  - **Zero Credential Leakage**: Performed deep regex and git commit history scan for AWS keys (`AKIA...`), Google AI Studio keys (`AIza...`), OpenAI keys (`sk-...`), and database credentials. Verified zero live secrets committed in source code or Git history.
  - **Sanitized Documentation & Configuration Templates**: Sanitized `README.md` and `.env.example` to use generic connection placeholders (`postgresql://username:password@your-cluster.cockroachlabs.cloud:26257/defaultdb?sslmode=verify-full`, `COCKROACH_MCP_CLUSTER_ID=YOUR_COCKROACH_MCP_CLUSTER_ID`, `S3_BUCKET_NAME=cockroachsre-knowledge-base`).
  - **Defensive Dotenv Auto-Loading (`src/memory/cockroach_store.py`, `src/memory/vector_store.py`)**: Enhanced `_get_conn()` in both database layers to automatically locate and load `.env` from project root if `COCKROACH_DATABASE_URL` is missing from `os.environ`, preventing crashes during standalone script and test execution.
  - **Async/Await Fix in FastAPI Backend (`src/api/chat_server.py`)**: Added missing `await` to `chat_router.chat(...)` in `chat_endpoint`.
  - **Model Alias Cleanup (`src/models/provider_router.py`)**: Cleaned up Google AI Studio model mapping in `_generate_google_direct` to pass through requested model names directly and map legacy aliases safely.
  - **Repository Hygiene & Untracked Binaries**: Removed compiled temporary test binaries (`test.exe`, `test2.exe`, `test.pdb`, `test2.pdb`) and `.patch` files from git tracking. Updated `.gitignore` and `ui/src-tauri/.gitignore` with `*.exe`, `*.pdb`, `*.patch`.
  - **Full Test Suite Verification**: Verified 100% passing tests for `scripts/test_cockroach_store.py` (relational memory, incidents, runbooks, fix history), `scripts/test_vector_store.py` (pgvector cosine search, clean chunk replace), `scripts/test_sre_tools.py` (incident ingestion, fix actions, semantic RAG retrieval), `src/tools/test_mcp_normalization.py` (MCP tool payload normalization), and frontend TypeScript compilation (`npm run build`).
- **Official Rebranding to AegisDB & Brand Icon Deployment (Aug 18, 2026)**:
  - **Brand Assets**: Deployed official SVG brand assets (`appicon.SVG`, `logo.SVG`, `logo_horizontal.SVG`, `logo_mono_dark.SVG`) from `icons/` into `ui/public/` (`logo.svg`, `logo_horizontal.svg`, `appicon.svg`).
  - **Tauri Desktop Icon Generation**: Generated full suite of desktop and mobile application icons (`icon.ico`, `icon.icns`, `128x128.png`, `128x128@2x.png`, `32x32.png`, `StoreLogo.png`, `Square*.png`) via `@tauri-apps/cli` in `ui/src-tauri/icons/`.
  - **Frontend Desktop Shell**: Updated `tauri.conf.json` (`productName: AegisDB`, `identifier: com.aegisdb.app`), `lib.rs` system tray menu (`AegisDB (Engine Active)`), `ChatPanel.tsx` (top navigation bar logo, header titles, draft input, and footer), `index.html`, and `package.json`.
  - **Backend & Documentation**: Updated `chat_server.py`, `embedded_backend.py`, `setup.py`, `README.md`, `AGENTS.md`, and the Master Notion Hub. Verified with complete test suite.
- **Architectural Diagram Redesign (Aug 18, 2026)**:
  - Redesigned the architecture diagram into two clean, uncluttered options: (1) **4-Tier Modular System Architecture** separating Client/Ingest, Multi-Model Orchestration, CockroachDB + AWS S3 Memory/Knowledge, and Diagnostic WinPTY Execution, and (2) **Closed-Loop Self-Healing SRE Workflow**.
  - Saved redesign diagrams and documentation directly to the CockroachAI Notion Hub page (`3b8c8b7b-66a5-809d-bfeb-f380a7bcb0e4`) and its subpage `💡 Ideas & Architecture Planning` (`3b8c8b7b-66a5-81dc-a510-f0bf3061e9db`) for user review before updating the main README.

## Planned Future Roadmap Tasks (Notion Tracked)
- **Task 1: Live Token Usage & Budget Warning Tracker Widget**: Add live token/cost meter in top header bar showing expenditure ($) per session/model with dynamic OpenRouter pricing catalog sync, multi-tier protection (75% Soft Alert, 90% Auto-Downgrade, 100% Hard Cap), sub-agent cost attribution tagging, atomic Redis sync, and an analytics drawer with spending graphs.
- **Task 2: Expanded Native MCP Tools**: Build `SystemMonitorTool` (CPU/RAM/Disk), `ProcessManagerTool` (active task management), and `GitInspectorTool` (git diffs/commits).
- **Task 3: Autonomous Scheduled Background Workflows & Reminders**: One-shot & cron background scheduler for periodic health checks, repo backups, and AI reminders.