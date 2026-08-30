"""
Shared contract types used by every subsystem (Members 1-5).

This file should be treated as team-owned. A change here is a team
decision, not a solo one, because every module imports from it.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class FileRef(BaseModel):
    """Reference to a file living in the shared workspace filesystem."""
    id: str
    filename: str
    path: str
    mime_type: str = "application/octet-stream"


class Artifact(BaseModel):
    """A file produced by the system (docx, xlsx, csv, png, etc.)."""
    id: str
    filename: str
    path: str
    mime_type: str = "application/octet-stream"


class ToolResult(BaseModel):
    """
    Universal envelope every agent-callable tool returns.
    The Agent (Member 1) only ever has to understand this one shape,
    no matter which subsystem produced it.
    """
    success: bool
    data: dict = Field(default_factory=dict)
    error: str | None = None
    metadata: dict = Field(default_factory=dict)


class AppError(BaseModel):
    """Standardized error so the Agent can decide whether to retry."""
    code: str
    message: str
    retryable: bool = False
