"""Schemas for the GitHub integration (via Nango)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class GithubStatus(BaseModel):
    connected: bool


class RepoView(BaseModel):
    name: str
    full_name: str
    private: bool = False
    clone_url: str


class RepoCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    private: bool = True
