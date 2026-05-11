"""Aegra integration for LangGraph Platform deployment.

This package bridges template-agent with the LangGraph Platform (aegra),
enabling the agent to be served via `langgraph dev` or `langgraph up`
and used with deep-agents-ui.

Modules:
    graph: Graph builder and exported agent for langgraph.json
    state: Extended LangGraph state schema
    converters: State conversion and serialization utilities
    serialization: Full state serialization/deserialization
    nodes: Error-handling node wrappers for graph execution
    middleware: Authentication middleware (API key, JWT)
    telemetry: OpenTelemetry + Langfuse integration
    redis: Redis caching layer
    worker: Worker pool configuration
"""

__version__ = "0.1.0"
