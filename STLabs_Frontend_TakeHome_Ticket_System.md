# Frontend Take-Home Assignment

## Build an AI-First Ticket Management System (Frontend-Centric)

**Focus:** Frontend quality, AI-assisted UX, async interaction patterns  
**Framework:** React (preferred), Vue, or Svelte  
**AI usage:** Allowed (and encouraged), with session transcripts

---

## What we are looking for

We care most about your ability to build a clean, intuitive frontend that handles asynchronous AI interactions gracefully. A polished experience with thoughtful loading states and error handling is better than a broad feature set.

## Context

You are designing the frontend (and light backend) for an AI-powered ticket management system used by internal support teams. The goal is to provide a clean, intuitive UI that uses AI to help triage and respond to support tickets effectively.

This is a full-stack assignment with frontend as the primary focus, but some backend/API work is needed to provide or simulate AI and ticket logic.

---

# Core Scope (required)

## 1. Ticket Submission Form

Build a form for users to report an issue, with:

- Fields: Title, Description, Email, optional Priority, Department
- Button: "Generate AI Suggestions"
  - When clicked, simulate or call an API that:
    - Auto-selects a category (e.g., "Network", "Software", "Access")
    - Generates tags from the description
    - Suggests a priority level
- Display AI suggestions as editable, with a "Use Suggestion" option.

## 2. Ticket Dashboard

A ticket list UI for support team use:

- Show each ticket's:
  - Title, Description, Status, Category, Tags, Priority
  - AI-suggested response (e.g., "Try resetting your password.")
- Allow changing status (New, In Progress, Resolved)
- Add filters by category, status, and tag
- Optimistic UI updates encouraged

## 3. AI Integration (Lightweight)

Simulate AI using either:

- Actual integration (e.g., OpenAI API or a Hugging Face model)
- Or mock data + logic in your backend

Frontend should treat these responses as asynchronous:

- Show loading indicators
- Handle errors gracefully

## 4. Backend (Minimal)

Use Python with FastAPI (or Flask/Django) to provide:

- API to submit/retrieve/update tickets (in-memory or SQLite)
- Endpoint to simulate AI suggestions:
  - Return mocked or static AI predictions (category, tags, priority, response)

Optional: You may use OpenAI, Cohere, or Hugging Face APIs to return real AI output.

---

# Implementation Guidelines

## Tech Stack

- Frontend: React (preferred), Vue, or Svelte
  - Component library optional (MUI, Chakra, Tailwind, Ant Design, etc.)
  - TypeScript preferred but not required
- Backend: FastAPI or Flask (can be minimal; no auth or DB setup needed)
- State Management: React hooks, Context API, or lightweight stores
- AI Integration: Use OpenAI or mock logic

## What to prioritize

- Usability, responsiveness, and layout quality
- Async UX: loading indicators, error feedback, optimistic updates
- Intuitive AI prompts with clear user control over suggestions
- Modular components with readable code and sensible structure

## What we do not expect

- A production-grade backend or real model integration
- Perfect styling or pixel precision
- Every edge case handled — pick a coherent slice and document choices

## Optional extensions (choose at most one)

If you finish early, pick one extension that best shows your strengths. Do not do multiple unless you truly have time.

- **Editable tickets or comments:** Add inline editing or a comment thread to tickets.
- **Theme toggle:** Dark/light mode with persistent preference.
- **Live updates:** WebSocket or polling to update the dashboard in real time.
- **Dockerize:** Containerize the app for local development.
- **Tests:** A small set of unit tests (Jest, Pytest).

---

# OpenRouter

We will be providing you with an OpenRouter API key you can use to run/test your service. It gives you access to hundreds of AI models through a single endpoint. You can find the quickstart guide here: [https://openrouter.ai/docs/quickstart](https://openrouter.ai/docs/quickstart).

Additionally, we encourage you to use the same token to run a coding agent to help you with this assignment. For example, here is the guide to setup Claude Code: [https://openrouter.ai/docs/guides/guides/claude-code-integration](https://openrouter.ai/docs/guides/guides/claude-code-integration). Feel free to use any coding agent to help you if you want.

The token we will be providing you will have a set usage limit, but if you go over and need more, just contact us.

---

# Deliverables

- GitHub repo or zip containing:
  - Source code (frontend + backend)
  - A sample session (or all sessions) from your AI assisted coding sessions. Include session transcripts from Claude Code, Codex, OpenCode, Cursor or whatever your tool of choice is.
  - `README.md` with:
    - Setup instructions (install, run locally)
    - AI behavior explanation (real or mocked)
    - Design decisions & known limitations
    - Screenshots or a short screen capture (if possible)
    - How you used AI to develop during the take home

We index heavily on the `README.md` and your coding agent session transcripts. We like to see how you reason about engineering decisions.

---

# Evaluation Criteria

| Area                | Expectation                                                            |
| ------------------- | ---------------------------------------------------------------------- |
| Frontend Quality    | Usability, responsiveness, layout, async UX (loading, error, feedback) |
| Code Clarity        | Modular components, readable code, sensible structure                  |
| AI UX Integration   | Intuitive prompts, feedback for AI steps, clear user control           |
| Backend Integration | Well-defined APIs and good separation of concerns                      |
| Documentation       | Clear, complete setup and design summary                               |

---

# Mock API Spec (for AI Suggestions)

## POST /api/ai/suggest

### Request Body

```json
{
  "title": "Can't access VPN",
  "description": "I tried to connect to the VPN but it keeps timing out."
}
```

### Mock Response

```json
{
  "category": "Networking",
  "tags": ["VPN", "timeout", "remote access"],
  "priority": "High",
  "suggested_response": "Please ensure you're on the company network and restart your VPN client. If that fails, contact IT Support at x1234."
}
```
