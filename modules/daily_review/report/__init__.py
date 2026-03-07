"""Reporting layer for daily review."""

from .llm_digest import generate_llm_summary
from .renderer import render_report

__all__ = ["generate_llm_summary", "render_report"]
