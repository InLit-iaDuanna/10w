# Conversation Home Module Rules

## Ownership

This module owns the `assistant.conversation` editor, conversation records, assistant-action validation, conversation fixtures, and the chat-only Home workspace fixture.

It does not own Dockview, edge-drawer mechanics, editor placement execution, project/feature creation, workflow execution, artifact/issue behavior, approvals, or external LLM implementations.

## Invariants

- Natural-language text never becomes a shell, file-system, or tool command.
- Structured assistant actions are validated and forwarded to the shared `WorkbenchCommandBus`; this module does not register a second command bus.
- Any assistant-proposed layout mutation is previewed and explicitly confirmed before execution.
- Command availability is rechecked immediately before execution, including permissions, integrations, and approvals.
- Unified project and pre-project conversations use isolated local SQLite scopes per the approved integration plan; the legacy editor retains its session-scoped adapter.
- Every run, message, and structured card displays `live`, `cached`, `mock`, `planned`, or `blocked` truthfully.
- UI copy and module documentation are Simplified Chinese; code and contract identifiers are English.

## Integration contracts

- Consume only the public core `WorkbenchCommandBus` and editor-registry contracts when they are available.
- The Forge Shell consumes the exported Home fixture and owns its four-edge affordances.
- LLM access is supplied through the typed `ConversationTransport` port.
- Do not import any other module's internal path.

## Generated files

Unified network types are generated from backend/export_unified_contracts.py and OpenAPI. Do not hand-edit generated network types or the global module catalog.

## Acceptance commands

Run from `modules/conversation-home/frontend`:

```text
npm test
```

After the core workspace lands, also run the repository's module-manifest validator, TypeScript checker, component suite, and catalog generator.

## Integrated lab update (2026-09-05)

The user requested a CodeBuddy CLI API and model selection. This module now owns that bounded text-only adapter and generated network types; it still never interprets text as executable tool commands. Do not bypass host permissions. Generated files: `frontend/src/generated/*`, `backend/src/conversation_home/generated_manifest.py`, and `contracts/codebuddy.openapi.json`. Only startup/import and one minimal local path are authorized; all broader commands above remain not run / pending approval.
