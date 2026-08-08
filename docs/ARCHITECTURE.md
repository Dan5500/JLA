# JLA Architecture

## 1. System Overview

JLA is a model-independent personal assistant composed of persistent backend services and replaceable interfaces and reasoning models.

```text
                    User
                     │
          ┌──────────┼──────────┐
          │          │          │
         CLI      Desktop      Web
          │          │          │
          └──────────┼──────────┘
                     │
                  FastAPI
                     │
                  JLA Core
                     │
      ┌──────────────┼──────────────┐
      │              │              │
   Memory         Task/Tool       Model
   System          System         System
      │              │              │
 Obsidian +       Permissions     Router
 SQLite                │              │
                       │       ┌──────┼──────┐
                       │       │      │      │
                       │    Ollama  OpenAI  Anthropic
                       │
                 Integrations
```

## 2. Repository Structure

Target structure:

```text
JLA/
├── src/
│   ├── server/
│   │   ├── jla/
│   │   │   ├── core/
│   │   │   ├── memory/
│   │   │   ├── retrieval/
│   │   │   ├── models/
│   │   │   ├── tools/
│   │   │   ├── permissions/
│   │   │   ├── database/
│   │   │   ├── tasks/
│   │   │   ├── api/
│   │   │   └── integrations/
│   │   ├── config/
│   │   ├── tests/
│   │   └── .env
│   ├── desktop/
│   └── web/
├── docs/
├── scripts/
├── infrastructure/
└── README.md
```

Not every directory needs to exist during Phase 0. Directories should be introduced when their corresponding subsystem is implemented.

## 3. JLA Core

JLA Core coordinates the assistant independently of any user interface or model provider.

Its responsibilities eventually include:

- Receiving normalized user requests.
- Maintaining conversation and task state.
- Retrieving relevant context.
- Building model context packages.
- Classifying tasks.
- Selecting models.
- Managing the agent/tool loop.
- Enforcing permission checks before execution.
- Updating memory when appropriate.
- Recording activity and failures.

The UI must not contain core assistant logic.

## 4. Memory Architecture

JLA uses multiple forms of state rather than treating all information as one giant prompt.

### Assistant Obsidian Vault

The assistant vault contains durable, human-readable memory such as:

- Identity and preferences.
- People and relationships.
- Experiences.
- Knowledge.
- Projects.
- Goals.
- Decisions.
- Ideas.
- Current focus.
- Session summaries.
- Memory-management records.

JLA may eventually write to this vault according to the memory and permission policies.

### Personal Obsidian Vault

The personal vault is controlled by the user. JLA may retrieve approved information from it.

The personal vault should initially be treated as read-only by JLA. Future writes must pass through explicit tools and the permission engine.

### SQLite

SQLite stores operational state that benefits from strict schemas and efficient queries, including:

- Conversations.
- Messages.
- Tool calls.
- Tasks.
- Task steps.
- Approvals.
- Retrieval/index metadata.
- Model usage.
- Activity records.

## 5. Retrieval Architecture

Retrieval determines what existing information should enter the model context.

Initial retrieval should remain simple and inspectable:

1. Discover Markdown files.
2. Parse titles, headings, frontmatter, and Obsidian links.
3. Split notes into heading-aware chunks.
4. Index chunk metadata in SQLite.
5. Search by filename, title, keyword, metadata, and links.
6. Rank candidate chunks.
7. Pass only relevant chunks to the context builder.

Advanced semantic retrieval, embeddings, reranking, and graph-aware ranking are post-MVP improvements.

## 6. Model Architecture

JLA models are replaceable reasoning engines.

Every provider should implement a common internal interface so that JLA Core does not depend directly on provider-specific APIs.

Conceptually:

```text
ModelProvider
├── OllamaProvider
├── OpenAIProvider
└── AnthropicProvider
```

Provider-specific request and response formats should be normalized at the adapter boundary.

## 7. Model Routing

Routing should use structured task information rather than arbitrary model choice.

Potential routing factors include:

- Task type.
- Complexity.
- Privacy requirements.
- Tool requirements.
- Context size.
- Required reasoning quality.
- Required modality.
- Latency.
- Cost.
- Provider availability.

A local model may assist with classification, but deterministic Python configuration retains final routing authority.

Example:

```text
Simple summary -> local fast model
Complex architecture -> cloud reasoning model
Local-only/private task -> best permitted local model
Provider failure -> configured fallback
```

## 8. Context Builder

The context builder constructs the information given to the selected model.

A model call may receive:

```text
JLA identity and behavioral policy
+
Task-specific instructions
+
Conversation context
+
Relevant retrieved memories
+
Current project/task state
+
Available tool definitions
+
Permission constraints
```

The context builder should not blindly load the entire memory vault.

## 9. Tool Architecture

Models never directly execute Python functions, modify files, or call external services.

Instead:

```text
Model
  │
  └── requests structured tool call
          │
          v
     Tool Registry
          │
          v
   Permission Engine
          │
     allowed/approved?
          │
          v
      Tool Handler
          │
          v
       Result
          │
          v
        Model
```

Model-facing tools should be narrow and semantic. Prefer:

```text
update_assistant_memory(...)
```

over:

```text
write_arbitrary_file(path, ...)
```

## 10. Permission Architecture

Permission enforcement is deterministic and occurs outside the LLM.

Initial conceptual levels:

```text
Level 0: automatic safe/read operation
Level 1: automatic but logged operation
Level 2: explicit user approval required
Level 3: restricted/disabled by default
```

The exact level definitions may evolve, but models must never be able to grant themselves permission or change the policy governing a tool.

## 11. Agent Loop

JLA should support iterative model/tool interaction rather than assuming every task can be completed in one model response.

```text
User request
    ↓
Context + selected model
    ↓
Model reasoning
    ↓
Tool request?
 ┌──┴──┐
No    Yes
│      ↓
│   Validate
│      ↓
│   Permission
│      ↓
│   Execute
│      ↓
│   Tool result
│      ↓
│   Model continues
│      │
└──────┘
    ↓
Final response
```

## 12. Multi-Step Task Execution

JLA, not the model, owns persistent task state.

A model may propose a plan, but JLA records and validates it.

Example task state:

```text
Task 42
status: waiting_for_approval

1. Retrieve project context    COMPLETE
2. Find target document        COMPLETE
3. Edit target document        WAITING_FOR_APPROVAL
4. Create reminder             PENDING
5. Summarize work              PENDING
```

This allows tasks to survive approval delays, failures, process restarts, and model changes.

## 13. Memory Writing

Memory writing should be a controlled pipeline rather than unrestricted transcript storage.

```text
Conversation / event
        ↓
Memory extraction
        ↓
Structured proposal
        ↓
Validation
        ↓
Duplicate / contradiction checks
        ↓
Permission policy
        ↓
Canonical memory update
        ↓
Retrieval index refresh
```

Durable memories should include provenance where practical.

## 14. FastAPI Boundary

FastAPI will expose JLA Core as a network service.

Potential endpoints include:

```text
POST /chat
GET  /tasks/{id}
POST /tasks/{id}/approve
GET  /memory/search
GET  /projects
GET  /models
GET  /activity
```

The CLI, desktop client, and web client should ultimately communicate through this boundary instead of importing JLA internals directly.

## 15. Desktop Architecture

The desktop client will use Tauri with a web-based frontend such as React/TypeScript.

Tauri does not make JLA a web application. It packages a native desktop application whose interface uses web technologies.

The desktop client should primarily handle:

- Chat presentation.
- Streaming output.
- Approval prompts.
- Task status.
- Memory/activity inspection.
- Settings.
- Connection state.

It should not own JLA's persistent intelligence.

## 16. Web Architecture

The web client will provide a lightweight mobile-compatible interface, particularly for iOS.

It should use the same FastAPI backend and expose only appropriate functionality over authenticated connections.

## 17. Raspberry Pi Deployment

Post-MVP, the Raspberry Pi 4B should become the always-on JLA host.

Expected Pi-hosted components:

- JLA Core.
- FastAPI.
- SQLite.
- Assistant memory vault.
- Retrieval index.
- Permission engine.
- Task engine.
- Model router.
- Scheduler/background services.
- Eventually MCP.

The Raspberry Pi may retain Raspberry Pi OS and its desktop packages while normally booting/running headlessly.

## 18. MCP Architecture

MCP is an optional standardized adapter, not a foundational dependency.

JLA's services should work without MCP.

Later:

```text
External MCP Client
        ↓
    MCP Adapter
        ↓
Existing JLA Services
        ↓
Permission Engine
```

This allows compatible external AI clients to use selected JLA capabilities without duplicating the underlying implementation.

## 19. Configuration

Server configuration belongs under the server component.

Example:

```text
src/server/config/
├── app.yaml
├── vaults.yaml
├── models.yaml
└── permissions.yaml
```

Secrets belong in an ignored environment file during development:

```text
src/server/.env
```

Secrets must not be committed to Git.

## 20. Architectural Invariants

The following should remain true as JLA evolves:

1. JLA's identity is independent of any model.
2. Models cannot authorize their own actions.
3. Models do not receive unrestricted filesystem access.
4. Persistent memory remains independently accessible from model providers.
5. UI clients do not own core assistant logic.
6. Core services should be reusable by FastAPI, future MCP adapters, and other interfaces.
7. Sensitive actions pass through the permission engine.
8. Tool success is determined by backend execution, not by model claims.
9. Model output is treated as untrusted structured input whenever it controls application behavior.
10. The system should fail safely when uncertain.
