import ipaddress

from django.db.models import Model

from .models import AuditLog


def record_audit_event(
    *,
    request,
    action,
    resource_type,
    resource_id="",
    outcome=AuditLog.Outcome.SUCCESS,
    metadata=None,
    actor=None,
):
    request_user = getattr(request, "user", None)
    if actor is None:
        actor_obj = (
            request_user
            if isinstance(request_user, Model) and request_user.is_authenticated
            else None
        )
    else:
        actor_obj = (
            actor
            if isinstance(actor, Model) and getattr(actor, "is_authenticated", True)
            else None
        )
    remote_addr = request.META.get("REMOTE_ADDR", "")
    try:
        ip_address = str(ipaddress.ip_address(remote_addr)) if remote_addr else None
    except ValueError:
        ip_address = None
    return AuditLog.objects.create(
        actor=actor_obj,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id or "")[:64],
        outcome=outcome,
        http_method=request.method,
        ip_address=ip_address,
        request_id=request.headers.get("X-Request-ID", "")[:64],
        metadata=metadata or {},
    )