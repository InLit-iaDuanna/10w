import { createElement } from "react";
import { EditorSurface } from "./EditorSurface.ts";
import type { PlaytestEditorProps } from "../types.ts";
import { issueBrowserViewModel } from "../view-models.ts";

export default function IssueBrowserEditor(props: PlaytestEditorProps) {
  const issues = issueBrowserViewModel(props.readModel);
  return createElement(
    EditorSurface,
    { ...props, title: "问题浏览器" },
    createElement(
      "ul",
      null,
      ...issues.map((issue) =>
        createElement(
          "li",
          { key: issue.issueId, "data-severity": issue.severity },
          createElement("strong", null, issue.title),
          createElement(
            "p",
            null,
            `${issue.failureKind} · 回钉 ${issue.backpinStatus} (${Math.round(issue.backpinConfidence * 100)}%) · ${issue.backpinTargetId ?? "无唯一目标"}`,
          ),
          createElement(
            "ul",
            null,
            ...issue.backpinReasons.map((reason) =>
              createElement("li", { key: reason }, reason),
            ),
          ),
          issue.backpinAlternatives.length > 0
            ? createElement(
                "p",
                null,
                `备选：${issue.backpinAlternatives.join(", ")}`,
              )
            : null,
          createElement(
            "p",
            null,
            issue.backpinReviewedBy
              ? `审核人：${issue.backpinReviewedBy}`
              : "审核状态：待人工确认或拒绝",
          ),
          createElement(
            "ul",
            { "aria-label": "问题限制标签" },
            ...issue.limitationLabels.map((label) =>
              createElement("li", { key: label }, label),
            ),
          ),
          createElement(
            "button",
            {
              type: "button",
              disabled: !issue.canRestore,
              onClick: () => {
                props.updateLocalState({ selectedIssueId: issue.issueId });
                void props.commands.execute("playtest.issue.open-backpin", {
                  issueId: issue.issueId,
                });
              },
            },
            "恢复现场",
          ),
          createElement(
            "button",
            {
              type: "button",
              disabled: issue.backpinStatus !== "resolved" || Boolean(issue.backpinReviewedBy),
              onClick: () => props.commands.execute("playtest.issue.review-backpin", {
                issueId: issue.issueId,
                decision: "confirm",
              }),
            },
            "确认回钉",
          ),
          createElement(
            "button",
            {
              type: "button",
              disabled: issue.backpinStatus === "rejected" || Boolean(issue.backpinReviewedBy),
              onClick: () => props.commands.execute("playtest.issue.review-backpin", {
                issueId: issue.issueId,
                decision: "reject",
              }),
            },
            "拒绝回钉",
          ),
          createElement(
            "button",
            {
              type: "button",
              disabled: !issue.canProposeChange,
              onClick: () => props.commands.execute("playtest.changeset.propose", {
                issueId: issue.issueId,
              }),
            },
            "提出 ChangeSet",
          ),
        ),
      ),
    ),
  );
}
