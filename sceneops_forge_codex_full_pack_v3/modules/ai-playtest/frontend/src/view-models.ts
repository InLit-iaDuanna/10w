import type { PlaytestReadModel } from "./types.ts";

export function gameViewModel(model: PlaytestReadModel) {
  return {
    screenshotUri: model.screenshotUri,
    camera: model.camera,
    buildId: model.buildId,
    hasFrame: Boolean(model.screenshotUri),
  };
}

export function agentMonitorViewModel(model: PlaytestReadModel) {
  const currentStep = model.steps.at(-1);
  return {
    runId: model.runId,
    status: model.status,
    objective: model.objective,
    agentMode: model.agentMode,
    actionBounds: model.actionBounds,
    currentAction: currentStep?.actionLabel,
    completedGoals: model.goals.filter((goal) => goal.state === "completed").length,
    goalCount: model.goals.length,
    goals: model.goals,
  };
}

export function trajectoryViewModel(model: PlaytestReadModel) {
  return model.steps.map((step) => ({
    stepIndex: step.stepIndex,
    position: step.position,
    outcome: step.outcome,
  }));
}

export function stepLogViewModel(model: PlaytestReadModel) {
  return model.steps.map((step) => ({
    stepIndex: step.stepIndex,
    action: step.actionLabel,
    occurredAt: step.occurredAt,
    target: step.targetSceneOpsId ?? "—",
    outcome: step.outcome,
    signals: step.signalKinds.join(", ") || "—",
    camera: step.camera,
    gameState: step.gameState,
    goals: step.goals,
    availableActionIds: step.availableActionIds,
    evidenceArtifactIds: step.evidenceArtifactIds,
  }));
}

export function issueBrowserViewModel(model: PlaytestReadModel) {
  return model.issues.map((issue) => ({
    ...issue,
    canRestore: true,
    canProposeChange:
      issue.backpinStatus === "resolved" && Boolean(issue.backpinReviewedBy),
  }));
}

export function regressionViewModel(model: PlaytestReadModel) {
  return {
    status: model.regressionStatus,
    exactConfiguration: model.exactConfiguration,
    baselineBuildId: model.baselineBuildId,
    candidateBuildId: model.candidateBuildId,
    newIssueIds: model.newIssueIds,
    resolvedIssueIds: model.resolvedIssueIds,
    persistentIssueIds: model.persistentIssueIds,
    metrics: model.regressionMetrics,
    improved: model.regressionMetrics.filter((item) => item.outcome === "improved").length,
    regressed: model.regressionMetrics.filter((item) => item.outcome === "regressed").length,
  };
}
