import { createElement as h, type ReactElement } from "react";

import type { ConceptEditorProps, StyleBiblePresentation } from "../types.ts";
import { styleAssessmentText } from "./presentation.ts";
import "./concept-lab.css";


export default function StyleBibleEditor(
  props: ConceptEditorProps<StyleBiblePresentation>,
): ReactElement {
  const { availability } = props.presentation;
  if (availability.kind !== "ready") {
    const message = availability.kind === "loading" ? "正在加载风格圣经…" : availability.message;
    return h(
      "section",
      { className: `concept-lab concept-lab--state state-${availability.kind}` },
      h("p", null, message),
      availability.kind === "failed"
        ? h(
            "button",
            {
              type: "button",
              onClick: () => props.commands.execute(availability.retryCommandId, {
                conceptId: props.presentation.conceptId,
              }),
            },
            "重试",
          )
        : null,
    );
  }
  return h(
    "section",
    { className: "concept-lab", "aria-label": "风格圣经" },
    h(
      "header",
      { className: "concept-lab__header" },
      h("h2", null, "风格圣经"),
      h("span", null, `Project Bible · ${props.presentation.projectBibleVersionId}`),
    ),
    h("p", { className: "concept-lab__subjective" }, props.presentation.subjectiveNotice),
    h("h3", null, "必须保持"),
    h("ul", null, ...props.presentation.styleConstraints.map((value) => h("li", { key: value }, value))),
    h("h3", null, "禁止元素"),
    props.presentation.forbiddenElements.length
      ? h("ul", null, ...props.presentation.forbiddenElements.map((value) => h("li", { key: value }, value)))
      : h("p", { className: "concept-lab__empty" }, "未声明禁止元素"),
    h(
      "div",
      { className: "concept-lab__assessment" },
      h("strong", null, styleAssessmentText(props.presentation)),
      props.presentation.evidenceCoverage === null
        ? null
        : h("span", null, `证据覆盖 ${Math.round(props.presentation.evidenceCoverage * 100)}%`),
    ),
    h(
      "button",
      {
        type: "button",
        onClick: () => props.commands.execute("concept.style.check", {
          conceptId: props.presentation.conceptId,
        }),
      },
      "提交风格证据",
    ),
  );
}
