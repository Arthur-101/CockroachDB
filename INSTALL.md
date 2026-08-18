# AegisDB — Installation & Setup Guide

> **AegisDB** is an Autonomous AI SRE Copilot powered by CockroachDB Serverless, Amazon S3, and a dynamic multi-model agent team, packaged as a native Windows desktop application (Tauri v2 + React 19) with an embedded Python AI engine.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Step 1 — Clone the Repository](#step-1--clone-the-repository)
3. [Step 2 — Python Virtual Environment & Dependencies](#step-2--python-virtual-environment--dependencies)
4. [Step 3 — Configure Environment Variables (.env)](#step-3--configure-environment-variables-env)
5. [Step 4 — Launch the Application](#step-4--launch-the-application)
6. [Step 5 — Verify All Services](#step-5--verify-all-services)
7. [Troubleshooting](#troubleshooting)
8. [Architecture Overview](#architecture-overview)

---

## Prerequisites

Install all of the following tools **before** cloning:

| Tool | Version | Required For | Install |
|---|---|---|---|
| **Python** | 3.10+ (3.12 recommended) | AI engine, memory, tools | [python.org](https://www.python.org/downloads/) |
| **Node.js + npm** | v18+ | React UI build | [nodejs.org](https://nodejs.org/) |
| **Rust + Cargo** | stable (latest) | Compiling the Tauri desktop window | `winget install Rustlang.Rustup` |
| **Git** | any | Cloning the repo | [git-scm.com](https://git-scm.com/) |

> **⚠️ Important — Rust Restart Required**: After installing Rust, **close and reopen your terminal completely** before continuing. Otherwise `cargo` won't be in your PATH and `npm run tauri dev` will fail with `cargo: program not found`.

### Quick Install (Windows PowerShell)

```powershell
winget install Rustlang.Rustup
winget install OpenJS.NodeJS
winget install Python.Python.3.12
winget install Git.Git
# ← Close and reopen PowerShell after this
```

### Verify Prerequisites

```powershell
python --version    # Should be 3.10+
node --version      # Should be v18+
npm --version       # Should be 9+
cargo --version     # Should be 1.70+ (MUST work before continuing)
git --version
```

---

## Step 1 — Clone the Repository

```powershell
git clone https://github.com/Arthur-101/CockroachDB.git AegisDB
cd AegisDB
```

Your project root is now `AegisDB/`. **All paths below are relative to this root.**

---

## Step 2 — Python Virtual Environment & Dependencies

```powershell
# Create a virtual environment inside the project root
python -m venv .venv

# Activate it (Windows PowerShell)
.venv\Scripts\Activate.ps1

# If you get a PowerShell execution policy error, run first:
# Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

# Install all Python dependencies
pip install -r requirements.txt
```

> **Note**: `requirements.txt` includes `sentence-transformers`, which downloads the `all-MiniLM-L6-v2` embedding model (~90 MB) on first use. This is a one-time download for local zero-quota vector embeddings.

---

## Step 3 — Configure Environment Variables (.env)

Copy the example file and fill in your credentials:

```powershell
copy .env.example .env
notepad .env   # Or open in VS Code / any editor
```

### Required Variables

#### 1. CockroachDB Cloud Serverless *(Required)*

Get a free cluster at [cockroachlabs.cloud/clusters](https://cockroachlabs.cloud/clusters):

```env
COCKROACH_DATABASE_URL=postgresql://username:password@your-cluster.cockroachlabs.cloud:26257/defaultdb?sslmode=require
```

> **Tip**: Use `?sslmode=require` (not `verify-full`) on fresh machines — no certificate download needed.

> **✅ Auto Schema Init**: All CockroachDB tables, indexes, and the `pgvector` extension are **created automatically on first launch**. No SQL scripts to run manually.

#### 2. Amazon S3 Knowledge Base *(Required for Runbook features)*

Create an S3 bucket and IAM user with `AmazonS3FullAccess` at [aws.amazon.com/s3](https://aws.amazon.com/s3):

```env
S3_BUCKET_NAME=your-s3-bucket-name
AWS_ACCESS_KEY_ID=YOUR_AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY=YOUR_AWS_SECRET_ACCESS_KEY
AWS_REGION=ap-south-1
```

#### 3. AI Model Provider Keys *(At least one required)*

Google Gemini is recommended — free tier provides 1,500 requests/day:

```env
# Recommended: Google AI Studio (free)
# Get key at: https://aistudio.google.com/app/apikey
GEMINI_API_KEY=YOUR_GEMINI_API_KEY

# Optional: Additional providers (can also be added later in the Settings UI)
OPENAI_API_KEY=YOUR_OPENAI_API_KEY
ANTHROPIC_API_KEY=YOUR_ANTHROPIC_API_KEY
GROQ_API_KEY=YOUR_GROQ_API_KEY
MISTRAL_API_KEY=YOUR_MISTRAL_API_KEY
OPENROUTER_API_KEY=YOUR_OPENROUTER_API_KEY
```

### Optional Variables

```env
# CockroachDB Cloud Managed MCP Server (enables live DB observability tools)
COCKROACH_MCP_URL=https://cockroachlabs.cloud/mcp
COCKROACH_MCP_CLUSTER_ID=YOUR_COCKROACH_MCP_CLUSTER_ID
COCKROACH_MCP_API_KEY=YOUR_COCKROACH_CLOUD_API_KEY

# Cost guardrails
COST_WARNING_THRESHOLD=5.0
COST_LIMIT=20.0
```

> **Security**: The `.env` file is in `.gitignore` and is **never** committed to the repository or baked into the compiled app binary. It lives only on your local machine and is read at runtime.

---

## Step 4 — Launch the Application

### Option A: Desktop Studio *(Recommended)*

Runs the full Tauri native desktop app with the React 19 glass-theme UI:

```powershell
cd ui
npm install        # First time only — installs JS/TypeScript dependencies (~3 min)
npm run tauri dev  # Compiles Rust + launches the desktop window
```

> **First launch note**: `npm run tauri dev` compiles the Rust backend on first run (~3–5 minutes). Subsequent launches are near-instant.

On startup the app automatically:
1. Detects and starts your Python virtual environment engine
2. Auto-provisions all CockroachDB tables and pgvector indexes
3. Connects to Amazon S3
4. Starts the bundled portable Redis server (zero install)
5. Opens the native desktop window

### Option B: Headless CLI Mode

Runs the Python AI engine directly in your terminal with no desktop window:

```powershell
# From the project root, with .venv activated
python main.py chat
```

---

## Step 5 — Verify All Services

Run the automated test suite to confirm every service is connected:

```powershell
# From the project root (with .venv active)

# 1. CockroachDB ACID Relational Layer & Session Storage
python scripts/test_cockroach_store.py

# 2. CockroachDB pgvector Semantic Search (cosine distance <=>)
python scripts/test_vector_store.py

# 3. SRE Incident Lifecycle, Runbook Retrieval & Fix History
python scripts/test_sre_tools.py

# 4. Seed Amazon S3 with SRE Runbooks & Sync to CockroachDB pgvector
python scripts/seed_s3_runbooks.py

# 5. Build the React frontend bundle (verifies Node/TypeScript setup)
cd ui && npm run build && cd ..
```

All 5 should complete with no errors. ✅

---

## Troubleshooting

### ❌ `cargo: program not found` when running `npm run tauri dev`

**Cause**: Rust/Cargo is not installed or not in PATH.

```powershell
winget install Rustlang.Rustup
# ← Close terminal completely, reopen, then retry
cargo --version
```

---

### ❌ PowerShell: `.ps1 cannot be loaded, execution policy`

**Cause**: Windows blocks unsigned PowerShell scripts by default.

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
.venv\Scripts\Activate.ps1
```

---

### ❌ CockroachDB: `SSL connection required` or `Connection refused`

**Cause**: Wrong `sslmode` or IP not allowlisted in CockroachDB Cloud.

1. Change your URL to use `?sslmode=require` (not `verify-full`).
2. In [CockroachDB Cloud Console](https://cockroachlabs.cloud/clusters) → **Networking** → **Authorized Networks** → Add `0.0.0.0/0` for development.

---

### ❌ Amazon S3: `NoCredentialsError` or `Access Denied`

**Cause**: Missing or incorrect AWS credentials.

1. Double-check `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in `.env`.
2. In [AWS IAM Console](https://console.aws.amazon.com/iam/), verify your user has `AmazonS3FullAccess` attached.
3. Confirm `AWS_REGION` matches your bucket's region exactly (e.g. `ap-south-1`).

---

### ❌ `pip install` fails on `psycopg2` or `sentence-transformers`

**Cause**: Missing Microsoft C++ Build Tools.

```powershell
winget install Microsoft.VisualStudio.2022.BuildTools
# Then retry:
pip install -r requirements.txt
```

---

### ❌ AI model returns 404 or no response

**Cause**: Missing or incorrect API key for the configured provider.

1. Launch the app → click **⚙️ Settings** → **Keys & Models** tab.
2. Enter your API key and click **Test Key**.
3. Switch to **Gemini 2.0 Flash** (Google AI Studio) — most generous free tier.

---

### ❌ Port 1430 already in use

**Cause**: Vite dev server port conflict from a previous run.

```powershell
netstat -ano | findstr :1430
taskkill /PID <pid_number_here> /F
```

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────┐
│       AegisDB Native Desktop Window (Tauri v2)       │
│       React 19 + TypeScript + Glass Theme UI         │
└────────────────────────┬─────────────────────────────┘
                         │ Tauri IPC Commands
                         ▼
┌──────────────────────────────────────────────────────┐
│              Rust Native Layer (Tauri)               │
│  • Windows System Tray   • Process Lifecycle Manager │
│  • JSON-RPC Pipe Bridge  • Redis Auto-Start          │
└────────────────────────┬─────────────────────────────┘
                         │ Async JSON-RPC (stdin/stdout)
                         ▼
┌──────────────────────────────────────────────────────┐
│              Embedded Python AI Engine               │
│  • CockroachDB Serverless (ACID + pgvector 384d)     │
│  • Amazon S3 Knowledge Base (boto3)                  │
│  • CockroachDB Cloud Managed MCP Server              │
│  • Dynamic Multi-Model Specialist Routing            │
│  • Bundled Portable Redis (zero install)             │
└──────────────────────────────────────────────────────┘
```

### What the Compiled Binary Does NOT Bundle

The compiled `.exe` / installer contains **only** the native Rust window and pre-built React UI. Everything else stays external and configurable — no recompile needed to change models or rotate keys.

| Item | Where It Lives | Loaded |
|---|---|---|
| `.env` secrets & API keys | `AegisDB/.env` on your disk | At runtime by Python |
| Python packages | `AegisDB/.venv/` on your disk | At runtime by Python |
| CockroachDB data | CockroachDB Cloud Serverless | Over network |
| S3 runbooks | Amazon S3 (`cockroachsre-knowledge-base`) | Over network |
| AI model inference | Provider APIs (Gemini, OpenAI, etc.) | Over network |

---

*For full project documentation, architecture diagrams, and hackathon details, see [README.md](README.md).*


---

## Quickstart (3 Steps)

### Step 1: Clone Repository & Setup Virtual Environment

```bash
# 1. Clone repository
git clone https://github.com/Arthur-101/CockroachDB.git AegisDB
cd AegisDB

# 2. Create Python virtual environment
python -m venv .venv

# 3. Activate virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# 4. Install Python dependencies
pip install -r requirements.txt
```

---

### Step 2: Configure Environment Variables

Create your `.env` file by copying `.env.example`:

```bash
cp .env.example .env
```

Open `.env` in your editor and fill in your credentials:

```env
# ── 1. CockroachDB Cloud Serverless (Required) ──
# Create a free cluster at: https://cockroachlabs.cloud/clusters
COCKROACH_DATABASE_URL=postgresql://username:password@your-cluster.cockroachlabs.cloud:26257/defaultdb?sslmode=verify-full

# ── 2. Amazon S3 Knowledge Base (Required for Runbooks & S3 Sync) ──
S3_BUCKET_NAME=cockroachsre-knowledge-base
AWS_ACCESS_KEY_ID=YOUR_AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY=YOUR_AWS_SECRET_ACCESS_KEY
AWS_REGION=ap-south-1

# ── 3. AI Model Providers (At least one required) ──
# Recommended: Google AI Studio (Free tier: 1500 req/day)
GEMINI_API_KEY=YOUR_GEMINI_API_KEY

# Optional direct provider keys:
OPENAI_API_KEY=YOUR_OPENAI_API_KEY
ANTHROPIC_API_KEY=YOUR_ANTHROPIC_API_KEY
GROQ_API_KEY=YOUR_GROQ_API_KEY
MISTRAL_API_KEY=YOUR_MISTRAL_API_KEY
```

> **Note on Schema Initialization**: CockroachDB tables and `pgvector` indexes are **automatically created on first launch**. No manual database migrations or SQL scripts required!

---

### Step 3: Run the Application

#### Option A: Launch Desktop Studio (Tauri + React UI)

```bash
cd ui
npm install
npm run tauri dev
```

#### Option B: Run Headless CLI Mode

```bash
python main.py chat
```

---

## Verifying the Installation

You can run our automated verification test suite to ensure all services are connected properly:

```bash
# 1. Test CockroachDB Relational Layer & Session Store
python scripts/test_cockroach_store.py

# 2. Test CockroachDB pgvector Semantic Search & Embeddings
python scripts/test_vector_store.py

# 3. Test S3 Knowledge Base Seed & pgvector Sync
python scripts/seed_s3_runbooks.py

# 4. Test SRE Autonomous Incident Lifecycle & Fix History
python scripts/test_sre_tools.py
```

---

## Troubleshooting

### 1. `psycopg2` or Database Connection Issues
- Ensure your `COCKROACH_DATABASE_URL` is enclosed properly and includes `?sslmode=verify-full`.
- Verify your IP is allowed in your CockroachDB Cloud cluster network authorization list (or set to `0.0.0.0/0` for development).

### 2. Amazon S3 Permission Errors
- Ensure your IAM user has `AmazonS3FullAccess` or `s3:GetObject`, `s3:PutObject`, `s3:ListBucket` permissions for your bucket.
- Verify `AWS_REGION` matches your bucket's region.

### 3. Model Quota or Rate Limit Errors
- AegisDB includes **Zero Hardcoded Model Fallbacks** and supports free providers (such as Google Gemini 2.0 Flash / Groq). Configure or hot-swap your model assignments at any time via the Desktop Settings modal.