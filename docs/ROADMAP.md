
## Roadmap

This roadmap focuses on stabilizing the core multi‑agent execution loop, expanding the toolchain, improving observability and UX, and enabling reliable deployment and evaluation at scale. It is aligned with the current architecture and codebase (CLI and WebSocket service, LiteLLM provider, Search tools, dynamic role/action orchestration, and optional document store).

### Long‑Term Objective
- Build a robust, extensible multi‑agent framework that can reliably plan, execute, and audit complex tasks end‑to‑end with controllable cost, tools, and safety; support multiple model/providers, pluggable tools, persistent memory, and production‑grade observability.

### Short‑Term Objective (next 1–2 releases)
- Stabilize planning → execution loop and schema parsing/repair.
- Improve search/tooling reliability and add browser automation scaffolding.
- Ship a clearer Web UI with streaming logs, run history, and interrupt/resume.
- Add tests for critical flows, cost accounting, and configuration.

### Milestones

1) Core Stability and DX
- Robust parsing: Harden structured outputs and regex parsing for roles/plan steps; add fallbacks and validation before instantiating actions.
- Cost/budget: Ensure LiteLLM cost tracking and budget enforcement across all paths; surface totals in logs and service messages.
- Config clarity: Make `cfg.py` the single source of truth; document env precedence and defaults; add validation and helpful error messages for missing keys.
- Logging: Standardize logger usage and levels; add concise per‑step summaries; write consistent artifacts under `workspace/` with timestamps.

2) Tools and Integrations
- Search: Unify SerpAPI/Serper/Google CSE behavior; improve error handling and backoff; add rate‑limit awareness.
- Browser automation: Implement `WebBrowserEngineType` backends (Playwright/Selenium) and a minimal `BrowseAndExtract` action with safe URL allow‑list.
- File and FS tools: Provide safe file I/O helpers for actions (path sanitation, size limits, MIME hints) and a consolidated “Write/Read File” action schema.
- RAG/doc store: Wrap `FaissStore` in an optional `RetrieveAndSummarize` action; document how to index domain docs and query during execution.

3) Service and UI
- Web UI: Improve `frontend/app/` to show run timeline, per‑role messages, artifacts, and cost; add interrupt/resume and basic run history.
- WebSocket service: Harden process lifecycle (timeouts, graceful cancel, queue drain); add simple auth gate and per‑run temp directories.
- API contract: Define a stable schema for streamed messages (role, step, response, file) and version it.

4) Reliability and Testing
- Unit tests: Core planner (Create/CheckRoles, CheckPlans), action output parser, environment step orchestration, search adapters.
- Integration tests: CLI happy‑path run using mocked LLM/tooling; budget exhaustion path; parser repair path.
- CI: Lint + type checks, fast tests, and optional nightly integration tests with mocked providers.

5) Observability and Ops
- Metrics: Track requests, tokens, errors, retries, runtime per step; expose via logs and optional Prometheus exporter.
- Tracing: Add run/step/role IDs; propagate through logs and streamed events for post‑mortems.
- Artifacts: Persist `process.md` and per‑role `result.md` consistently; add a compact run summary artifact.

6) Safety and Governance
- Key handling: Avoid logging secrets; support proxy configuration; document key sourcing and defaults.
- Sandboxing: Guard file writes to `workspace/`; size limits for outputs; optional content filtering for tool outputs.
- Policy hooks: Provide observer hooks for policy checks (e.g., allowed domains, PII, prompt injection heuristics).

### Stretch Goals (mid/long term)
- Multi‑provider models: First‑class Anthropic/OpenAI/Azure routing with per‑model defaults and capability tags; dynamic model selection per action.
- Planner improvements: Use the `NextAction` observer to choose steps adaptively; enable partial re‑planning when a step fails.
- Role/Action Bank: Curate reusable, typed actions and predefined roles with metadata; simple registry and discovery.
- Multi‑task orchestration: Queue and schedule multiple runs; lightweight dashboard with run status and costs.
- Evaluations: Add benchmark tasks and automatic comparisons across providers/tools; minimal scoring harness.

### Planned Additions
- Expand Tools: Add more first‑party tools (code execution, static analysis, package management, filesystem I/O, browser automation extensions), organized via a registry with permissions and safe defaults.
- Self‑Interaction Testbed: Build a closed‑loop, sandboxed environment where agents can interact with tools and with themselves to automatically test tasks and generated code (mock providers, deterministic fixtures, recording/replay, and headless orchestration).

### Success Metrics
- Reliability: >95% successful completion on a curated task set without manual retries.
- Cost control: Budget overruns reduced to <1% of runs; accurate cost within ±5% of provider billing.
- UX: Median time‑to‑first‑use <5 minutes; clear, navigable run history and artifacts.
- Extensibility: Add a new tool or action with <100 LOC and documented steps.

### Near‑Term Task Breakdown
- Parsing/validation: Guard role/plan extraction and fail gracefully with actionable messages.
- Tooling: Add browser action prototype with Playwright; unify search adapters and error paths.
- Tests/CI: Unit tests for actions/parsers; mock providers; GitHub Actions workflow.
- UI/Service: Stream step‑level events; add interrupt/resume and basic run history; surface cost/budget.
- Docs: Expand `docs/tutorial.md` with tool setup, env matrix, and examples; add “Extending Tools/Actions” and “RAG quickstart”.

### Dependencies and Assumptions
- Requires API keys for LLM and at least one search provider; browser tooling is optional and off by default.
- Network access and proxies may be needed for certain tools; document fallbacks and offline behavior where possible.

### Risks
- Provider variance: Output formats drift; mitigate via stricter schemas and repair.
- Tool reliability: Search/browser rate limits; add backoff and caching where permissible.
- Cost creep: Enforce budgets and surface costs early in runs; default conservative generation params.

### Versioning Strategy
- Minor releases: Bug fixes, UI polish, small tools.
- Feature releases: New actions/tools, browser integration, RAG; may update streamed message schema (versioned).
- Stabilization releases: Focus on tests, performance, and observability improvements.
