"""Authentication permission utilities."""

from functools import wraps

from django.shortcuts import redirect


def role_required(*roles):
    """Decorator to restrict views by user role."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("authentication:login")
            if request.user.role not in roles:
                from django.http import HttpResponseForbidden
                return HttpResponseForbidden("Accès non autorisé pour votre rôle.")
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def admin_required(view_func):
    return role_required("ADMIN")(view_func)


def operator_required(view_func):
    return role_required("ADMIN", "OPERATOR")(view_func)
