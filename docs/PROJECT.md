# JLA

## Purpose

JLA is a personal AI assistant designed to maintain persistent identity, memory, context, and capabilities independently of any individual language model.

JLA should function as one continuous assistant even when the reasoning model powering a particular task changes. A lightweight local model may handle simple tasks, while stronger remotely hosted models may be selected for difficult reasoning, coding, research, or multi-step work.

The long-term goal is an always-available personal assistant that can understand ongoing projects, remember useful information across sessions, retrieve relevant personal context, use external tools, and perform approved actions on the user's behalf.

## Core Principle

**JLA is not the LLM. The LLM is a replaceable reasoning engine used by JLA.**

JLA's persistent identity consists of its memory, behavioral policies, current state, projects, goals, permissions, tools, task history, and other persistent context. Models are temporary reasoning engines selected according to the needs of a task.

Changing from Ollama to OpenAI, Anthropic, or another future provider must not create a new assistant or discard JLA's identity.

## Goals

- Maintain persistent long-term memory across conversations and devices.
- Use Obsidian Markdown vaults as human-readable long-term memory.
- Use SQLite for structured operational state.
- Retrieve only context relevant to the current task.
- Route simple tasks to inexpensive or local models when appropriate.
- Route difficult tasks to more capable models when appropriate.
- Maintain consistent JLA behavior regardless of the selected model.
- Allow models to request controlled tools and actions.
- Enforce permissions outside of the LLM using deterministic backend code.
- Support multi-step tasks that can pause, resume, fail safely, and request approval.
- Provide a desktop interface on Ubuntu.
- Provide a lightweight mobile/web interface for iOS.
- Eventually run the persistent JLA server on a Raspberry Pi 4B.
- Keep the architecture modular enough to add new models, tools, interfaces, and integrations without redesigning JLA.

## MVP Scope

The MVP should provide:

- A persistent JLA identity independent of model provider.
- An assistant Obsidian memory vault.
- Controlled read access to a personal Obsidian vault.
- SQLite operational state.
- Basic memory retrieval.
- A local model through Ollama.
- At least one cloud-model provider.
- Automatic model routing.
- Structured tool calling.
- Deterministic permission enforcement.
- Multi-step task execution.
- Long-term memory creation and updating.
- A FastAPI server interface.
- A Tauri desktop client.

## Explicitly Post-MVP

The following features are useful but should not delay the MVP:

- Raspberry Pi deployment.
- iOS/mobile web client.
- MCP server.
- Google Calendar, Docs, Drive, Gmail, and similar external integrations.
- Advanced embeddings and semantic retrieval.
- Automated memory consolidation.
- Proactive/background assistant behavior.
- Voice input and output.
- Wake-word functionality.

## Core Components

### JLA Server

The server contains the actual assistant logic. It owns orchestration, memory access, retrieval, model routing, tools, permissions, task state, and integrations.

### Obsidian Memory

Markdown files provide persistent, inspectable, editable long-term memory. Obsidian links and metadata can represent relationships between memories.

### SQLite

SQLite stores structured operational information such as conversations, messages, tool calls, tasks, task steps, approvals, indexing metadata, and other machine-oriented state.

SQLite is not intended to replace the human-readable Obsidian memory vault.

### Model Layer

Models are providers of reasoning, classification, summarization, extraction, planning, and language generation. They do not own JLA's identity or security state.

### Model Router

The router selects an appropriate model based on factors such as task type, complexity, privacy requirements, context requirements, capabilities, cost, and availability.

### Tool System

Tools expose narrow, structured capabilities to models. Models request tools; backend code validates and executes them.

### Permission Engine

The permission engine deterministically decides whether an action is automatically allowed, logged, requires approval, or is blocked.

### Task Engine

The task engine stores and executes multi-step work. It allows tasks to pause for approval, recover after failure, and resume after application restarts.

### Desktop Client

A Tauri-based desktop application provides the primary Ubuntu interface to JLA.

### Web Client

A responsive web application will eventually provide lightweight access from iOS and other browsers.

## Design Principles

1. **Model-independent identity.** JLA must survive model and provider changes.
2. **No LLM is a security authority.** Models may propose actions but cannot authorize them.
3. **Least privilege.** Models receive narrow tools instead of unrestricted filesystem, database, or shell access.
4. **Deterministic enforcement.** Security, filesystem boundaries, and permission decisions are enforced in normal code.
5. **Local-first where practical.** Personal information and inexpensive processing should remain local when reasonable.
6. **Human-readable memory.** Important long-term memory should remain inspectable through Obsidian.
7. **Structured operational state.** Machine state belongs in SQLite rather than being forced into Markdown.
8. **Modularity.** Models, clients, integrations, and deployment environments should remain replaceable.
9. **Simple before sophisticated.** Basic retrieval and explicit rules should be proven before adding embeddings, autonomous behavior, or complicated infrastructure.
10. **Traceability.** Important memory changes and actions should be attributable to their source and recorded in activity logs.
11. **Failure must be safe.** Model errors, malformed tool calls, network failures, and application crashes must not silently create unsafe actions.
12. **One canonical source where possible.** Avoid unnecessary duplication of memories and configuration.

## Long-Term Deployment Vision

After the MVP is stable, the persistent JLA server should move to a Raspberry Pi 4B. The Pi should host the backend, SQLite state, assistant memory, retrieval services, permission engine, task engine, model routing, and eventually scheduled/background behavior.

Desktop and mobile applications should become clients of that server.

Conceptually:

```text
Desktop Client ─┐
                │
Web/iOS Client ─┼──> JLA Server ──> Memory / Tools / Models
                │
MCP Clients ────┘
```

The Raspberry Pi, desktop client, web client, and any particular LLM are implementation components. None of them individually define JLA's identity.
