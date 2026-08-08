# JLA Security Model

## 1. Core Rule

**No LLM is trusted as a security authority.**

Language models are probabilistic components. They may reason about what should happen, but deterministic JLA backend code decides what is actually permitted and executed.

## 2. What Models May Do

Models may:

- Interpret user requests.
- Reason.
- Summarize.
- Classify tasks.
- Propose plans.
- Request tools.
- Propose memory changes.
- Generate arguments for structured tool calls.
- Explain completed actions.

## 3. What Models May Not Do

Models may not independently:

- Grant permissions.
- Change their own permission level.
- Change tool security classifications.
- Bypass the permission engine.
- Access arbitrary filesystem paths.
- Execute arbitrary shell commands unless a deliberately restricted tool is added later.
- Access secrets.
- Declare a tool operation successful without backend confirmation.
- Change security policy.
- Expand their own tool access.

## 4. Permission Enforcement

Every model-accessible tool must have a permission policy enforced by backend code.

Initial conceptual levels:

### Level 0: Safe Automatic Operation

Typical use:

- Reading approved assistant memory.
- Searching approved memory indexes.

No user approval is required.

### Level 1: Automatic but Logged Operation

Typical use:

- Low-risk changes to JLA-owned operational state.
- Approved forms of assistant-memory maintenance.

The action is executed automatically but recorded.

### Level 2: User Approval Required

Typical use:

- Editing user-owned notes.
- Creating or modifying external resources.
- Actions with meaningful side effects.

The backend must pause execution until approval is received.

### Level 3: Restricted

Typical use:

- Destructive actions.
- Broad shell or filesystem capabilities.
- Security-sensitive configuration changes.

These capabilities are disabled by default and may require stronger safeguards if ever implemented.

## 5. Filesystem Boundaries

Filesystem access must use validated paths and explicitly configured roots.

### Assistant Vault

Initial policy:

```text
Read:  allowed
Write: allowed only through defined memory tools/policies
```

### Personal Vault

Initial policy:

```text
Read:  allowed through approved retrieval/read tools
Write: disabled during early development
```

Future personal-vault writes must use narrowly scoped tools and appropriate approval.

### Outside Approved Roots

```text
Direct model access: denied
```

Backend services should reject path traversal and attempts to escape configured roots.

Examples that must be handled safely include:

```text
../../etc/passwd
/home/user/PersonalVault/../../.ssh/
symlink-based escapes
unexpected absolute paths
```

## 6. Tool Security

Models should receive semantic tools rather than general-purpose machine access.

Prefer:

```text
read_personal_note(note_id)
update_assistant_memory(memory_id, change)
create_calendar_event(...)
```

Avoid exposing capabilities such as:

```text
open_any_file(path)
run_any_command(command)
execute_python(code)
```

unless a future use case justifies them and strong isolation is added.

## 7. Structured Input Validation

Model-generated tool calls and structured outputs are untrusted input.

They must be validated before execution using explicit schemas.

Validation should cover:

- Required fields.
- Types.
- Allowed enum values.
- Path boundaries.
- String length where relevant.
- Resource identifiers.
- Permission requirements.
- Tool availability.

Malformed requests should fail closed.

## 8. Secrets

Secrets include API keys, authentication tokens, encryption keys, session secrets, and external-service credentials.

Secrets must never be:

- Committed to Git.
- Stored in Obsidian memory.
- Included in normal model context.
- Printed in normal logs.
- Returned through memory/search tools.

During development, secrets may be stored in:

```text
src/server/.env
```

The file must be ignored by Git.

Long-term deployment may use stronger secret storage appropriate to the operating system and Raspberry Pi environment.

## 9. Logging

JLA should log enough information to audit actions without leaking secrets.

Useful activity records include:

- Request identifier.
- Selected model.
- Routing reason.
- Retrieved memory identifiers.
- Tool requested.
- Permission level.
- Approval/rejection result.
- Tool execution result.
- Error information.
- Task state transitions.

Logs should avoid storing credentials or unnecessary sensitive content.

## 10. Approval Integrity

Approval must be associated with the specific proposed action or an explicitly defined scope.

A model must not be able to request approval for one action and then use that approval for a materially different action.

Approval records should eventually include:

- Action/tool.
- Arguments or normalized action summary.
- Target resource.
- Time.
- User decision.
- Approval scope.

## 11. Multi-Step Tasks

Each step of a multi-step task must independently pass normal tool and permission validation.

A user's approval to begin a task does not automatically imply approval for every possible side effect unless the UI explicitly presents and grants a broader scope.

## 12. Model Routing Security

The model router must respect privacy and security constraints.

A local classifier may recommend a model, but deterministic policy decides whether data is permitted to leave the local machine.

A cloud model must never receive context marked local-only.

## 13. Personal Data Minimization

The context builder should send models only information reasonably needed for the task.

JLA should not send an entire personal vault to a cloud model merely because the model has a large context window.

Retrieval and context construction should minimize unnecessary disclosure.

## 14. Memory Integrity

Long-term memory must not blindly accept every model-generated statement as fact.

Memory writes should eventually support:

- Provenance.
- Confidence.
- Source references.
- Duplicate detection.
- Contradiction detection.
- Canonical-note updates.

The model may propose a memory; the memory subsystem decides how it is stored.

## 15. External Integrations

Every external integration must enter JLA through a defined service and tool boundary.

Examples include:

- Google Calendar.
- Google Docs.
- Gmail.
- Git.
- Web access.
- Filesystem actions.

Adding an integration must not bypass the existing permission architecture.

## 16. Network Security

During local development, the server should not be exposed publicly without a deliberate reason.

When JLA moves to the Raspberry Pi and supports remote/mobile access, authentication and encrypted transport must be implemented before exposing sensitive endpoints outside the trusted local environment.

## 17. MCP Security

A future MCP server must expose only deliberately selected JLA services.

MCP must not provide direct unrestricted access to:

- The filesystem.
- SQLite.
- Shell execution.
- Secrets.
- Internal permission configuration.

MCP calls must pass through the same service and permission layers as requests from JLA's own clients.

## 18. Failure Policy

When JLA cannot determine whether an operation is permitted, it should not execute the operation.

When validation fails, execution stops.

When approval is required but unavailable, the task pauses.

When a model claims an action succeeded but no successful tool result exists, JLA treats the action as not completed.

## 19. Security Invariants

These rules should remain true throughout development:

1. Models cannot grant themselves authority.
2. Secrets do not enter model context by default.
3. Model-generated structured data is validated.
4. Filesystem operations remain inside explicit roots.
5. Sensitive actions pass through the permission engine.
6. External integrations cannot bypass JLA security.
7. Tool execution results, not model prose, determine whether actions occurred.
8. Unknown or malformed actions fail closed.
9. Security behavior is testable with deterministic automated tests.
