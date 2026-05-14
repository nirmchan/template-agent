# Template Platform: Consolidated Production Roadmap

**Goal:** Build the best open-source agent template platform in the world — a production-ready backend (template-agent) with a world-class frontend (template-ui).

**Strategy:**
- **Backend:** Deploy on aegra infrastructure + import production-proven patterns from 17 repositories + align with LangChain DeepAgents
- **Frontend:** Combine the best of deep-agents-ui, sales-assistant-frontend, and dataverse-ui into a single, production-grade template

**Timeline:** 14 weeks (May 11 – August 16, 2026)
**Total MRs:** 235 (134 backend + 101 frontend)
**Effort:** ~2-4 hours per MR

---

## Executive Summary

### The Vision

A **complete agent platform** — backend + frontend — that is:
1. **Production-ready** with horizontal scaling, auth, observability, error handling
2. **Feature-rich** with sub-agents, interrupts, memory, caching, file artifacts
3. **DeepAgents-compatible** for full LangChain ecosystem alignment
4. **Beautiful** with PatternFly 6 design system, accessibility, and polished UX

### Key Outcomes

| Metric | Target | Source |
|--------|--------|--------|
| Scalability | 30+ concurrent jobs/instance | Aegra workers |
| Test Coverage | 80%+ (both tracks) | agent-lightning, vitest |
| Token Cost | 70% reduction | Multi-layer caching |
| Throughput | 3x improvement | Score-ranked memory + caching |
| MTTR | <15 min | OpenTelemetry (both tracks) |
| Security | Enterprise-ready | JWT + RBAC + CSP + sandbox |
| Accessibility | WCAG 2.1 AA | PatternFly + custom ARIA |
| Compatibility | Full LangChain DeepAgents | Agent types, middleware, filesystem |

---

## Timeline Overview

```
Week  Backend (template-agent)              Frontend (template-ui)
────  ─────────────────────────────────────  ─────────────────────────────────────
 1    ✅ Aegra Setup & Dependencies          ✅ Foundation & Architecture
 2    ✅ Aegra Core Integration              ✅ PatternFly Integration
 3    ✅ Aegra Testing & Deployment          ✅ Core Chat (Streaming Engine)
 4    ✅ Error Handling & Type Safety        ✅ Core Chat (UI + Sidebar)
 5    ✅ Test Infrastructure                  ✅ Deep Agent Features (Sub-agents)
 6    ✅ Multi-Layer Caching                 ✅ Deep Agent Features (Interrupts)
 7    ✅ Memory & Database                   ✅ Personalization & Settings
 8    ✅ Logging & Telemetry                 ✅ Resilience & Error Handling
 9    ✅ Health & Diagnostics                ✅ UX Polish (Feedback, Editing)
10    Developer Experience (CLI)             ✅ UX Polish (Accessibility)
11    DeepAgents: Agent Types & Middleware   Production Hardening (OTEL, Security)
12    DeepAgents: Filesystem Abstraction     Testing & Quality
13    DeepAgents: Providers & Async Tasks    ─ (buffer / polish)
14    DeepAgents: Permissions & Utilities    ─ (buffer / polish)
```

### Cross-Track Dependencies

```
Backend                          Frontend
───────                          ────────
Aegra streaming API ──────────── BFF proxy SSE streaming (Phase 2)
__interrupt__ events ─────────── Interrupt handler UI (Phase 3)
SubAgent orchestration ───────── Sub-agent indicator (Phase 3)
/feedback endpoint ───────────── Feedback buttons (Phase 6)
Memory API ───────────────────── Memory management UI (Phase 4)
OTEL trace IDs ───────────────── Trace ID propagation (Phase 7)
Health endpoint (/ok) ────────── Agent health indicator (Phase 6)
```

---

## Workstream A: Backend (template-agent)

**Repository:** `template-agent`
**Stack:** Python, LangGraph, LangChain, Aegra, FastAPI
**MRs:** 134
**Duration:** 14 weeks

### PART A: AEGRA INTEGRATION (Weeks 1-3) ✅ COMPLETE

**Goal:** Deploy template-agent on aegra infrastructure for production scalability
**Completed:** May 31, 2026

#### Week 1: Setup & Dependencies (MRs 1-15) ✅
- [x] MR-01: Add aegra-cli to dependencies
- [x] MR-02: Add langgraph-sdk to dependencies
- [x] MR-03: Create deep_agent/aegra/ directory structure
- [x] MR-04: Add .env.example for aegra
- [x] MR-05: Create docker-compose.yml
- [x] MR-06: Add Makefile targets
- [x] MR-07: Update .gitignore
- [x] MR-08: Add aegra docs to README
- [x] MR-09: Define LangGraph State schema
- [x] MR-10: Create state converters
- [x] MR-11: Wrap AgentManager in node
- [x] MR-12: Add skill invocation node
- [x] MR-13: Add subagent orchestration node
- [x] MR-14: Create graph builder
- [x] MR-15: Add checkpointing config

#### Week 2: Core Integration (MRs 16-28) ✅
- [x] MR-16: Implement state serialization
- [x] MR-17: Add error handling to graph
- [x] MR-18: Create graph export function
- [x] MR-19: Create aegra.json configuration
- [x] MR-20: Configure Redis connection
- [x] MR-21: Configure Postgres checkpoints
- [x] MR-22: Set up auth configuration
- [x] MR-23: Configure OpenTelemetry tracing
- [x] MR-24: Add Langfuse integration
- [x] MR-25: Configure worker pool settings
- [x] MR-26: Add health check endpoints
- [x] MR-27: Add unit tests for converters
- [x] MR-28: Add unit tests for graph nodes

#### Week 3: Testing & Deployment (MRs 29-42) ✅
- [x] MR-29: Add BMI skill integration test
- [x] MR-30: Add email skill integration test
- [x] MR-31: Add subagent flow integration test
- [x] MR-32: Add end-to-end test with aegra
- [x] MR-33: Add load test script
- [x] MR-34: Add test fixtures
- [x] MR-35: Update Containerfile
- [x] MR-36: Update K8s manifests
- [x] MR-37: Add deployment scripts
- [x] MR-38: Add Redis to dev compose
- [x] MR-39: Add Langfuse to dev compose
- [x] MR-40: Add Jaeger/OTEL to dev compose
- [x] MR-41: Create unified dev stack with make dev
- [x] MR-42: Add performance benchmarks

**Milestone:** Aegra integration complete, production deployment ready, full dev environment

---

### PART B: FEATURE ENHANCEMENTS (Weeks 4-10)

**Goal:** Import production-proven patterns to make template-agent world-class
**Source:** 17 production repositories analyzed

#### Phase 2: Production Foundations (Weeks 4-5)

**Week 4: Error Handling & Type Safety (MRs 43-54) ✅**
- [x] MR-43: Add tenacity dependency
- [x] MR-44: Create error_handling.py module (retry decorators, circuit breaker, classify_error, with_fallback)
- [x] MR-45: Add retry decorators to LLM calls (llm.py — @llm_retry, LLMError wrapping)
- [x] MR-46: Add retry to skill invocations (aegra/nodes.py — tenacity-based with_retry replacing hand-rolled)
- [x] MR-47: Add retry to subagent calls (subagent_retry decorator, SubAgentError wrapping)
- [x] MR-48: Implement circuit breaker pattern (Redis-backed with in-memory fallback, TTL auto-expiry)
- [x] MR-49: Add graceful degradation (classify_error, with_fallback decorator)
- [x] MR-50: Add type hints to core agent modules (llm.py, factory.py, manager.py)
- [ ] MR-51: Add type hints to skills/
- [x] MR-52: Add type hints to subagents/ and infrastructure (mcp.py, subagents.py)
- [ ] MR-53: Add pyright to pre-commit
- [x] MR-54: Tighten mypy config (disallow_untyped_defs, disallow_incomplete_defs, check_untyped_defs, warn_return_any)

**Additional deliverables (beyond original plan):**
- [x] Expanded exception hierarchy: TransientError, LLMError, LLMTimeoutError, MCPError, MCPTimeoutError, SubAgentError, ConfigurationError, RateLimitError, AuthenticationError (with is_retryable property)
- [x] 11 structured error codes (E_001–E_011) with HTTP status mapping
- [x] Redis as explicit dependency (redis>=5.0.0) — promoted from lazy import
- [x] Circuit breaker Redis persistence with HSET/HGETALL + TTL auto-expiry (3x reset_timeout, min 300s)
- [x] 43 unit tests for error_handling.py (classify_error, with_fallback, CircuitBreaker in-memory + Redis-mocked)

**Week 5: Test Infrastructure (MRs 55-68) ✅**
- [x] MR-55: Add pytest-mock dependency
- [x] MR-56: Create conftest.py with fixtures
- [x] MR-57: Add test DB fixture
- [x] MR-58: Add mock LLM fixture
- [x] MR-59: Unit tests for AgentManager
- [x] MR-60: Unit tests for BMI skill
- [x] MR-61: Unit tests for email skill
- [x] MR-62: Parametrized tests for skills
- [x] MR-63: Integration tests for subagents
- [x] MR-64: Add test markers (unit/integration)
- [x] MR-65: Add pytest-cov configuration
- [x] MR-66: Add coverage gate to CI
- [x] MR-67: Add coverage report generation
- [x] MR-68: Achieve 80%+ coverage baseline

**Additional deliverables (beyond original plan):**
- [x] New test files: test_settings, test_schema, test_personalization, test_repository, test_auth, test_telemetry, test_serialization, test_middleware, test_graph, test_backend, test_mcp_helpers, test_worker, test_redis, test_init
- [x] Fixed 3 pre-existing test_config failures (PROMPT.md path migration)
- [x] 372 unit tests passing, 83% coverage (up from 19%)
- [x] CI coverage gate raised to 81%
- [x] `asyncio_mode = "auto"` for pytest-asyncio
- [x] `make test-cov` target for local coverage runs
- [x] Coverage source fixed from `src` to `deep_agent`
- [x] HTML + XML coverage report generation

**Milestone:** ✅ Production error handling + type safety + test infrastructure complete. Remaining: skills/ type hints (MR-51), pyright (MR-53)

#### Phase 3: Scalability Features (Weeks 6-7)

**Week 6: Multi-Layer Caching (MRs 69-77)** ✅ COMPLETE
- [x] MR-69: Add cachetools dependency (replaces diskcache — OpenShift-native)
- [x] MR-70: Create cache/ module (config, backend protocol, multi-layer)
- [x] MR-71: Model instance cache (TTLCache by model/temp/tokens)
- [x] MR-72: Multi-layer cache infrastructure (L1 in-memory + L2 Redis)
- [x] MR-73: Personalization cache (Redis L2, user memories/rules)
- [x] MR-74: Cache backend implementations (NullCache, InMemoryCache, RedisCache)
- [x] MR-75: Feature-flagged CacheSettings (all OFF by default)
- [x] MR-76: Cache warming (pre-create models at startup)
- [x] MR-77: Cache metrics (hit/miss/set/delete counters per cache name)

**Additional deliverables (beyond original plan):**
- [x] Replaced diskcache with cachetools+Redis (OpenShift: no ephemeral disk, shared L2 via Redis PVC)
- [x] All caches behind feature flags: CACHE_ENABLED master + per-layer flags
- [x] Integrated into hot paths: graph.py, factory.py, subagents.py
- [x] 58 new cache tests, 430 total passing, 85% coverage
- [x] Updated .env.example with all cache env vars

**Week 7: Memory & Database (MRs 78-83)** ✅ COMPLETE
- [x] MR-78: Add APScheduler v4 dependency + memory config with feature flags
- [x] MR-79: Create memory consolidation module (token-similarity dedup)
- [x] MR-80: Add exponential decay scoring (e^(-λ·age) with access boost)
- [x] MR-81: Add semantic clustering (TF-IDF cosine similarity, background only)
- [x] MR-82: Add relationship inference (keyword/entity overlap linking)
- [x] MR-83: Add scheduled consolidation jobs (APScheduler, Redis distributed lock)
- [x] ~~MR-84: Implement dual-pool DB~~ — DROPPED (unnecessary with Postgres)
- [x] ~~MR-85: Add WAL mode for SQLite~~ — DROPPED (not using SQLite)

**Additional deliverables (beyond original plan):**
- [x] Schema migration: added `score FLOAT` + `cluster_id UUID` columns to `user_memories`
- [x] New `list_top_memories()` — score-ranked top-N query (replaces unranked list)
- [x] Injector upgraded to use `MEMORY_MAX_INJECT` (default 20) via score ranking
- [x] Memory model extended: `score`, `cluster_id` fields on `Memory` Pydantic model
- [x] 7 new feature flags: `MEMORY_CONSOLIDATION_ENABLED`, `MEMORY_DECAY_ENABLED`, etc.
- [x] All clustering/consolidation runs as background jobs only — zero request-path impact
- [x] 42 new memory tests, 475 total passing, 81.57% coverage
- [x] Updated `.env.example` with all memory env vars

**Milestone:** Memory consolidation, decay scoring, semantic clustering, 81%+ coverage

#### Phase 4: Observability (Weeks 8-9)

**Week 8: Logging & Telemetry (MRs 86-92)** ✅ COMPLETE
- [x] MR-86: Add structlog dependency — already present (structlog==25.5.0)
- [x] MR-87: Replace stdlib logging with structlog — migrated 21 files from raw `import logging`
- [x] MR-88: Add structured logging fields — `request_id`, `user_id`, `thread_id`, `service` via contextvars
- [x] MR-89: Add JSONL log output — already active (JSONRenderer in pipeline)
- [x] MR-90: Add rich console renderer for dev — `LOG_FORMAT=console` env var
- [x] ~~MR-91: Add OpenTelemetry spans~~ — SKIPPED (already exists in telemetry.py)
- [x] ~~MR-92: Add custom metrics~~ — SKIPPED (already exists in telemetry.py)

**Additional deliverables:**
- [x] `bind_request_context()` / `clear_request_context()` for per-request log enrichment
- [x] `_inject_request_context` structlog processor auto-injects context into every log line
- [x] `LOG_FORMAT` env var: `json` (default, production) or `console` (dev-friendly with colors)
- [x] `SERVICE_NAME` env var in every log line (default: template-agent)
- [x] 11 new logger tests, `pylogger.py` at 100% coverage
- [x] 486 total tests passing, 81.97% coverage

**Week 9: Health & Diagnostics (MRs 93-95)** ✅ COMPLETE
- [x] MR-93: Health endpoint — `/health`, `/healthz`, `/readyz`, `/livez` with DB, Redis, config, cache checks
- [x] ~~MR-94: Create diagnostic CLI~~ — DROPPED (irrelevant for containerized agents)
- [x] MR-95: Startup orchestrator — coordinated init (config → DB → cache → scheduler → telemetry)

**Additional deliverables:**
- [x] `health.py`: async checks for DB latency, Redis ping, config validation, cache stats
- [x] `startup.py`: idempotent startup sequence, lazy first-request init via `graph.py`
- [x] Health response: `healthy` / `degraded` / `unhealthy` with HTTP 200/503
- [x] OpenShift probes now have a real backend (startup/liveness/readiness all point to `/health`)
- [x] 23 new health + startup tests, 509 total passing, 82.16% coverage

**Milestone:** <15min MTTR, full observability, structured logging

#### Phase 5: Developer Experience (Week 10)

- [ ] MR-96: Add typer dependency
- [ ] MR-97: Create CLI with subcommands
- [ ] MR-98: Add interactive setup wizard
- [ ] MR-99: Add pre-commit hooks (bandit, ruff, black)
- [ ] MR-100: Create CLAUDE.md
- [ ] MR-101: Create ARCHITECTURE.md
- [ ] MR-102: Update documentation

**Milestone:** World-class developer experience

---

### PART C: DEEPAGENTS ARCHITECTURE ALIGNMENT (Weeks 11-14)

**Goal:** Align with LangChain deepagents standard for ecosystem compatibility

#### Phase 6: Agent Type System & Middleware (Week 11)

- [ ] MR-103: Implement SubAgent base class
- [ ] MR-104: Add CompiledSubAgent with optimization
- [ ] MR-105: Add AsyncSubAgent for parallel tasks
- [ ] MR-106: Create HarnessProfile system
- [ ] MR-107: Create middleware base class
- [ ] MR-108: Add SummarizationToolMiddleware
- [ ] MR-109: Add PatchToolCallsMiddleware
- [ ] MR-110: Add SkillsMiddleware
- [ ] MR-111: Add MemoryMiddleware

**Milestone:** Agent type hierarchy complete, middleware architecture functional

#### Phase 7: Filesystem Abstraction (Week 12)

- [ ] MR-112: Define BackendProtocol interface
- [ ] MR-113: Implement LocalShellBackend
- [ ] MR-114: Implement StateBackend
- [ ] MR-115: Add CompositeBackend
- [ ] MR-116: Add file operation schemas (ls, read, write, edit, glob, grep)
- [ ] MR-117: Implement FilesystemMiddleware

**Milestone:** Complete filesystem abstraction with multiple backends

#### Phase 8: Provider & Async Systems (Week 13)

- [ ] MR-118: Create ProviderProfile system
- [ ] MR-119: Add provider registration
- [ ] MR-120: Implement resolve_model()
- [ ] MR-121: Add create_deep_agent() factory
- [ ] MR-122: Add GeneralPurposeSubagentProfile
- [ ] MR-123: Define async task schemas
- [ ] MR-124: Implement AsyncSubAgentState
- [ ] MR-125: Add AsyncSubAgentMiddleware
- [ ] MR-126: Create task lifecycle handlers

**Milestone:** Multi-provider support, async task API complete

#### Phase 9: Permissions & Utilities (Week 14)

- [ ] MR-127: Define FilesystemPermission model
- [ ] MR-128: Implement validate_path()
- [ ] MR-129: Add permission inheritance
- [ ] MR-130: Add permission middleware
- [ ] MR-131: Add content formatting utils
- [ ] MR-132: Add path normalization utils
- [ ] MR-133: Define file operation response models
- [ ] MR-134: Add file error handling

**Milestone:** LangChain deepagents architecture alignment complete

---

## Workstream B: Frontend (template-ui)

**Repository:** `template-ui`
**Stack:** React 19, TypeScript, Vite, PatternFly 6, Tailwind CSS 4, Redux Toolkit, Fastify 5
**MRs:** 101
**Duration:** 11 weeks

### Backend Integration (Aegra / LangGraph Platform API)

| Endpoint | Purpose |
|----------|---------|
| `POST /threads` | Create thread |
| `GET /threads/{id}` | Get thread |
| `DELETE /threads/{id}` | Delete thread |
| `POST /threads/{id}/runs/stream` | SSE streaming |
| `POST /assistants/search` | List assistants |
| `GET /ok` | Health check |
| `POST /feedback` | Record feedback to Langfuse |

### Reference Implementations

| Source | What we take |
|--------|-------------|
| deep-agents-ui | Sub-agent indicator, file artifacts viewer, interrupt handler, todo progress |
| sales-assistant-frontend | PatternFly patterns, memories, skills, theme selector, message editing, token tracking, thinking blocks |
| dataverse-ui | Redux state, streaming manager, rules editor, error types, BFF proxy, OTEL, connection status, stream cancellation, vitest |
| template-ui (existing) | Fastify BFF architecture, project structure, auth toggle, Containerfile, compose, OpenShift manifests |

---

### PHASE 1: FOUNDATION & ARCHITECTURE (Week 1) ✅ COMPLETE

**Completed:** 2026-05-12 — commit `7082f94` on `feat/template-agent`

#### Dependencies & Tooling (MRs 1-4) ✅
- [x] MR-01: Upgrade `@langchain/langgraph-sdk` to `^1.9.2`
- [x] MR-02: Add Redux Toolkit, store, hooks, `<Provider>`
- [x] MR-03: Add structured error types (ErrorCode enum, APIError, ErrorHandler)
- [x] MR-04: Add vitest + Testing Library + jsdom

#### State Management (MRs 5-8) ✅
- [x] MR-05: Chats Redux slice — CRUD, streaming state, tool result merging
- [x] MR-06: User settings slice — theme, memory, debug mode, localStorage persistence
- [x] MR-07: Authenticated fetch wrapper — credentials, 401/429 handling
- [x] MR-08: Migrate App, AppLayout, HomePage, ChatPage from ChatContext to Redux

#### BFF Proxy Layer (MRs 9-12) ✅
- [x] MR-09: BFF proxy router with Bearer token auth, SSE pipeline, abort detection
- [x] MR-10: Token refresh in proxy — session-based, pre-forward validation
- [x] MR-11: One-time token endpoint + feedback proxy + agent health check
- [x] MR-12: Redis utility (ioredis) with graceful fallback

**Milestone:** Foundation complete. Redux store, BFF proxy with Bearer token auth, structured error types, test tooling.

---

### PHASE 1.5: PATTERNFLY INTEGRATION (Week 2) ✅ COMPLETE

**Goal:** Adopt PatternFly 6 as the design system.
**Completed:** 2026-05-13

- [x] PF-01: Add PatternFly 6 dependencies (2h)
- [x] PF-02: Migrate AppLayout to PatternFly Page (3h)
- [x] PF-03: Migrate UI primitives to PatternFly (3h)
- [x] PF-04: Add PatternFly dialogs and alerts (2h)
- [x] PF-05: Update theme system for PatternFly (2h)

**Additional deliverables:**
- [x] `@patternfly/chatbot` dependency added (not yet imported in source)
- [x] `useThemeSync` applies both Tailwind `dark` class and `.pf-v6-theme-dark` on `<html>`
- [x] PatternFly global CSS (`patternfly.css`, `patternfly-addons.css`) loaded in `main.tsx`
- [x] Removed all `@radix-ui/*` dependencies (scroll-area, select, slot, tabs, tooltip)
- [x] Removed `class-variance-authority` — no longer needed
- [x] Deleted 8 Radix/Tailwind wrappers in `components/ui/` (button, badge, card, scroll-area, input, select, tabs, textarea)
- [x] Migrated Button to PF `Button` in ChatPage, Sidebar, ErrorBoundary, ChatErrorBoundary
- [x] Migrated Card/ScrollArea to PF `Card`/`CardBody` in ActivityTimeline
- [x] Migrated Badge to PF `Label` in ChatMessagesView
- [x] Added PF `Modal` for delete-chat confirmation in Sidebar
- [x] Added PF `Alert` + `ExpandableSection` in ErrorBoundary
- [x] Added PF `Alert` (warning variant) in ChatErrorBoundary
- [x] 48 npm packages removed from lockfile

**Milestone:** ✅ PatternFly design system fully integrated. All UI primitives migrated, Radix eliminated, PF dialogs and alerts in place.

---

### PHASE 2: CORE CHAT (Weeks 2-3) ✅ COMPLETE

**Goal:** Rebuild chat interface with proper streaming, thread persistence, and LangGraph SDK integration.
**Completed:** 2026-05-13

#### Streaming Engine (MRs 13-17) ✅
- [x] MR-13: Create global streaming manager (4h)
- [x] MR-14: Add SSE chunk processor (3h)
- [x] MR-15: Add `useStreamingAPI` hook (3h)
- [x] MR-16: Wire streaming to BFF proxy (2h)
- [x] MR-17: Add stream cancellation (2h)

#### Chat UI Components (MRs 18-24)
- [x] MR-18: Rebuild ChatMessagesView with Redux (3h)
- [x] MR-19: Add tool call/response rendering (3h)
- [x] MR-20: Add markdown rendering with code highlighting (3h)
- [x] MR-21: Rebuild InputForm with keyboard shortcuts (2h)
- [x] MR-22: Add auto-scroll hook (2h)
- [x] MR-23: Add connection status indicator (2h)
- [x] MR-24: Add toast notification system (2h)

#### Sidebar & Thread Management (MRs 25-30)
- [x] MR-25: Rebuild sidebar with Redux (3h)
- [x] MR-26: Add thread CRUD via BFF proxy (3h)
- [x] MR-27: Add conversation search/filter (2h)
- [x] MR-28: Add delete all conversations (2h)
- [x] MR-29: Rebuild welcome screen (2h)
- [x] MR-30: Add responsive sidebar (2h)

**Additional deliverables (beyond original plan):**
- [x] `StreamEventRenderer` component for structured tool call / intermediate event display
- [x] `ActivityTimeline` component for step-by-step agent activity view
- [x] `ChatErrorBoundary` — chat-level error boundary (originally Phase 5 MR-57)
- [x] `ErrorBoundary` — global error boundary (originally Phase 5 MR-58)
- [x] `RedHatLogo` component with Red Hat branding
- [x] `useRefreshableToken` hook for BFF token refresh
- [x] Auto-send prompt cards from WelcomeScreen
- [x] No-response retry UI

**Milestone:** ✅ Core chat complete. Streaming engine, chat UI, sidebar, toast notifications, delete all conversations — all delivered.

---

### PHASE 3: DEEP AGENT FEATURES (Weeks 4-5) — ✅ COMPLETE

**Goal:** Add support for deep-agent capabilities: sub-agents, interrupts, files, and task tracking.
**Depends on:** Backend sub-agent orchestration (Part A MR-13), interrupt events

#### Sub-Agent Rendering (MRs 31-34) — ✅ COMPLETE
Completed: 2026-05-13

- [x] MR-31: Define deep-agent types — `SubAgentStatus`, `SubAgentInfo`, `ToolCallWithContent`, `isSubAgentToolCall()` type guard, `extractSubAgentName()` utility (`types/deep-agent.ts`)
- [x] MR-32: Add sub-agent indicator component — PF `Card` with `Label` status badge, three visual states (delegating/complete/error), expandable args + result view (`SubAgentIndicator.tsx`)
- [x] MR-33: Add sub-agent event processing — BFF `rewriteSubAgentName()` mirrors Python `converter.py` `task`→`subagent_type` rewrite; Redux `StreamingState.activeSubAgent` tracking in `useStreamingAPI`
- [x] MR-34: Add sub-agent status in sidebar — active chat shows blue PF `Label` with sub-agent name and animated spinner during delegation

#### Interrupt / HITL Handler (MRs 35-38) — ✅ COMPLETE
Completed: 2026-05-13

- [x] MR-35: Add interrupt detection in streaming — `interrupt` SSEChunk type, `pendingInterrupt` in `StreamingState`, `onInterrupt` callback in `StreamingManager`, BFF thread state check post-stream
- [x] MR-36: Add ToolApprovalInterrupt component — `InterruptBanner` with approve/reject buttons for tool approval interrupts (PF `Alert variant="warning"`)
- [x] MR-37: Add generic interrupt dialog — Same `InterruptBanner` handles text-response interrupts (PF `Alert variant="info"` + `TextInput`)
- [x] MR-38: Add interrupt resume flow in BFF — `resume` flag in `StreamRequestBody`, BFF uses `command: { resume }` instead of `input: { messages }` when set

#### File Artifacts & Task Progress (MRs 39-42) — ✅ COMPLETE
Completed: 2026-05-13

- [x] MR-39: Add file artifacts viewer — `ArtifactViewer` with syntax detection (`detectArtifactKind`: code/json/markdown/text), copy button, ReactMarkdown rendering; wired into `AIMessageRenderer` for rich tool results
- [x] MR-40: Add todo/task progress stepper — `TaskProgressStepper` derives steps from tool calls in messages, shows PF `Label` chain with status icons (running/complete), mounted above chat when tool calls present
- [x] MR-41: Add tasks/files sidebar panel — `TasksSidebar` extracts tool call entries from messages, shows completion count, result previews, artifact kind labels; visible on lg+ screens when tool calls present
- [x] MR-42: Add debug mode toggle — `DebugToggle` (Bug icon in masthead), `DebugPanel` (message counts, streaming state JSON); `debugMode` already existed in `userSettings` Redux slice

**Milestone:** ✅ Full deep-agent support. Sub-agents, interrupts, file artifacts, task progress, debug mode — all delivered.

---

### PHASE 4: PERSONALIZATION & SETTINGS (Week 6) — ✅ COMPLETE

**Goal:** Add memories, custom rules, themes, and a settings page.
**Depends on:** Backend memory API (Part B MR-79+)
**Completed:** 2026-05-14

#### Memories Management (MRs 43-47) — ✅ COMPLETE
- [x] MR-43: Add memories API service — `personalization` Redux slice with `addMemory`, `removeMemory`, `clearMemories`; localStorage persistence (`template-ui-personalization`); BFF forwards `memories[]` in stream request `config.configurable`
- [x] MR-44: Add BFF proxy routes for memories — `proxy.router.ts` updated: `StreamRequestBody.memories` field extracted, forwarded as `config.configurable.user_memories` in LangGraph run body
- [x] MR-45: Add MemoryListView component — `MemoryList.tsx` with add/delete/clear, info callout, empty state, Brain icon
- [x] MR-46: Add memory toggle — `memoryEnabled` already in `userSettings` slice; memories sent only when non-empty
- [x] MR-47: Add memories to settings page — "Memories" tab in `SettingsPage.tsx`

#### User Rules (MRs 48-50) — ✅ COMPLETE
- [x] MR-48: Add rules API service — `personalization` Redux slice with `addRule`, `updateRule`, `toggleRule`, `removeRule`, `clearRules`; `selectActiveRules` selector; BFF forwards `rules[]` via `config.configurable.user_rules`
- [x] MR-49: Add RulesEditor component — `RulesEditor.tsx` with add/toggle/delete/clear, PF `Switch` for per-rule enable/disable, amber info callout
- [x] MR-50: Add rules to settings page — "Custom Rules" tab in `SettingsPage.tsx`

#### Settings & Themes (MRs 51-54) — ✅ COMPLETE
- [x] MR-51: Create settings page — `SettingsPage.tsx` with 4-tab layout (Profile, Memories, Custom Rules, Appearance); responsive nav + content; back-to-home button; route `/settings` in `App.tsx`
- [x] MR-52: Add theme selector — `AppearanceSettings.tsx` with visual card picker (Light/Dark) using `setTheme` dispatch; Interface Density placeholder
- [x] MR-53: Add user profile section — `ProfileSection.tsx` shows avatar initial, display name, username, email, SSO badge from `window.USER_DATA`
- [x] MR-54: Add settings link in sidebar footer — `Sidebar.tsx` updated with `Settings` icon link via `useNavigate('/settings')`

#### Backend: Personalization Module — ✅ COMPLETE
- [x] `deep_agent/src/personalization/models.py` — Pydantic `Memory` + `Rule` models with UUID, user_id, timestamps
- [x] `deep_agent/src/personalization/repository.py` — Async Postgres CRUD (`PersonalizationRepository`) using `psycopg` for `user_memories` + `user_rules` tables with lazy table creation
- [x] `deep_agent/src/personalization/injector.py` — `inject_personalization()` appends memories + rules sections to system prompt
- [x] `deep_agent/aegra/graph.py` — Modified to read user personalization from Postgres at graph creation time and inject into system prompt (graceful fallback if tables don't exist)
- [x] `config/migrations/001_personalization.sql` — DDL for `user_memories` + `user_rules` tables with indexes

**Milestone:** ✅ Full personalization. Memories CRUD, user rules with toggle, theme selector, settings page, profile section, sidebar link. Backend reads personalization from Postgres and injects into agent prompt. Frontend persists to localStorage and forwards via streaming configurable.

---

### PHASE 5: RESILIENCE & ERROR HANDLING (Week 7) — ✅ COMPLETE

**Goal:** Make the UI resilient to network failures, auth expiry, and backend errors.
**Completed:** 2026-05-14

#### Error Recovery (MRs 55-58) — ✅ COMPLETE
- [x] MR-55: Add ErrorRecovery component — `ErrorRecovery.tsx` shared component with PatternFly `EmptyState`, retry counter (`Retry (attempt x/y)`), expandable technical details, error ID display, Start Over / Retry / Refresh buttons with loading state, max-retry limit
- [x] MR-56: Add retry with exponential backoff — `useStreamingAPI.ts` updated with `MAX_RETRIES=3`, `BASE_DELAY_MS=1000`, `computeRetryDelayMs()` (exponential + jitter, cap 30s), `isRecoverableStreamError()` classifier (network errors, 5xx, 429 only), `retryCount` exposed from hook
- [x] MR-57: Add chat-level error boundary — `ChatErrorBoundary.tsx` refactored to use `ErrorRecovery` with "Refresh Chat" action, sidebar shell preserved
- [x] MR-58: Add global error boundary — `ErrorBoundary.tsx` refactored to use `ErrorRecovery` with `crypto.randomUUID()` error ID, stack trace in expandable details, "Reload Application" as primary action

#### Auth & Session Resilience (MRs 59-62) — ✅ COMPLETE
- [x] MR-59: Add session timeout detection — `SessionExpiredModal.tsx` (PatternFly Modal), `setAuthExpiredCallback` wired in `AppLayout.tsx`, `authenticated-fetch.ts` calls callback on 401 instead of hard redirect, `notifySessionExpired()` exported for non-fetch paths
- [x] MR-60: Add token refresh in BFF — `proxy.router.ts` returns HTTP 401 `{ error: 'session_expired' }` when `ensureFreshTokens` fails (previously passed stale tokens through)
- [x] MR-61: Add rate limiting UI — `useRateLimitState.ts` hook with countdown timer, `setRateLimitCallback` pattern, `InputForm.tsx` shows "Wait (Xs)" disabled button + inline Alert on 429, `StreamingManager.ts` also triggers on stream 429
- [x] MR-62: Add logout flow — `POST /auth/logout` route (`logout.router.ts`) clears cookies + destroys session; `logout.ts` service clears Redux (`resetChatsState`, `clearAllToasts`, `resetPersonalization`) + localStorage + redirects; log out button in `Sidebar.tsx`

#### Stream Resilience (MRs 63-66) — ✅ COMPLETE
- [x] MR-63: Add stale run detection — 30s idle watchdog in `useStreamingAPI.ts`, `lastTokenTimeRef` updated on every token, 1s interval checks staleness, `isStreamStale` boolean exposed (no auto-cancel), clears when tokens resume
- [x] MR-64: Add MCP status event handling — BFF forwards `event: mcp_status` SSE events in `proxy.router.ts`, `SSEProcessor.ts` parses `mcp_status` events, `McpStatusPanel.tsx` with PatternFly `ExpandableSection` + color-coded `Label` (blue/green/red), `mcpEvents` array exposed from hook
- [x] MR-65: Add stream interrupted badge + recovery — `wasInterrupted` boolean in `useStreamingAPI.ts`, set on non-retryable error (not user cancel), reset on new stream start
- [x] MR-66: Add graceful shutdown handling — `beforeunload` listener in `useStreamingAPI.ts`, `navigator.sendBeacon` for best-effort cancel notification, graceful stream cancel on tab close, cleanup on unmount

#### Additional deliverables
- `authenticated-fetch.ts`: `parseRetryAfterSeconds()` handles both delta-seconds and HTTP-date formats
- `useRefreshableToken.tsx`: on refresh 401, calls `notifySessionExpired()` instead of hard redirect
- Redux slices: added `resetChatsState`, `clearAllToasts`, `resetPersonalization` reset actions
- 6 new files, 19 modified files, build verified clean

**Milestone:** ✅ Resilient UI. Survives network drops, auth expiry, rate limiting, stale runs, page refreshes, tab close.

---

### PHASE 6: UX POLISH (Weeks 8-9)

**Goal:** Add features that make the chat experience polished and professional.
**Depends on:** Backend /feedback endpoint (Part A MR-24 Langfuse integration)

#### Feedback System (MRs 67-69) — ✅ COMPLETE
- [x] MR-67: Add feedback buttons on AI messages — `FeedbackButtons.tsx` with ThumbsUp/ThumbsDown (lucide-react), hover-visible below AI messages, loading state, toggle support, disabled with tooltip when `traceId` unavailable
- [x] MR-68: Add feedback API service and BFF route — `feedback-api.ts` posts to `/api/proxy/agent/feedback` with `{trace_id, name, value, kwargs}`; BFF now forwards `metadata` SSE events (was skipping them); `SSEProcessor` emits `kind: 'metadata'`; `StreamingManager` calls `onMetadata`; `useStreamingAPI` captures and exposes `traceId`
- [x] MR-69: Add feedback state tracking — `ChatItem.feedback: Record<string, 'up' | 'down'>` in Redux `chats.ts`; `setMessageFeedback(chatId, messageId, feedback)` reducer; persisted to localStorage via chatStorage

#### Backend: Feedback → Langfuse Scores — ✅ COMPLETE
- [x] B-1: `POST /feedback` route — `deep_agent/aegra/feedback.py` with FastAPI app, validates `FeedbackRequest`, calls `langfuse_client.score(trace_id, name, value, **kwargs)`, graceful degradation when Langfuse unconfigured; registered via `aegra.json` `http.app`
- [x] B-2: Stream metadata event — `manager.py` yields `{"type": "metadata", "content": {"run_id", "trace_id", "thread_id"}}` before streaming loop; frontend captures for feedback correlation

#### Message Enhancements (MRs 70-74) — ✅ COMPLETE
- [x] MR-70: Add message editing — Pencil icon on hover for last human message, inline textarea edit mode, Save/Cancel, re-submits truncated conversation with edited message
- [x] MR-71: Add thinking/reasoning blocks — Detects `<think>`/`<thinking>` tags and `type: "thinking"` content blocks; renders in collapsed PatternFly `ExpandableSection` with muted monospace styling
- [x] MR-72: Add copy actions — Copy button on AI messages (with Copied! feedback), copy button on fenced code blocks (top-right corner, 2s Check icon transition)
- [x] MR-73: Add response latency indicator — `useStreamingAPI` tracks `streamStartTime`, `firstTokenTime`, `streamEndTime`; exposes `timeToFirstToken` and `totalDuration`; shown below last AI message as subtle muted text
- [x] MR-74: Add custom data renderer — `CustomDataRenderer.tsx` handles `table` (PatternFly Table), `json` (formatted code), `list` (bulleted), default (pretty JSON); wired into `AiMessageBubble` via `custom_data` field

#### Additional deliverables
- Backend: 6 new unit tests for feedback (Langfuse mock, graceful degradation, validation, score failure)
- Backend: Manager test updated for metadata-first assertion
- Frontend: 3 new files, 14 modified files, build verified clean
- Added `@patternfly/react-table` dependency for custom data renderer

#### Navigation & Discovery (MRs 75-78) — ✅ COMPLETE
- [x] MR-75: Add keyboard shortcuts — `useKeyboardShortcuts.ts` hook with layered listener; `/` focus input, `Esc` cancel/blur, `Ctrl+N` new chat, `Ctrl+Shift+S` settings, `?` help dialog, `Ctrl+Shift+E` export
- [x] MR-76: Add keyboard shortcuts help dialog — `KeyboardShortcutsDialog.tsx` PatternFly Modal with styled `<kbd>` elements, toggled via `?` key
- [x] MR-77: Add export conversation — `export-chat.ts` with Markdown/JSON export + `downloadFile`; PatternFly Dropdown in ChatMessagesView with Download icon
- [x] MR-78: Add agent health indicator — `useAgentHealth.ts` polls `/api/health/agent` every 30s; green/red/gray dot in Sidebar with Tooltip

#### Accessibility (MRs 79-80) — ✅ COMPLETE
- [x] MR-79: Add WCAG 2.1 AA keyboard navigation — Skip-to-main link, focus management on route change, sidebar `role="listbox"` with Arrow/Enter/Space navigation, global `:focus-visible` outlines
- [x] MR-80: Add ARIA labels and screen reader support — `role="log"` + `aria-live="polite"` on message list, `role="article"` per message, `aria-label` on all interactive elements (input, send, cancel, feedback, delete, settings, logout), `aria-pressed` on feedback buttons, `sr-only` live region for stream status announcements, ARIA on ErrorRecovery/InterruptBanner/TodoStrip/McpStatusPanel

#### Additional deliverables
- `InputForm` converted to `forwardRef` for focus management
- `global.css`: skip link visibility, focus-visible outline with PF brand token
- 4 new files, 11 modified files, build verified clean

**Milestone:** ✅ UX Polish complete. Feedback with Langfuse scores, message editing, thinking blocks, copy actions, latency indicator, custom data renderer, keyboard shortcuts, export, agent health, WCAG 2.1 AA accessibility.

---

### PHASE 7: PRODUCTION HARDENING (Week 10)

**Goal:** Add observability, security headers, and production-ready infrastructure.

#### OpenTelemetry Integration (MRs 81-84)
- [ ] MR-81: Add OTEL SDK bootstrap (3h)
- [ ] MR-82: Add Fastify + HTTP auto-instrumentation (2h)
- [ ] MR-83: Add structured logging with Pino (3h)
- [ ] MR-84: Add trace ID in response headers (2h)

#### Security Headers (MRs 85-87)
- [ ] MR-85: Add Content Security Policy (2h)
- [ ] MR-86: Add security headers (2h)
- [ ] MR-87: Add request size limits (1h)

#### Infrastructure (MRs 88-90)
- [ ] MR-88: Add announcement banner (2h)
- [ ] MR-89: Add version endpoint and display (2h)
- [ ] MR-90: Update Containerfile and compose (2h)

**Milestone:** Production-ready. OTEL traces, structured logging, security headers, health checks, containerized.

---

### PHASE 8: TESTING & QUALITY (Week 11)

**Goal:** Comprehensive test coverage and quality gates.

- [ ] MR-91: Add unit tests for Redux slices (4h)
- [ ] MR-92: Add unit tests for streaming engine (4h)
- [ ] MR-93: Add unit tests for BFF proxy (3h)
- [ ] MR-94: Add component tests (4h)
- [ ] MR-95: Add ESLint + TypeScript strict checks (2h)
- [ ] MR-96: Add CI pipeline (3h)

**Milestone:** Quality gates established. Unit tests, component tests, BFF tests, CI pipeline, strict TypeScript.

---

## Feature Catalog (Backend)

### Production Error Handling Framework
**Source:** aegra, agent-ship, mcp-memory-service | **MRs:** 43-49 | **Impact:** 90% fewer incidents

- Specific exception handling (never bare `except:`)
- Retry with exponential backoff (tenacity)
- Circuit breaker for external dependencies
- Graceful degradation with fallback strategies

### Multi-Layer Caching System
**Source:** omnicache-ai | **MRs:** 69-77 | **Impact:** 70% token cost reduction

5-layer cache hierarchy:
1. Semantic cache (cosine similarity ≥ 0.95)
2. Response cache (exact model + messages hash)
3. Retrieval cache (query results)
4. Embedding cache (text → vector)
5. Context cache (conversation turns)

### Memory Consolidation
**Source:** mcp-memory-service | **MRs:** 78-83 | **Impact:** 60% token reduction

- Exponential decay scoring
- Semantic clustering (DBSCAN)
- Relationship inference via LLM
- APScheduler for automatic consolidation

### OpenTelemetry Integration
**Source:** hello-dataverse-agent | **MRs:** 91-92 | **Impact:** 15min MTTR

- OTEL spans for LLM calls, tool invocations, subagent calls
- Custom metrics: token count, duration, success/failure
- W3C trace propagation (backend ↔ frontend)

### DeepAgents Agent Architecture
**Source:** LangChain deepagents | **MRs:** 103-134

- Agent type hierarchy (SubAgent, CompiledSubAgent, AsyncSubAgent, HarnessProfile)
- Middleware pipeline (summarization, tool patching, skills, memory)
- Filesystem abstraction (6 tools, 4 backends, protocols)
- Multi-provider support (OpenAI, Anthropic, Google, Ollama)
- Async task management with lifecycle handlers
- Declarative filesystem permissions

---

## Feature Catalog (Frontend)

### Streaming Engine
**Source:** dataverse-ui | **MRs:** 13-17

- Singleton GlobalStreamingManager (survives unmounts)
- SSE chunk processing (token, message, error, mcp_status, [DONE])
- Deduplication via chunk_id
- Stream cancellation with BFF abort detection

### Deep Agent UI Features
**Source:** deep-agents-ui | **MRs:** 31-42

- Sub-agent delegation indicator with animated states
- Human-in-the-loop interrupt handler (tool approval, confirmation)
- File artifacts viewer with syntax highlighting
- Todo/task progress stepper

### PatternFly 6 Design System
**Source:** PatternFly 6 | **MRs:** PF-01–PF-05

- Page, Masthead, Sidebar layout
- Component library: Button, Modal, Alert, Dropdown, EmptyState, Tabs
- Dark/light theme via `.pf-v6-theme-dark`
- Coexists with Tailwind (PatternFly = components, Tailwind = utilities)

### Observability (Frontend)
**Source:** dataverse-ui | **MRs:** 81-84

- OpenTelemetry SDK with Fastify auto-instrumentation
- W3C traceparent propagation to backend
- Pino structured logging (JSON production, pretty dev)
- X-Trace-ID / X-Request-ID headers on all responses

---

## Success Metrics

### Backend Gates

| Gate | Week | Criteria |
|------|------|----------|
| Aegra Integration | 3 ✅ | Working, 30+ concurrent jobs, load test passes |
| Production Foundations | 5 ⏳ | Error handling ✅, type safety ✅; coverage + test infra remaining |
| Scalability | 7 | 70% cost reduction, cache hit >90%, 3x throughput |
| Observability | 9 | MTTR <15min, OTEL traces, structured logging |
| Developer Experience | 10 | CLI functional, pre-commit hooks, docs complete |
| DeepAgents: Agents | 11 | Type hierarchy, middleware functional |
| DeepAgents: Filesystem | 12 | Abstraction complete, backends working |
| DeepAgents: Providers | 13 | Multi-provider, async task API |
| DeepAgents: Complete | 14 | Permissions, utilities, integration tests |

### Frontend Gates

| Gate | Week | Criteria |
|------|------|----------|
| Foundation | 1 ✅ | Redux, BFF proxy, Bearer auth, error types |
| PatternFly | 2 ✅ | Design system integrated, all primitives migrated, Radix removed |
| Core Chat | 3-4 ✅ | Streaming, threads, tool rendering, toasts, responsive |
| Deep Agent | 5-6 ✅ | Sub-agents, interrupts, file artifacts, task progress, debug mode |
| Personalization | 7 ✅ | Memories, rules, themes, settings |
| Resilience | 8 | Error recovery, auth resilience, stale detection |
| UX Polish | 9-10 | Feedback, editing, accessibility, shortcuts |
| Production | 11 | OTEL, security headers, container |
| Testing | 12 | Unit/component tests, CI pipeline, strict TS |

---

## Tech Stack

### Backend (template-agent)

| Layer | Choice |
|-------|--------|
| Language | Python 3.12+ |
| Framework | LangGraph + LangChain |
| Infrastructure | Aegra (worker queue, auth, scaling) |
| Database | PostgreSQL (checkpoints), SQLite (WAL mode) |
| Cache | Redis + diskcache + FAISS |
| Observability | OpenTelemetry + structlog + Langfuse |
| Testing | pytest + pytest-asyncio + pytest-mock + pytest-cov |
| CLI | typer + rich |
| Quality | ruff + black + pyright + mypy + bandit |
| Deployment | Containerfile + K8s manifests + Helm |

### Frontend (template-ui)

| Layer | Choice |
|-------|--------|
| Language | TypeScript (strict mode) |
| UI Framework | React 19 + Vite + SWC |
| Design System | PatternFly 6 + Tailwind CSS 4 |
| State | Redux Toolkit |
| LangGraph SDK | `@langchain/langgraph-sdk` (latest) |
| BFF | Fastify 5 + TypeScript |
| Auth | @fastify/oauth2 + @fastify/session + Bearer forwarding |
| Sessions | Redis (connect-redis) with in-memory fallback |
| Observability | OpenTelemetry SDK + Pino |
| Testing | Vitest + Testing Library + fastify.inject() |
| Deployment | Containerfile + compose.yml + OpenShift manifests |

---

## Source Repositories Analyzed

### Backend Sources (17 repos)
1. **aegra** — Production infrastructure (worker queue, auth, scaling)
2. **agent-lightning** — 1,838 tests, type safety, performance
3. **agent-ship** — MCP integration, OPIK observability
4. **mcp-memory-service** — 1,547 tests, memory consolidation
5. **omnicache-ai** — 5-layer caching (70% cost reduction)
6. **langclaw** — Multi-agent routing, message bus
7. **CyberClaw** — Security sandbox, audit logging
8. **hello-dataverse-agent** — OpenTelemetry integration
9. **deepagents** — Agent types, middleware, filesystem abstraction
10. **flock** — Multi-agent coordination
11. **langgraph-librarian** — Knowledge graph patterns
12. **langgraph-temporal-workflow** — Workflow orchestration
13. **lightspeed-evaluation** — Evaluation framework
14. **Agent-Git** — Git operations, rollback
15. **cognify** — Reasoning patterns
16. **langgraph-bigtool** — Tool handling
17. **langgraph-agent-lightning-optimization** — Performance tuning
18. **LangChain deepagents** — Official LangChain agent framework

### Frontend Sources (4 repos)
1. **deep-agents-ui** — Sub-agent indicator, file viewer, interrupt handler, todo progress
2. **sales-assistant-frontend** — PatternFly, memories, skills, themes, editing, thinking blocks
3. **dataverse-ui** — Redux, streaming manager, rules editor, BFF proxy, OTEL, vitest
4. **template-ui** — Fastify BFF, project structure, auth toggle, Containerfile, compose

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking changes | HIGH | Feature flags, migration guides, incremental MRs |
| Complexity creep | MEDIUM | Keep core simple, features optional/pluggable |
| Performance regression | MEDIUM | Benchmark every change, load tests |
| Timeline slip | MEDIUM | Weekly milestones, parallel workstreams |
| Cross-track dependency blocks | MEDIUM | Mock APIs, feature-flag partial integration |
| Design system conflicts | LOW | PatternFly prefixed classes, clear CSS layers |
| Dependency conflicts | LOW | Lock files, version constraints |

---

## Key Dependencies (Combined)

**Backend Core:**
- LangChain 0.2+ • LangGraph 0.1+ • Pydantic v2 • pytest + pytest-asyncio • structlog

**Backend Performance:**
- aegra-cli • tenacity • diskcache • Redis • APScheduler

**Backend Observability:**
- OpenTelemetry • prometheus-client

**Backend DeepAgents:**
- langchain-core • langchain-openai • langchain-anthropic • langchain-google-genai • scikit-learn

**Frontend Core:**
- React 19 • TypeScript (strict) • Vite + SWC • Redux Toolkit • @langchain/langgraph-sdk

**Frontend Design:**
- @patternfly/react-core • @patternfly/react-icons • Tailwind CSS 4

**Frontend BFF:**
- Fastify 5 • @fastify/oauth2 • @fastify/session • ioredis

**Frontend Observability:**
- @opentelemetry/sdk-node • @opentelemetry/auto-instrumentations-node • pino

**Frontend Testing:**
- Vitest • @testing-library/react • jsdom

---

## Summary

| Dimension | Backend | Frontend | Combined |
|-----------|---------|----------|----------|
| Duration | 14 weeks | 11 weeks | 14 weeks (parallel) |
| MRs | 134 | 101 | 235 |
| Avg MR size | 2-4h | 2-4h | 2-4h |
| Completed | 52 MRs ✅ | 47 MRs ✅ | 99 MRs ✅ |
| Remaining | 82 MRs | 54 MRs | 136 MRs |

**What Makes This Platform "Best in the World":**
1. **Full-stack:** Production backend + polished frontend, integrated end-to-end
2. **Production-ready:** 80%+ coverage, error handling, type safety (both tracks)
3. **Scalable:** 30+ concurrent jobs, worker queue, streaming engine
4. **Performant:** 70% cost reduction (caching), 3x throughput, optimized streaming
5. **Observable:** <15min MTTR, W3C trace propagation across full stack
6. **Secure:** JWT + RBAC + CSP + sandbox + filesystem permissions
7. **Accessible:** WCAG 2.1 AA, PatternFly design system
8. **Developer-friendly:** CLI, pre-commit hooks, comprehensive docs, quality gates
9. **Ecosystem-compatible:** Full LangChain DeepAgents alignment, multi-provider
10. **Extensible:** Middleware architecture, pluggable backends, Redux slices, custom renderers
