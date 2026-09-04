import type {
  ConversationFeatureDraftInput,
  DecisionRecord,
  DesignCommandContext,
  DesignCommandMetadata,
  FeatureSpec,
  GddDocument,
  ProjectBible,
} from "../contracts.ts";
import type { NewProjectIntakeInput } from "../../../../project-intake/frontend/src/index.ts";

export const findMyWayHomeIntakeForDesign: NewProjectIntakeInput = {
  intakeId: "intake_find_my_way_home",
  projectId: "prj_find_my_way_home",
  projectName: "Find My Way Home",
  targetPlatforms: ["Windows", "macOS"],
  projectRoots: [
    {
      rootId: "root_find_my_way_home",
      kind: "engine-project",
      absolutePath: "/fixtures/find-my-way-home",
      displayName: "Find My Way Home",
    },
  ],
  actorId: "usr_designer",
  occurredAt: "2026-09-04T01:00:00Z",
  mode: "mock",
};

export const findMyWayHomeBible: ProjectBible = {
  schemaVersion: 1,
  documentType: "project-bible",
  bibleId: "bible_find_my_way_home",
  projectId: "prj_find_my_way_home",
  sourceIntakeId: "intake_find_my_way_home",
  title: "Find My Way Home Project Bible",
  status: "approved",
  gameGoal: "让玩家通过观察环境、寻找关键物品并安全回到家。",
  targetPlayers: [
    {
      audienceId: "audience_exploration_players",
      description: "喜欢紧凑叙事探索的玩家",
      playerNeeds: ["清晰但不过度直白的引导", "可理解的交互反馈"],
    },
  ],
  coreLoop: [
    { stepId: "loop_observe", order: 1, action: "观察环境", feedback: "视觉与音频线索", playerValue: "形成路线假设" },
    { stepId: "loop_explore", order: 2, action: "探索路径", feedback: "发现关键物品", playerValue: "推进目标" },
    { stepId: "loop_unlock", order: 3, action: "解锁入口", feedback: "门打开并更新目标", playerValue: "获得归家感" },
  ],
  visualRules: [
    { id: "visual_warm_home", statement: "家的方向使用温暖琥珀色线索。", rationale: "强化归家身份。" },
  ],
  audioRules: [
    { id: "audio_confirm_actions", statement: "拾取和解锁必须有不同的确认音。", rationale: "避免只依赖视觉。" },
  ],
  interactionRules: [
    { id: "interaction_one_action", statement: "同一时刻只突出一个主要交互动作。", rationale: "降低歧义。" },
  ],
  namingRules: [
    { id: "naming_stable_ids", statement: "生产实体使用稳定英文 ID，显示名称可本地化。", rationale: "保持跨工具身份。" },
  ],
  platformBudgets: [
    { budgetId: "budget_fps_60", platform: "Windows", metric: "frame_rate", limit: 60, unit: "fps", measurementContext: "1920x1080 gameplay build" },
  ],
  prohibitedChanges: [
    { id: "prohibit_silent_unlock", statement: "不得让门在没有钥匙时自动打开。", scope: "key-door feature" },
  ],
  approvedDecisionIds: ["decision_key_visibility"],
  assumptions: [],
};

export const findMyWayHomeGdd: GddDocument = {
  schemaVersion: 1,
  documentType: "gdd",
  gddId: "gdd_find_my_way_home",
  projectId: "prj_find_my_way_home",
  title: "Find My Way Home GDD",
  status: "approved",
  executiveSummary: "一段通过环境线索、钥匙与家门完成的短篇归家体验。",
  designPillars: [
    { id: "pillar_readable", statement: "空间线索可读" },
    { id: "pillar_homecoming", statement: "回家具有情绪回报" },
  ],
  playerExperienceGoals: [{ id: "experience_discovery", statement: "玩家自行发现钥匙用途。" }],
  gameplaySystems: [
    {
      systemId: "system_key_door",
      name: "钥匙与门",
      purpose: "控制回家入口的解锁条件。",
      inputs: [{ id: "input_interact", statement: "玩家交互" }],
      outputs: [{ id: "output_door_state", statement: "门锁状态与任务进度" }],
      dependencyIds: ["system_inventory"],
      edgeCases: [{ id: "edge_repeat_interact", statement: "玩家重复使用已解锁门。" }],
    },
  ],
  progression: [{ id: "progress_home", statement: "发现钥匙 → 拾取 → 返回家门 → 解锁" }],
  worldStructure: [{ id: "world_branch", statement: "钥匙位于主路可见的短分支。" }],
  economyRules: [],
  failureRecovery: [{ id: "recovery_key", statement: "遗漏钥匙时提供逐步增强的环境线索。" }],
  dependencyIds: ["system_inventory"],
  assumptions: [],
};

export const keyDoorFeatureSpec: FeatureSpec = {
  schemaVersion: 1,
  documentType: "feature-spec",
  featureSpecId: "feature_key_door_branch",
  projectId: "prj_find_my_way_home",
  gddId: "gdd_find_my_way_home",
  title: "钥匙开门分支",
  status: "approved",
  goal: "玩家找到钥匙后才能打开家门并完成该目标。",
  playerValue: "发现、理解并完成归家路径。",
  inputs: [
    { id: "input_key_pickup", statement: "玩家拾取钥匙", source: "player" },
    { id: "input_door_interact", statement: "玩家与家门交互", source: "player" },
  ],
  outputs: [
    { id: "output_inventory", statement: "背包包含 home_key", consumer: "system" },
    { id: "output_door_open", statement: "家门进入 opened 状态", consumer: "player" },
  ],
  dependencies: [
    { dependencyId: "system_inventory", kind: "system", requiredState: "available" },
    { dependencyId: "decision_key_visibility", kind: "decision", requiredState: "decided" },
  ],
  edgeCases: [
    { id: "edge_door_without_key", statement: "没有钥匙时与门交互", expectedBehavior: "门保持锁定并给出明确反馈" },
    { id: "edge_pickup_twice", statement: "重复拾取钥匙", expectedBehavior: "保持单一库存条目且不重复触发任务" },
  ],
  acceptanceCriteria: [
    {
      criterionId: "ac_key_required",
      title: "钥匙是开门前置条件",
      given: "玩家未拾取 home_key",
      when: "玩家与家门交互",
      then: "门保持锁定并显示缺少钥匙的反馈",
      priority: "must",
    },
    {
      criterionId: "ac_door_opens",
      title: "持钥匙可开门",
      given: "玩家背包含 home_key",
      when: "玩家与家门交互",
      then: "门打开、播放音效并更新归家目标",
      priority: "must",
    },
  ],
  requiredDeliverables: [
    { requirementId: "req_asset_key", kind: "asset", description: "可识别的家门钥匙", existingArtifactId: null },
    { requirementId: "req_scene_key_branch", kind: "scene", description: "主路径旁的钥匙短分支", existingArtifactId: null },
    { requirementId: "req_script_lock", kind: "script", description: "背包、拾取与门锁状态逻辑", existingArtifactId: null },
    { requirementId: "req_ui_prompt", kind: "ui", description: "拾取与缺少钥匙提示", existingArtifactId: null },
    { requirementId: "req_audio_key_door", kind: "audio", description: "拾取、锁定与解锁音效", existingArtifactId: null },
    { requirementId: "req_vfx_door", kind: "vfx", description: "轻量解锁反馈", existingArtifactId: null },
  ],
  requiredTests: [
    { testId: "test_key_door_happy", level: "playtest", description: "拾取钥匙并打开家门", linkedCriterionIds: ["ac_door_opens"] },
    { testId: "test_key_door_locked", level: "integration", description: "无钥匙时门保持锁定", linkedCriterionIds: ["ac_key_required"] },
  ],
  assumptions: [],
};

export const keyDoorConversationDraft: ConversationFeatureDraftInput = {
  ...keyDoorFeatureSpec,
  inferredStatements: [
    { id: "assumption_key_location", statement: "钥匙放在入口左侧分支可获得最佳可见性。" },
  ],
  sourceMessageId: "msg_add_key_branch_001",
};

export const keyVisibilityDecision: DecisionRecord = {
  decisionId: "decision_key_visibility",
  projectId: "prj_find_my_way_home",
  subject: "如何让玩家发现钥匙",
  status: "open",
  alternatives: [
    { alternativeId: "alt_emissive", title: "轻微自发光", consequences: ["高可见性", "可能破坏写实感"], disposition: "pending", rationale: null },
    { alternativeId: "alt_warm_light", title: "暖光构图引导", consequences: ["符合视觉规则", "需要灯光调优"], disposition: "pending", rationale: null },
  ],
  decidedBy: null,
  decidedAt: null,
};

export const warehouseEscapeFeatureSpec: FeatureSpec = {
  schemaVersion: 1,
  documentType: "feature-spec",
  featureSpecId: "feature_switch_exit",
  projectId: "prj_warehouse_escape",
  gddId: null,
  title: "仓库开关与出口",
  status: "draft",
  goal: "玩家触发开关、避开障碍并到达出口。",
  playerValue: "理解空间因果关系并完成逃脱。",
  inputs: [{ id: "input_switch", statement: "玩家触发墙面开关", source: "player" }],
  outputs: [{ id: "output_exit_open", statement: "出口门解锁", consumer: "player" }],
  dependencies: [{ dependencyId: "system_navigation", kind: "system", requiredState: "available" }],
  edgeCases: [{ id: "edge_blocked_path", statement: "障碍使目标不可达", expectedBehavior: "测试失败并回指障碍碰撞体" }],
  acceptanceCriteria: [{ criterionId: "ac_exit", title: "开关解锁出口", given: "出口门锁定", when: "玩家触发开关", then: "出口门解锁且路径可达", priority: "must" }],
  requiredDeliverables: [
    { requirementId: "req_switch_asset", kind: "asset", description: "墙面开关", existingArtifactId: null },
    { requirementId: "req_warehouse_scene", kind: "scene", description: "仓库障碍与出口", existingArtifactId: null },
    { requirementId: "req_switch_logic", kind: "script", description: "开关到门的状态连接", existingArtifactId: null },
  ],
  requiredTests: [{ testId: "test_warehouse_exit", level: "playtest", description: "触发开关并抵达出口", linkedCriterionIds: ["ac_exit"] }],
  assumptions: [],
};

export const enabledDesignContext: DesignCommandContext = {
  moduleEnabled: true,
  permissions: new Set(["design:read", "design:write", "design:approve"]),
};

export const designFixtureMetadata: DesignCommandMetadata = {
  commandId: "cmd_design_fixture_001",
  eventId: "evt_design_fixture_001",
  correlationId: "corr_design_fixture_001",
  actorId: "usr_designer",
  actorType: "user",
  occurredAt: "2026-09-04T04:00:00Z",
  mode: "mock",
};
