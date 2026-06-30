"""
CMDB Agent — Configuration

Central settings for the AI-First CMDB knowledge-graph service.
Reads from environment (see .env.example). No secrets hard-coded.
"""
from __future__ import annotations

import os
from functools import lru_cache


class Settings:
    # --- App ---
    APP_NAME: str = "AI-First CMDB Knowledge Graph"
    APP_VERSION: str = "1.0.0"

    # --- Storage backend: "neo4j" (default) or "memory" (no external deps) ---
    STORE_BACKEND: str = os.getenv("STORE_BACKEND", "neo4j")

    # --- Neo4j ---
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "cmdb-dev-password")
    NEO4J_DATABASE: str = os.getenv("NEO4J_DATABASE", "neo4j")

    # --- OpenRouter / LlamaIndex agent ---
    # Key is read from OPENROUTER_API_KEY. For convenience in this take-home,
    # if that's unset we fall back to a token.txt at the repo root.
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL: str = os.getenv(
        "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
    )
    # Any OpenRouter-hosted model id. Default is a strong Claude Sonnet — best
    # balance of code/Cypher quality, reasoning, latency and cost for the ReAct
    # text->Cypher loop. Override via ASK_MODEL (e.g. a larger model for harder
    # questions, or a cheaper one to save tokens).
    ASK_MODEL: str = os.getenv("ASK_MODEL", "anthropic/claude-sonnet-4.5")

    # --- Identity resolution ---
    # Name-similarity threshold above which two user records are the same person.
    USER_MATCH_THRESHOLD: float = float(os.getenv("USER_MATCH_THRESHOLD", "0.85"))

    # --- Tickets / chats (file-backed stores) ---
    TICKETS_FILE: str = os.getenv(
        "TICKETS_FILE",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_store", "tickets.json"),
    )
    CHATS_FILE: str = os.getenv(
        "CHATS_FILE",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_store", "chats.json"),
    )

    def resolve_openrouter_key(self) -> str:
        """Return the OpenRouter key, falling back to repo-root token.txt."""
        if self.OPENROUTER_API_KEY:
            return self.OPENROUTER_API_KEY.strip()
        # token.txt lives one level up from agent/
        here = os.path.dirname(os.path.abspath(__file__))
        token_path = os.path.join(os.path.dirname(here), "token.txt")
        if os.path.exists(token_path):
            with open(token_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        return ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
