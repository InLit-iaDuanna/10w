# Conversation Home Module Rules

## Ownership

This module owns the `assistant.conversation` editor, conversation records, assistant-action validation, conversation fixtures, and the chat-only Home workspace fixture.

It does not own Dockview, edge-drawer mechanics, editor placement execution, project/feature creation, workflow execution, artifact/issue behavior, approvals, or external LLM implementations.

## Invariants

- Natural-language text never becomes a shell, file-system, or tool command.
- Structured assistant actions are validated and forwarded to the shared `WorkbenchCommandBus`; this module does not register a second command bus.
- Any assistant-proposed layout mutation is previewed and explicitly confirmed before execution.
- Command availability is rechecked immediately before execution, including permissions, integrations, and approvals.
- Project conversations use project-persistent storage; pre-project conversations use session-scoped temporary storage.
- Every run, message, and structured card displays `live`, `cached`, `mock`, `planned`, or `blocked` truthfully.
- UI copy and module documentation are Simplified Chinese; code and contract identifiers are English.

## Integration contracts

- Consume only the public core `WorkbenchCommandBus` and editor-registry contracts when they are available.
- The Forge Shell consumes the exported Home fixture and owns its four-edge affordances.
- LLM access is supplied through the typed `ConversationTransport` port.
- Do not import any other module's internal path.

## Generated files

None in this module. Do not hand-edit a generated global module catalog when the module-runtime task is available.

## Acceptance commands

Run from `modules/conversation-home/frontend`:

```text
npm test
```

After the core workspace lands, also run the repository's module-manifest validator, TypeScript checker, component suite, and catalog generator.
