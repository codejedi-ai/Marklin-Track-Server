"""
CMDB-grounded ticket triage.

POST /api/ai/suggest calls this. Instead of returning mocked predictions, it looks
the submitter up in the CMDB graph (their device, department, apps, MFA status) and
grounds the category / priority / tags / response in real Configuration Items.

A fully deterministic grounding always runs (so the endpoint works with no LLM and
is unit-testable). When an OpenRouter key is present, an LLM refines the wording —
but the grounded facts and related CIs come from the graph, not the model's memory.
"""
from __future__ import annotations

import json
import re
from typing import Optional

from config import settings

_NETWORK_KW = ("vpn", "network", "wifi", "wi-fi", "ethernet", "dns", "internet",
               "connect", "connection", "timeout", "timing out", "latency", "offline")
_ACCESS_KW = ("access", "login", "log in", "sign in", "signin", "password", "mfa",
              "2fa", "sso", "locked out", "permission", "denied", "can't get in")
_SOFTWARE_KW = ("install", "update", "crash", "crashes", "error", "bug", "freeze",
                "frozen", "slow", "won't open", "not working", "broken")
_ENCRYPTION_KW = ("encrypt", "filevault", "bitlocker", "luks", "disk encryption")


def _has(text: str, words) -> bool:
    return any(w in text for w in words)


def gather_context(store, email: Optional[str], description: str) -> tuple[dict, list[dict]]:
    """Return (context, related_cis) pulled from the CMDB graph."""
    ctx: dict = {}
    related: list[dict] = []
    desc = (description or "").lower()

    # 1. The submitter and their CIs
    if email:
        found = None
        try:
            found = store.get_ci(email)
        except Exception:
            found = None
        if found:
            user = found["ci"]
            ctx["user"] = {
                "name": user.get("name"), "email": user.get("email"),
                "mfa_enabled": user.get("mfa_enabled"),
                "department": user.get("department"), "team": user.get("team"),
                "title": user.get("title"), "status": user.get("status"),
            }
            related.append({"type": "user", "id": email, "name": user.get("name")})
            devices, apps = [], []
            for nb in found.get("relationships", []):
                node = nb["node"]
                if nb["rel"] == "ASSIGNED_TO":
                    devices.append({"hostname": node.get("hostname"),
                                    "device_id": node.get("device_id"),
                                    "os": node.get("os"), "status": node.get("status"),
                                    "encryption": node.get("encryption")})
                elif nb["rel"] == "USES":
                    apps.append(node.get("name") or node.get("name_norm"))
            ctx["devices"] = devices
            ctx["apps_used"] = apps

    # 2. Entities explicitly mentioned in the description
    mentioned_apps = []
    try:
        for app in store.list_label("App"):
            name = app.get("name")
            if name and len(name) > 2 and name.lower() in desc:
                mentioned_apps.append(name)
                related.append({"type": "app", "id": app.get("name_norm"), "name": name})
    except Exception:
        pass
    ctx["mentioned_apps"] = sorted(set(mentioned_apps))

    return ctx, related


def deterministic_suggest(title: str, description: str, ctx: dict) -> dict:
    text = f"{title} {description}".lower()
    user = ctx.get("user") or {}
    apps = ctx.get("mentioned_apps") or ctx.get("apps_used") or []

    # --- category ---
    if _has(text, _NETWORK_KW):
        category = "Network"
    elif apps or _has(text, _ACCESS_KW):
        category = "Access"
    elif _has(text, _SOFTWARE_KW) or _has(text, _ENCRYPTION_KW):
        category = "Software"
    else:
        category = "General"

    # --- priority (grounded) ---
    priority = "Medium"
    title_l = (user.get("title") or "").lower()
    dept_l = (user.get("department") or "").lower()
    mfa_off = user.get("mfa_enabled") is False
    exec_user = "chief" in title_l or "cto" in title_l or "executive" in dept_l
    dev_inactive = any(d.get("status") == "inactive" for d in ctx.get("devices", []))
    if exec_user or (category == "Access" and mfa_off) or dev_inactive:
        priority = "High"

    # --- tags (from real entities + signals) ---
    tags = list(apps)
    if mfa_off or "mfa" in text or "2fa" in text:
        tags.append("MFA")
    if "sso" in text or apps:
        tags.append("SSO")
    if _has(text, _NETWORK_KW):
        tags.append("VPN" if "vpn" in text else "Network")
    if _has(text, _ENCRYPTION_KW):
        tags.append("Encryption")
    # de-dup, cap
    seen, tags_out = set(), []
    for t in tags:
        if t and t.lower() not in seen:
            seen.add(t.lower())
            tags_out.append(t)
    tags_out = tags_out[:6]

    # --- grounded suggested response ---
    app_name = apps[0] if apps else None
    if category == "Access" and mfa_off and app_name:
        resp = (f"Your account shows MFA disabled, which commonly blocks SSO access "
                f"to {app_name}. Enable MFA in Okta and retry. If it persists, IT can "
                f"re-sync your {app_name} entitlement.")
    elif category == "Access" and app_name:
        resp = (f"Confirm you're signed into Okta SSO, then reopen {app_name}. "
                f"If access is still denied, IT will verify your {app_name} assignment.")
    elif category == "Network":
        resp = ("Please ensure you're on the company network or VPN and restart the "
                "client. If it keeps timing out, IT will check your device connectivity.")
    elif category == "Software" and _has(text, _ENCRYPTION_KW) and ctx.get("devices"):
        host = ctx["devices"][0].get("hostname")
        resp = (f"We'll check the encryption status on {host}. Please keep the device "
                f"plugged in and connected while IT verifies the disk-encryption profile.")
    else:
        resp = ("Thanks for the report. IT has logged this and will follow up shortly "
                "with next steps.")

    return {"category": category, "tags": tags_out, "priority": priority,
            "suggested_response": resp}


def _llm_refine(title: str, description: str, ctx: dict, base: dict) -> dict:
    """Refine wording with an OpenRouter LLM, constrained to the grounded facts."""
    from llama_index.llms.openrouter import OpenRouter

    llm = OpenRouter(api_key=settings.resolve_openrouter_key(),
                     model=settings.ASK_MODEL, max_tokens=512, temperature=0.2)
    prompt = (
        "You are an IT support triage assistant. Using ONLY the CMDB facts provided, "
        "produce a JSON object with keys: category (one of Network, Access, Software, "
        "General), tags (array of short strings), priority (Low, Medium, High), "
        "suggested_response (one helpful paragraph). Do not invent facts not present.\n\n"
        f"Ticket title: {title}\nDescription: {description}\n"
        f"CMDB facts: {json.dumps(ctx, default=str)}\n"
        f"Deterministic baseline (improve wording, keep grounded): {json.dumps(base)}\n\n"
        "Return ONLY the JSON object."
    )
    raw = str(llm.complete(prompt))
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return base
    data = json.loads(match.group(0))
    out = dict(base)
    for k in ("category", "priority", "suggested_response"):
        if data.get(k):
            out[k] = data[k]
    if isinstance(data.get("tags"), list) and data["tags"]:
        out["tags"] = [str(t) for t in data["tags"]][:6]
    return out


def suggest(store, title: str, description: str = "", email: Optional[str] = None,
            use_llm: bool = True) -> dict:
    ctx, related = gather_context(store, email, description)
    result = deterministic_suggest(title, description, ctx)
    if use_llm and settings.resolve_openrouter_key():
        try:
            result = _llm_refine(title, description, ctx, result)
        except Exception:
            pass  # fall back to the grounded deterministic result
    result["related_cis"] = related
    result["grounded"] = bool(ctx.get("user") or related)
    return result
