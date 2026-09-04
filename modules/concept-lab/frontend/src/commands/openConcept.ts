export interface ConceptOpenInput {
  conceptId: string;
  projectId: string;
  taskId?: string;
  source: "chat" | "task_link" | "tool_library";
  placement?: "tab" | "split" | "floating" | "drawer";
}

export interface OpenEditorAction {
  type: "workbench.open_editor";
  editorId: "concept.moodboard";
  placement: {
    mode: "tab" | "split" | "floating" | "drawer";
    direction?: "right";
    edge?: "left";
  };
  context: {
    projectId: string;
    activeTaskId: string | null;
    conceptId: string;
  };
  requireConfirmation: true;
}

export function openConcept(input: ConceptOpenInput): OpenEditorAction {
  const mode = input.placement ?? "split";
  return {
    type: "workbench.open_editor",
    editorId: "concept.moodboard",
    placement: {
      mode,
      ...(mode === "split" ? { direction: "right" as const } : {}),
      ...(mode === "drawer" ? { edge: "left" as const } : {}),
    },
    context: {
      projectId: input.projectId,
      activeTaskId: input.taskId ?? null,
      conceptId: input.conceptId,
    },
    requireConfirmation: true,
  };
}
