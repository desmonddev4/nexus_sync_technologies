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
):
    user = getattr(request, "user", None)
    actor = user if isinstance(user, Model) and user.is_authenticated else None
    remote_addr = request.META.get("REMOTE_ADDR", "")
    try:
        ip_address = str(ipaddress.ip_address(remote_addr)) if remote_addr else None
    except ValueError:
        ip_address = None
    return AuditLog.objects.create(
        actor=actor,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id or "")[:64],
        outcome=outcome,
        http_method=request.method,
        ip_address=ip_address,
        request_id=request.headers.get("X-Request-ID", "")[:64],
        metadata=metadata or {},
    )