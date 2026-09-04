import { createElement, type ReactElement } from "react";

export interface GateView {
  gateId: string;
  label: string;
  status: "passed" | "failed" | "warning" | "not_run";
  blocking: boolean;
  message: string;
}

export default function AssetValidationEditor({ gates }: { gates: GateView[] }): ReactElement {
  if (!gates.length) {
    return createElement("p", { role: "status" }, "尚未运行质量检查");
  }
  return createElement(
    "ul",
    { "aria-label": "资产质量门禁" },
    gates.map((gate) =>
      createElement(
        "li",
        { key: gate.gateId, "data-status": gate.status },
        `${gate.label} · ${gate.status} · ${gate.blocking ? "阻断" : "提示"} · ${gate.message}`,
      ),
    ),
  );
}
