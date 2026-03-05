# AVCD Agent (cado)

An AI coding agent with file system access, web search, code execution, and external knowledge capabilities — built on [Pydantic AI](https://ai.pydantic.dev/) and supporting multiple model providers.

---

## Features

### File System
- Read, create, and update files
- Navigate directories (absolute and relative paths)
- Self-healing path resolution with detailed error guidance

### Code Execution
- Run any shell command (`run_command` tool)
- Executes tests, installers, git commands, and scripts
- Captures stdout + stderr; 60-second timeout
- Requires approval in human-approval mode

### Web Search
- Multiple search providers (configurable via `SEARCH_PROVIDER` env var):
  - **Exa** — AI-optimized search with full content extraction (default)
  - **Firecrawl** — combined search + page scraping
  - **Tavily** — optimized for AI agents and RAG
  - **Brave** — independent search index
  - **Google Custom Search** — official Google API (100 free queries/day)
- Smart URL reader (`read_data_from_url`) supports HTML, JSON, CSV, XML, YAML, PDF, Excel

### External Knowledge
- **`lookup_package_info`** — queries PyPI, npm, or crates.io for latest version, changelog, and homepage
- **`search_github`** — searches GitHub repos, issues/PRs, and code via the official API
- **`lookup_security_advisory`** — queries OSV.dev for CVEs across PyPI, npm, Go, Maven, NuGet, and more

### Model Selection
Supports multiple AI backends via `MODEL_PROVIDER` env var:
- `openai_compatible` (default) — any local or self-hosted OpenAI-compatible model
- `openai` — OpenAI cloud API
- `anthropic` — Anthropic Claude API

### Human-in-the-Loop Approval
Toggle between two modes at runtime:
- **YOLO mode** (default) — all tool calls execute automatically
- **Approval mode** — destructive operations (`create_or_update_file`, `create_directory`, `change_directory`, `run_command`) prompt for `y/n` confirmation before executing

---

## Requirements

- Python >= 3.12
- [`uv`](https://docs.astral.sh/uv/) package manager

---

## Setup

```bash
# Install dependencies
uv sync

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your API keys and settings
```

---

## Configuration

All configuration is via environment variables in `.env`.

### Model

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_PROVIDER` | `openai_compatible` | `openai_compatible`, `openai`, or `anthropic` |
| `MODEL_NAME` | `Qwen3-Coder-30b` | Default model name (overridden by `--model` CLI flag or `/models` command) |
| `OPENAI_BASE_URL` | `http://192.168.86.34:8083/v1` | Base URL for local/self-hosted models |
| `OPENAI_API_KEY` | `qwen3` | API key (set to any value for local models) |
| `ANTHROPIC_API_KEY` | — | Required when `MODEL_PROVIDER=anthropic` |

**Provider examples:**
```bash
# Local/self-hosted (default)
MODEL_PROVIDER=openai_compatible
MODEL_NAME=Qwen3-Coder-30b
OPENAI_BASE_URL=http://localhost:8083/v1

# Anthropic Claude
MODEL_PROVIDER=anthropic
MODEL_NAME=claude-sonnet-4-6
ANTHROPIC_API_KEY=sk-ant-...

# OpenAI cloud
MODEL_PROVIDER=openai
MODEL_NAME=gpt-4o
OPENAI_API_KEY=sk-...
```

### Web Search

| Variable | Default | Description |
|----------|---------|-------------|
| `SEARCH_PROVIDER` | `exa` | Active provider: `exa`, `firecrawl`, `tavily`, `brave`, `google_custom` |
| `DEFAULT_SEARCH_NUM_RESULTS` | `5` | Number of results to retrieve |
| `EXA_API_KEY` | — | [exa.ai](https://exa.ai) |
| `FIRECRAWL_API_KEY` | — | [firecrawl.dev](https://www.firecrawl.dev) |
| `TAVILY_API_KEY` | — | [tavily.com](https://tavily.com) |
| `BRAVE_API_KEY` | — | [brave.com/search/api](https://brave.com/search/api) |
| `GOOGLE_API_KEY` | — | [Google Programmable Search](https://programmablesearchengine.google.com) |
| `GOOGLE_CSE_ID` | — | Custom Search Engine ID |

### External Knowledge

| Variable | Default | Description |
|----------|---------|-------------|
| `GITHUB_TOKEN` | — | Optional — raises GitHub API rate limit from 60/hr to 5000/hr |

### General

| Variable | Default | Description |
|----------|---------|-------------|
| `TOOL_CALL_ERROR_MAX_RETRIES` | `5` | Max retries when a tool call fails |
| `DEBUG` | `true` | Enable debug logging |
| `PORT` | `3000` | Application port |

---

## Running

```bash
# Using uv directly (default model from .env)
uv run src/cado/main.py

# Override model at launch
uv run src/cado/main.py --model Qwen3-Coder-7b

# Or after pip install (see Deploy section below)
cado
cado --model deepseek-coder-v2
```

At the prompt, type your request. Type `exit`, `quit`, `q`, or `bye` to stop.

### Runtime commands

| Command | Description |
|---------|-------------|
| `/models` | List available OpenAI-compatible models and switch the active model |
| `exit` / `quit` / `q` / `bye` | Exit the agent |

**Example — switching models mid-session:**
```
> /models
Available OpenAI-compatible models:
  1. Qwen3-Coder-30b  —  Qwen 3 Coder 30B  — large coding model (default)  <-- current
  2. Qwen3-Coder-7b   —  Qwen 3 Coder 7B   — fast, lighter coding model
  3. deepseek-coder-v2 — DeepSeek Coder V2 — strong coding performance
  ...
Enter a number to switch, or press Enter to cancel:
2
Switched to: Qwen3-Coder-7b
```

---

## Deploy as a CLI command

### Install locally with pip

```bash
# From the project root (where pyproject.toml lives)
python3 -m venv venv

# Activate (macOS/Linux)
source venv/bin/activate

# Activate (Windows)
.\venv\Scripts\activate

# Install in editable mode
python3 -m pip install -e .

# Verify install
pip3 list | grep cado
```

### Create a launcher script

**Using uv:**
```bash
#!/bin/bash
uv run $HOME/<YOUR_CODE_DIR>/avcd-agent/src/cado/main.py
```

**Using pip/venv:**
```bash
#!/bin/bash
source $HOME/<YOUR_CODE_DIR>/avcd-agent/venv/bin/activate
python3 $HOME/<YOUR_CODE_DIR>/avcd-agent/src/cado/main.py
```

### Install the script

```bash
mkdir -p ~/util_scripts
touch ~/util_scripts/cado.sh
# Paste your chosen launcher content above into cado.sh
chmod +x ~/util_scripts/cado.sh
```

### Add alias to shell config (`~/.bashrc` or `~/.zshrc`)

```bash
alias cado=$HOME/util_scripts/cado.sh
```

Then reload: `source ~/.zshrc` (or open a new terminal), and run:

```bash
cado
```

---

## Project Structure

```
avcd-agent/
├── src/cado/
│   ├── agent.py        # All tool definitions, model config, agent initialization
│   ├── main.py         # CLI entry point and REPL loop
│   └── ui.py           # Terminal UI (Rich-based panels and spinners)
├── .env.example        # Environment variable reference
├── pyproject.toml      # Dependencies and package metadata
├── AGENTS.md           # Development guidelines for AI agents working in this repo
└── TODO_EXT_KNOWLEDGE.md  # External knowledge layer implementation notes
```

---

## Self-Healing Behaviour

The agent retries failed tool calls automatically (up to `TOOL_CALL_ERROR_MAX_RETRIES` times):

- File not found → lists directory and navigates step by step
- Permission denied → suggests alternative path
- API error → inspects error code, modifies parameters, retries with corrected request

---

## Coding Style

- PEP8 for Python
- Docstrings on all functions, classes, and modules
- Modular code — one responsibility per function
- Concise explanatory comments where logic is non-obvious
