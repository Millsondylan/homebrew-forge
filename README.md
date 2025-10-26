# 🔥 Forge - Homebrew Tap

Official Homebrew tap for [AgentForge](https://github.com/Millsondylan/forge), an agentic coding CLI designed to spawn and manage 500+ AI agents capable of executing complete autonomous development workflows.

## 📦 Installation

Install Forge with a single command:

```bash
brew install millsondylan/forge/forge
```

That's it! Forge and all its dependencies are now installed.

## 🆕 v0.2.0 Highlights

- `/login` and `auth anthropic` now launch the Anthropic browser flow automatically.
- `/model` and `/agentmodel` provide quick pickers for primary and workforce models.
- Persistent queue, scheduler, and agent runners live in `~/.agentforge`.
- `forge status` shows the current configuration snapshot.
- `forge memory search` surfaces recent task memories with cosine-ranked results.
- `forge monitor --follow` streams JSON logs alongside live queue stats.
- `forge dashboard` serves a lightweight web UI for queue metrics and model switching.
- `scripts/loadtest.sh --agents 500 --report reports/loadtest.json` runs a scalable load test and writes a metrics report.

Reinstall to pick up the latest build:

```bash
brew reinstall --build-from-source millsondylan/forge/forge
forge init
forge /model
forge /agentmodel
forge queue add "Smoke test from v0.2.0"
forge queue run --concurrency 2
```

## 🚀 Quick Start

### 1. Initialize Forge

```bash
forge init
```

This sets up your configuration and creates the local task database.

### 2. Authenticate with Anthropic

Forge uses Anthropic's Claude models. To authenticate, run:

```bash
forge auth anthropic
```

Or use the shorthand:

```bash
forge /login
```

This will **open your web browser** and redirect you to Anthropic's authentication page where you can log in with your Anthropic account. Once authenticated, your credentials are securely cached for the SDK to use.

> **How it works**: The `forge auth anthropic` command uses the official Anthropic CLI's OAuth-like browser flow. It opens your default browser, takes you to Anthropic's login page, and upon successful authentication, stores your credentials in a secure location for subsequent API calls.

## 📑 Development Manifest

Looking for the full build philosophy, execution pipeline, and verification rules? Read the dedicated [AgentForge Development Manifest](AGENTFORGE_DEVELOPMENT_MANIFEST.md). It codifies discovery-first workflows, the 20+ TODO requirement, browser-based Anthropic authentication via `forge /login`, and double verification standards for every agent execution loop.

### 3. Pick Your Primary Model

Use the slash command for an interactive picker:

```bash
forge /model
```

Prefer the long form?

```bash
forge model select
```

Either way, your choice persists in `~/.agentforge/config.yaml`.

### 4. Set the Agent Workforce Model

Define which model concurrent worker agents will run:

```bash
forge /agentmodel
```

You can also update it directly:

```bash
forge agent model set claude-3-5-haiku-20241022
```

### 5. Add Tasks to the Queue

```bash
forge queue add "Refactor authentication module"
forge queue add "Add unit tests for user service"
forge queue add "Optimize database queries"
```

### 6. Run Agents

Launch agents to process your task queue:

```bash
forge queue run --concurrency 5
```

Or spawn agents directly:

```bash
forge agent spawn 10
```

### 6. Search Agent Memory

```bash
forge memory search "oauth"
```

### 7. Preview System Prompts

```bash
forge prompt preview "Implement autoscaling dispatcher" --context "Refer to runtime.autoscale settings"
```

### 8. Launch the Dashboard

```bash
forge dashboard --host 127.0.0.1 --port 8765
```

### 9. Run the Load Test

```bash
scripts/loadtest.sh --agents 500 --tasks 1000 --report reports/loadtest.json --reset
```

The report captures queue throughput, completion counts, and execution duration in JSON format.

---

## 📋 Command Reference

### Core Commands

| Command | Description |
|---------|-------------|
| `forge init` | Initialize configuration and database |
| `forge /login` | Open browser to authenticate with Anthropic |
| `forge auth anthropic` | Same as `/login` - browser-based Anthropic authentication |
| `forge /model` | Interactive picker for the primary model |
| `forge /agentmodel` | Interactive picker for the agent workforce model |
| `forge auth openai <key>` | Store OpenAI API key in system keyring |
| `forge auth gemini <key>` | Store Gemini API key in system keyring |

### Model Management

| Command | Description |
|---------|-------------|
| `forge model list` | List all available models |
| `forge model select` | Interactive model picker |
| `forge model set <model>` | Set default model for all agents |

### Agent Operations

| Command | Description |
|---------|-------------|
| `forge agent spawn <n>` | Launch `n` concurrent agents |
| `forge agent spawn <n> --model <model>` | Override workforce model for the run |
| `forge agent model show` | Display current workforce model |
| `forge agent model set <model>` | Update workforce model without prompt |

### Queue Management

| Command | Description |
|---------|-------------|
| `forge queue add <task>` | Add a task to the queue |
| `forge queue list` | View queued tasks |
| `forge queue list --limit 50` | View up to 50 tasks |
| `forge queue run` | Run queue with default settings |
| `forge queue run --concurrency 10` | Run with custom concurrency |
| `forge memory search <query>` | Retrieve stored task memories |
| `forge prompt preview <task>` | Render the current system prompt |
| `forge dashboard` | Launch the local monitoring dashboard |
| `scripts/loadtest.sh` | Execute the load test harness |

### Scheduling

| Command | Description |
|---------|-------------|
| `forge schedule add <task> <time>` | Schedule a task |
| `forge schedule add "Deploy" "2024-12-01T15:00:00"` | Schedule with ISO timestamp |
| `forge schedule add "Backup" "in:30m"` | Schedule relative time (s/m/h) |
| `forge schedule run` | Start the scheduler daemon |

### Monitoring

| Command | Description |
|---------|-------------|
| `forge monitor` | Print queue statistics |
| `forge status` | Dump the active configuration snapshot |

---

## 💡 Example Workflows

### Workflow 1: Single Task, Multiple Agents

```bash
# Initialize
forge init
forge /login

# Configure
forge model set claude-3-5-sonnet-20241022

# Add task and run
forge queue add "Build REST API for user management"
forge queue run --concurrency 5
```

### Workflow 2: Batch Processing

```bash
# Add multiple tasks
forge queue add "Refactor legacy authentication"
forge queue add "Add rate limiting middleware"
forge queue add "Write integration tests"
forge queue add "Update API documentation"

# Process with 10 agents
forge agent spawn 10
```

### Workflow 3: Scheduled Execution

```bash
# Schedule future tasks
forge schedule add "Daily backup routine" "in:24h"
forge schedule add "Weekly report generation" "2024-12-01T09:00:00"

# Start scheduler
forge schedule run
```

### Workflow 4: Continuous Autopilot

```bash
# Run continuously with a 20-agent workforce
while true; do
  forge queue run --concurrency 20
  sleep 5
done
```

---

## 🔐 Authentication Details

### Anthropic (Browser OAuth Flow)

When you run `forge /login` or `forge auth anthropic`, Forge first tries to execute `anthropic login` (from the Anthropic CLI). That command opens your browser and stores the resulting credentials automatically. If the CLI isn't installed or fails, Forge falls back to simply opening the login page directly so you can complete the flow yourself; it still records the login timestamp once the browser opens.

**Requirements**:
- `anthropic` CLI installed (bundled with the Anthropic Python SDK) for the fully automated flow
- Active Anthropic account with browser access

### OpenAI & Gemini (API Key)

For OpenAI and Gemini, you provide API keys directly:

```bash
forge auth openai sk-...
forge auth gemini AIza...
```

Keys are saved to `~/.agentforge/config.yaml` under the `keys` section so you can script or rotate them easily—treat that file as sensitive.

---

## 🧠 Core Philosophy

AgentForge follows these principles:

1. **Truth Over Comfort** — Never hide errors or fabricate outputs
2. **Full Completion** — All tasks must finish completely
3. **Discovery First** — Structured analysis before execution
4. **No Fabrication** — No mock data or fake placeholders
5. **Persistence** — Continue until verified twice
6. **Self-Reliant** — Find alternate solutions when blocked

---

## 🏗️ Architecture

- **Agents**: Async workers that pull tasks from the queue
- **Queue**: Persistent SQLite-based task queue with retry logic
- **Scheduler**: Cron-like system for delayed/recurring tasks
- **Memory**: Task state, logs, and metadata persistence
- **Providers**: Pluggable model backends (Anthropic, OpenAI, Gemini, Ollama)

---

## 📊 System Requirements

- **Python**: 3.11+
- **macOS**: 10.15+ (Catalina or later)
- **Homebrew**: Latest version

---

## 🔧 Troubleshooting

### "anthropic login failed"

Make sure you have the Anthropic SDK installed:

```bash
pip install anthropic
```

Then retry:

```bash
forge /login
```

### "No models found"

Ensure you're authenticated:

```bash
forge auth anthropic
forge model list
```

### Tasks stuck in "pending"

Check queue state and logs:

```bash
forge monitor
tail -n 20 ~/.agentforge/logs/system.log
tail -n 20 ~/.agentforge/logs/agent_001.log
```

---

## 🛠️ Development

Want to contribute or modify the formula?

```bash
# Clone this tap
git clone https://github.com/Millsondylan/homebrew-forge.git

# Edit the formula
cd homebrew-forge
nano Formula/forge.rb

# Test locally
brew install --build-from-source ./Formula/forge.rb
```

---

## 📚 Resources

- **Main Repository**: [github.com/Millsondylan/forge](https://github.com/Millsondylan/forge)
- **Issues**: [github.com/Millsondylan/forge/issues](https://github.com/Millsondylan/forge/issues)
- **Anthropic Documentation**: [docs.anthropic.com](https://docs.anthropic.com)
- **Homebrew Documentation**: [docs.brew.sh](https://docs.brew.sh)

---

## 📄 License

AgentForge is released under the MIT License. See the [main repository](https://github.com/Millsondylan/forge) for details.

---

## 🙏 Acknowledgments

Built with:
- [Anthropic Claude](https://www.anthropic.com/) - AI models
- [Click](https://click.palletsprojects.com/) - CLI framework
- [PyYAML](https://pyyaml.org/) - YAML configuration support
- [SQLite](https://www.sqlite.org/) - Embedded task queue storage

---

**Made with 🔥 by the AgentForge team**
