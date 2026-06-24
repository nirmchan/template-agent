"""Platform audit logging — structured events gated by PLATFORM_AUDIT_ENABLED."""

from deep_agent.src.platform.audit.config import is_audit_enabled
from deep_agent.src.platform.audit.emitter import emit_audit_event
from deep_agent.src.platform.audit.events import AuditEventType

__all__ = [
    "AuditEventType",
    "emit_audit_event",
    "is_audit_enabled",
]
