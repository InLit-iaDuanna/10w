export const executionModes = [
  "live",
  "cached",
  "mock",
  "planned",
  "blocked",
] as const;

export type ExecutionMode = (typeof executionModes)[number];

export interface ExecutionModePresentation {
  label: "LIVE" | "CACHED" | "MOCK" | "PLANNED" | "BLOCKED";
  description: string;
  symbol: string;
}

const presentations: Record<ExecutionMode, ExecutionModePresentation> = {
  live: {
    label: "LIVE",
    description: "本次状态与结果来自真实服务请求",
    symbol: "●",
  },
  cached: {
    label: "CACHED",
    description: "来自之前真实执行的缓存结果",
    symbol: "◷",
  },
  mock: {
    label: "MOCK",
    description: "确定性本地测试数据",
    symbol: "⚗",
  },
  planned: {
    label: "PLANNED",
    description: "已规划但尚未执行",
    symbol: "◇",
  },
  blocked: {
    label: "BLOCKED",
    description: "当前无法执行，详情见失败原因",
    symbol: "!",
  },
};

export function isExecutionMode(value: unknown): value is ExecutionMode {
  return (
    typeof value === "string" &&
    (executionModes as readonly string[]).includes(value)
  );
}

export function presentExecutionMode(
  mode: ExecutionMode,
): ExecutionModePresentation {
  return presentations[mode];
}
