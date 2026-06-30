"""
CMDB Agent — Configuration Item (CI) schemas and API models.

These describe the normalized shapes stored in the graph and returned by the API.
The graph is the source of truth; these models validate and document the contract.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class CIType(str, Enum):
    DEVICE = "device"
    USER = "user"
    APP = "app"


# ---------------------------------------------------------------------------
# Configuration Items
# ---------------------------------------------------------------------------

class Device(BaseModel):
    ci_type: CIType = CIType.DEVICE
    device_id: str
    hostname: Optional[str] = None
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    os: Optional[str] = None
    os_version: Optional[str] = None
    status: Optional[str] = None
    encryption: Optional[bool] = None
    encryption_type: Optional[str] = None
    device_type: Optional[str] = None
    serial_number: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    location: Optional[str] = None
    department: Optional[str] = None
    assigned_user: Optional[str] = None
    last_checkin: Optional[str] = None
    sources: list[str] = Field(default_factory=list)


class User(BaseModel):
    ci_type: CIType = CIType.USER
    uid: str
    name: Optional[str] = None
    email: Optional[str] = None
    employee_id: Optional[str] = None
    department: Optional[str] = None
    team: Optional[str] = None
    title: Optional[str] = None
    mfa_enabled: Optional[bool] = None
    last_login: Optional[str] = None
    status: Optional[str] = None
    groups: list[str] = Field(default_factory=list)
    apps: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class App(BaseModel):
    ci_type: CIType = CIType.APP
    name: str
    name_norm: str
    app_id: Optional[str] = None
    vendor: Optional[str] = None
    app_type: Optional[str] = None
    category: Optional[str] = None
    deployment: Optional[str] = None
    owner: Optional[str] = None
    users_count: Optional[int] = None
    sso_enabled: Optional[bool] = None
    annual_cost_usd: Optional[float] = None
    integrations: list[str] = Field(default_factory=list)
    is_stub: bool = False
    sources: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# API request / response models
# ---------------------------------------------------------------------------

class IngestResult(BaseModel):
    source: str
    detected: str
    nodes_written: int
    edges_written: int
    errors: list[str] = Field(default_factory=list)


class AskRequest(BaseModel):
    question: str = Field(..., examples=["Which users don't have MFA?"])


class AskResponse(BaseModel):
    question: str
    answer: str
    cypher: Optional[str] = None
    rows: Optional[list[dict[str, Any]]] = None
    thoughts: Optional[list[str]] = None        # ReAct trace, line-per-step


# ---------------------------------------------------------------------------
# Tickets (frontend ticket system, grounded in the CMDB)
# ---------------------------------------------------------------------------

class RelatedCI(BaseModel):
    type: str                 # device | user | app
    id: str                   # identifier used to resolve the CI in the graph
    name: Optional[str] = None


class SuggestRequest(BaseModel):
    title: str
    description: str = ""
    email: Optional[str] = None


class SuggestResponse(BaseModel):
    category: str
    tags: list[str] = Field(default_factory=list)
    priority: str
    suggested_response: str
    related_cis: list[RelatedCI] = Field(default_factory=list)
    grounded: bool = False     # whether CMDB facts informed the suggestion


class TicketCreate(BaseModel):
    title: str
    description: str = ""
    email: Optional[str] = None
    department: Optional[str] = None
    priority: Optional[str] = None
    category: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    suggested_response: Optional[str] = None
    related_cis: list[RelatedCI] = Field(default_factory=list)


class Ticket(BaseModel):
    id: str
    title: str
    description: str = ""
    email: Optional[str] = None
    department: Optional[str] = None
    priority: str = "Medium"
    status: str = "New"
    category: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    suggested_response: Optional[str] = None
    related_cis: list[RelatedCI] = Field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class StatusUpdate(BaseModel):
    status: str = Field(..., examples=["In Progress"])


# ---------------------------------------------------------------------------
# Chats (multi-conversation history for /ask)
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str                              # "user" | "assistant"
    content: str
    cypher: Optional[str] = None           # assistant-only
    rows: Optional[list[dict[str, Any]]] = None
    thoughts: Optional[list[str]] = None   # assistant-only ReAct trace
    ts: Optional[str] = None


class Chat(BaseModel):
    id: str
    title: str
    messages: list[ChatMessage] = Field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ChatSummary(BaseModel):
    """Slim view for listing chats — omits the messages array."""
    id: str
    title: str
    message_count: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ChatCreate(BaseModel):
    title: Optional[str] = None


class ChatRename(BaseModel):
    title: str


class ChatSendMessage(BaseModel):
    question: str = Field(..., examples=["Which users don't have MFA?"])
