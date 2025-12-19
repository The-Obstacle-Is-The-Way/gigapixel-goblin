"""CLI module for GIANT (Spec-12).

Provides the command-line interface for running GIANT inference,
benchmarks, data downloads, and trajectory visualization.
"""

from __future__ import annotations

from giant.cli.main import Mode, Provider, app

__all__ = ["Mode", "Provider", "app"]
