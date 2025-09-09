# AutoAgents Tutorial and Architecture Guide

This guide explains how AutoAgents works end-to-end, the core architecture, and how to run and extend it. It is written for developers who want to understand the components, data flow, and the primary extension points (roles, actions, tools, and UI/service).

## What You’ll Build

- Run AutoAgents in command-line or service mode
- Understand how a Manager plans roles and execution steps
- See how a Group coordinates dynamic expert actions to complete tasks
- Extend the system with custom roles/actions/tools

## Prerequisites

- Python 3.9+ and a shell
- An LLM API key via `OPENAI_API_KEY` (or legacy `LLM_API_KEY`)
- One search key (any of): `SERPAPI_API_KEY`, `SERPER_API_KEY`, or `GOOGLE_API_KEY` + `GOOGLE_CSE_ID` for search tool features

## Quickstart

1) Install

```bash
python setup.py install
```

2) Configure environment (env vars are the single source of truth)

```bash
export OPENAI_API_KEY="sk-..."
# optional, see Config section for more
export SERPAPI_API_KEY="..."   # or SERPER_API_KEY / GOOGLE_API_KEY + GOOGLE_CSE_ID
export OPENAI_API_BASE="..."    # if using Azure/OpenAI compatible endpoints
```

3) Run

- Command-line mode:
```bash
python main.py --mode commandline --idea "Build a CLI snake game"
```

- WebSocket service (for the included web UI):
```bash
python main.py --mode service --host 127.0.0.1 --port 9000
```
Open `frontend/app/demo.html` in a browser to connect to the backend at `/api`.

Tip: You can also pass `--llm_api_key` and `--serpapi_key` flags. If omitted, the app reads `cfg.py` values from env.

## Architecture Overview

At a high level, AutoAgents creates a mini multi-agent organization to solve a task:

1) A Manager plans expert roles and a multi-step execution plan
2) The Environment parses that plan and spins up a Group role
3) The Group orchestrates step-by-step execution using dynamically created expert actions
4) Actions call the LLM and optional tools (e.g., web search) and can write files to `workspace/`
5) Memory records messages to drive subsequent decisions and observers can critique and refine the plan

Key components and responsibilities:

- LLM Provider: Unified via LiteLLM with rate limiting and cost tracking
- Roles: Manager, Group, Observers, and dynamically created expert roles
- Actions: Units of work run by roles; include planning, checking, and tool-using actions
- Environment: Message bus + memory + role lifecycle and execution loop
- Tools: Search engine wrappers (SerpAPI, Serper, Google CSE)
- Service/UI: WebSocket server and a simple browser UI

### Core Modules (by file)

- Entry Points
  - `main.py`: CLI entry and service launcher
  - `startup.py`: Creates `Explorer`, hires `Manager`, seeds the task, and runs the project

- Orchestration
  - `autoagents/explorer.py`: Wraps an `Environment`, manages investment/budget and main loop
  - `autoagents/environment.py`: Holds roles, memory, history; publishes/observes messages and drives role execution

- Roles
  - `autoagents/roles/role.py`: Base `Role` with thinking/acting/publishing loops and LLM usage
  - `autoagents/roles/manager.py`: The planner; calls actions to create/check roles and plans
  - `autoagents/roles/group.py`: Executes plan steps by dynamically instantiating expert actions
  - `autoagents/roles/observer.py`: Observers (agents and plan) that critique and iterate
  - `autoagents/roles/custom_role.py`: Convenience for custom one-off roles
  - `autoagents/roles/role_bank/*`: Optional predefined roles and mappings

- Actions
  - `autoagents/actions/action/action.py`: Base `Action` with structured-output parsing and repair
  - Planning lifecycle: `create_roles.py`, `check_roles.py`, `check_plans.py`, `steps.py`
  - Execution: `custom_action.py` orchestrates tool use and file writes per step
  - Action bank: domain-specific actions (`action_bank/*`), including `search_and_summarize.py`

- System & Tools
  - `autoagents/system/provider/llm_api.py`: LiteLLM-based provider with RPM limiter and cost tracking
  - `autoagents/system/memory/*`: Message memory store (with optional long-term memory)
  - `autoagents/system/tools/*`: Search engine adapters and enums
  - `autoagents/system/const.py`: Paths (project root, workspace, tmp, etc.)
  - `cfg.py`: Centralized runtime configuration from environment variables

- Service/UI
  - `ws_service.py`: WebSocket server bridging the UI and `startup`
  - `frontend/app/*`: A simple browser UI connecting to `/api`

## Execution Flow

The default command-line flow:

1) `main.py` parses args and chooses mode. Command-line mode calls `startup.startup`.
2) `startup.startup` constructs an `Explorer`, hires a `Manager`, sets the budget, and seeds the task as a `Message(role="Question/Task", ...)` in the `Environment`.
3) `Explorer.run()` loops, calling `Environment.run()` to let roles observe messages and act.
4) `Manager` runs planning actions in cycles:
   - CreateRoles → produces “Selected Roles List”, “Created Roles List”, and an “Execution Plan”
   - CheckRoles → critiques role choices and suggests refinements
   - CheckPlans → critiques the execution plan and suggests refinements
   The manager iterates until there are no further suggestions or a max iteration is reached.
5) `Environment.publish_message()` parses the manager’s output to:
   - Extract an ordered list of steps (the plan)
   - Extract role specs (name, prompt, tools, suggestions)
   - Create a `Group` role that dynamically constructs per-role `CustomAction` subclasses
6) `Group` orchestrates the plan:
   - Tracks remaining steps and picks the next step
   - For the step’s responsible role(s), runs the corresponding dynamic action
   - Each action can use tools such as search (`SearchAndSummarize`) and can write files to `workspace/`
   - Emits messages with structured “Step/Response” content
7) Memory and history accumulate across all roles; observers can critique (`ObserverAgents`, `ObserverPlans`) to refine plan/roles.

## Configuration

All configuration is read from environment variables by `cfg.py`. Important settings:

- LLM and Provider
  - `OPENAI_API_KEY` (alias: `LLM_API_KEY`)
  - `OPENAI_API_MODEL` (default `gpt-4o`), Azure style: `OPENAI_API_BASE`, `OPENAI_API_TYPE`, `OPENAI_API_VERSION`, `DEPLOYMENT_ID`
  - `RPM` requests-per-minute limiter (min 1)
  - `MAX_TOKENS`, `TEMPERATURE`, `TOP_P`, `PRESENCE_PENALTY`, `FREQUENCY_PENALTY`, `N`
  - `LLM_TIMEOUT` seconds

- Budgeting
  - `MAX_BUDGET` dollars; cost tracked via LiteLLM pricing or fallback table

- Proxies
  - `GLOBAL_PROXY` or `OPENAI_PROXY` (auto-propagated to `HTTP_PROXY`/`HTTPS_PROXY` when set)

- Additional Models
  - `CLAUDE_API_KEY` (aliases: `ANTHROPIC_API_KEY`, `Anthropic_API_KEY`), `CLAUDE_MODEL`

- Search
  - `SEARCH_ENGINE` one of: `serpapi`, `serper`, `google`, `ddg`, `custom`
  - Keys as applicable: `SERPAPI_API_KEY`, `SERPER_API_KEY`, `GOOGLE_API_KEY`, `GOOGLE_CSE_ID`

- Memory and Parsing
  - `LONG_TERM_MEMORY` true/false
  - `LLM_PARSER_REPAIR`, `LLM_PARSER_REPAIR_ATTEMPTS` enable schema repair for action outputs

## Tools and File Output

- Search: `autoagents/system/tools/search_engine.py` routes queries to SerpAPI, Serper, or Google CSE
- Custom engines: pass a `run_func` to `SearchEngine` or set `SEARCH_ENGINE=custom`
- File writes: actions can write files to `workspace/` via `CustomAction` using the `Write File` action format

Workspace location is resolved by `autoagents/system/const.py` and is safe to inspect while the system runs.

## Service Mode and Web UI

- Start server: `python main.py --mode service --host 127.0.0.1 --port 9000`
- Open `frontend/app/demo.html` in a browser; it connects to `ws://<host>:<port>/api` or `wss://` for HTTPS
- Provide API keys in the left panel; submit a task idea; watch agents and steps stream in

`ws_service.py` manages incoming tasks and streams role messages to the UI. Each run is isolated in a process and can be interrupted.

## Extending AutoAgents

1) Add a new predefined role (Role Bank)

- Create a class extending `Role` and implement its actions
- Register it in `autoagents/roles/role_bank/__init__.py` (in `ROLES_MAPPING`) and optionally in `ROLES_LIST`

2) Add a new action

- Extend `autoagents/actions/action/action.py` and implement `run`
- If the action needs structured outputs, define an output mapping and use `_aask_v1` for parsing/repair
- Add domain-specific actions in `autoagents/actions/action_bank/`

3) Add a tool

- Add a new wrapper in `autoagents/system/tools/`
- Extend the `SearchEngineType` enum if relevant, and route inside `SearchEngine.run`

4) Create a custom one-off role at runtime

- `Group` already builds dynamic `CustomAction` classes from the Manager’s role specs (name, prompt, tools, suggestions), so many scenarios don’t require code changes
- For tailored behavior, check `autoagents/roles/custom_role.py`

## Error Handling, Costs, and Limits

- Rate limiting: `RPM` controls request pacing at the provider level
- Streaming: provider streams tokens to stdout in CLI mode
- Costs: tracked per-request; enforced against `MAX_BUDGET`
- Output robustness: Actions use a schema parser and, if enabled, an LLM repair step to coerce outputs into the expected shape

## Troubleshooting

- “Invalid key” or missing results for search: ensure one of the search keys is set
- Stuck or slow progress: increase `RPM`, check proxy settings, or reduce `TEMPERATURE`
- No files appear: verify the action selected `Write File` and inspect the `workspace/` folder
- Azure setups: ensure `OPENAI_API_BASE`, `OPENAI_API_TYPE=azure`, `OPENAI_API_VERSION`, and `DEPLOYMENT_ID` are set

## Next Steps

- Wire in more tools (browsers, code execution, retrieval)
- Add new observers for domain-specific validation
- Build richer UIs or APIs on top of the WebSocket service

If you have ideas or questions, please open an issue or PR. Enjoy building with AutoAgents!
