"""
DataExtract AI - Custom Exception Handler
==========================================
Standardized API error response format.
"""

from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    """
    Custom DRF exception handler that returns a standardized JSON error format.
    """
    response = exception_handler(exc, context)

    if response is not None:
        custom_data = {
            "error": True,
            "status_code": response.status_code,
            "message": _get_error_message(exc, response.status_code),
            "details": response.data,
        }
        response.data = custom_data

    return response


def _get_error_message(exc, status_code: int) -> str:
    """Generate user-friendly error messages based on status code."""
    messages = {
        400: "Bad request. Please check your input and try again.",
        401: "Authentication required. Please log in.",
        403: "Permission denied. You do not have access to this resource.",
        404: "Resource not found.",
        405: "Method not allowed.",
        409: "Conflict. The resource has been modified.",
        429: "Too many requests. Please slow down and try again later.",
        500: "Internal server error. Our team has been notified.",
    }
    return messages.get(status_code, "An unexpected error occurred.")
