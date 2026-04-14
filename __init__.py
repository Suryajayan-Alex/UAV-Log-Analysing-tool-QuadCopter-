"""UAV log analyzer package."""

from __future__ import annotations


__all__ = ["run_analysis"]


def run_analysis(*args, **kwargs):
    """Lazy proxy to avoid importing heavy dependencies at package import time."""
    from .analyzer import run_analysis as _run_analysis

    return _run_analysis(*args, **kwargs)
