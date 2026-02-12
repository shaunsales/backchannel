from fasthtml.common import *


def success(msg):
    return Div(
        Span(msg),
        cls="alert alert-success text-sm",
        role="alert",
    )


def error(msg):
    return Div(
        Span(msg),
        cls="alert alert-error text-sm",
        role="alert",
    )


def warning(msg):
    return Div(
        Span(msg),
        cls="alert alert-warning text-sm",
        role="alert",
    )
