import type {
  CommandMetadata,
  ExistingProjectScanInput,
  NewProjectIntakeInput,
  ProjectIntakeCommandContext,
  ProjectRoot,
} from "../contracts.ts";
import type { ProjectScanHealth, ProjectScanReport } from "../adapters/ProjectScanAdapter.ts";

export const findMyWayHomeRoot: ProjectRoot = {
  rootId: "root_find_my_way_home",
  kind: "engine-project",
  absolutePath: "/fixtures/find-my-way-home",
  displayName: "Find My Way Home",
};

export const findMyWayHomeNewProject: NewProjectIntakeInput = {
  intakeId: "intake_find_my_way_home",
  projectId: "prj_find_my_way_home",
  projectName: "Find My Way Home",
  targetPlatforms: ["Windows", "macOS"],
  engine: { toolId: "unity", displayName: "Unity", version: "6000.0.40f1" },
  dccs: [{ toolId: "blender", displayName: "Blender", version: "4.3.2" }],
  projectRoots: [findMyWayHomeRoot],
  teamRoles: [
    {
      roleId: "role_game_designer",
      title: "游戏设计",
      responsibilities: ["功能规格", "验收标准"],
      assigneeId: "usr_designer",
    },
  ],
  styleGoals: [
    {
      goalId: "style_homecoming",
      dimension: "visual",
      statement: "温暖的归家感与清晰的路径引导",
      references: [],
    },
  ],
  performanceBudgets: [
    {
      budgetId: "budget_desktop_fps",
      platform: "Windows",
      metric: "frame_rate",
      limit: 60,
      unit: "fps",
      measurementContext: "1920x1080 gameplay build",
    },
  ],
  integrationRequirements: [
    {
      integrationId: "unity",
      capability: "scan-and-build",
      required: true,
      notes: "需要项目扫描、导入和构建能力。",
    },
  ],
  actorId: "usr_designer",
  occurredAt: "2026-09-04T01:00:00Z",
  mode: "mock",
};

export const warehouseEscapeRoot: ProjectRoot = {
  rootId: "root_warehouse_escape",
  kind: "engine-project",
  absolutePath: "/fixtures/warehouse-escape",
  displayName: "Warehouse Escape",
};

export const warehouseEscapeScanInput: ExistingProjectScanInput = {
  intakeId: "intake_warehouse_escape",
  projectId: "prj_warehouse_escape",
  projectRoot: warehouseEscapeRoot,
  adapterId: "fixture.unity-project-scan",
  actorId: "usr_producer",
  occurredAt: "2026-09-04T02:00:00Z",
};

export const warehouseEscapeScanHealth: ProjectScanHealth = {
  status: "online",
  checkedAt: "2026-09-04T02:00:00Z",
  message: "Fixture scanner ready.",
};

export const warehouseEscapeScanReport: ProjectScanReport = {
  adapterId: "fixture.unity-project-scan",
  adapterVersion: "0.1.0-fixture",
  scanId: "scan_warehouse_escape_001",
  scannedAt: "2026-09-04T02:00:01Z",
  mode: "mock",
  detected: {
    projectName: "Warehouse Escape",
    targetPlatforms: ["Windows"],
    engine: { toolId: "unity", displayName: "Unity", version: "2022.3.55f1" },
    dccs: [],
    integrationRequirements: [
      {
        integrationId: "unity",
        capability: "scan",
        required: true,
        notes: "由 fixture 扫描检测。",
      },
    ],
  },
  warnings: ["未发现团队角色与性能预算。"],
};

export const enabledProjectContext: ProjectIntakeCommandContext = {
  moduleEnabled: true,
  permissions: new Set(["project:read", "project:write", "project:scan"]),
};

export const fixtureCommandMetadata: CommandMetadata = {
  commandId: "cmd_project_intake_fixture_001",
  eventId: "evt_project_intake_fixture_001",
  correlationId: "corr_project_intake_fixture_001",
  actorId: "usr_designer",
  occurredAt: "2026-09-04T01:00:00Z",
};
