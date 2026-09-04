import { createElement as h, type ReactElement } from "react";

import type { ConceptEditorProps, MoodboardPresentation } from "../types.ts";
import { moodboardNotice } from "./presentation.ts";
import "./concept-lab.css";


export default function MoodboardEditor(
  props: ConceptEditorProps<MoodboardPresentation>,
): ReactElement {
  const { availability } = props.presentation;
  if (availability.kind !== "ready") {
    return renderAvailability(availability, props);
  }

  const visibleItems = props.presentation.items.filter(
    (item) => props.localState.showRejected || item.decision !== "rejected",
  );
  return h(
    "section",
    { className: "concept-lab", "aria-label": "概念情绪板" },
    h(
      "header",
      { className: "concept-lab__header" },
      h("div", null, h("h2", null, props.presentation.subject ?? "未命名概念")),
      h("span", { className: `concept-lab__mode mode-${props.presentation.executionMode}` }, props.presentation.executionMode.toUpperCase()),
    ),
    moodboardNotice(props.presentation)
      ? h("p", { className: "concept-lab__notice" }, moodboardNotice(props.presentation))
      : null,
    h(
      "div",
      { className: "concept-lab__toolbar" },
      h(
        "button",
        {
          type: "button",
          onClick: () => props.commands.execute("concept.reference.import", {
            conceptId: props.presentation.conceptId,
          }),
        },
        "导入参考图",
      ),
      h(
        "button",
        {
          type: "button",
          onClick: () => props.commands.execute("concept.variant.generate", {
            conceptId: props.presentation.conceptId,
          }),
        },
        "请求生成变体",
      ),
      h(
        "button",
        {
          type: "button",
          disabled: props.localState.selectedVariantIds.length < 2,
          onClick: () => props.commands.execute("concept.variant.compare", {
            conceptId: props.presentation.conceptId,
            variantIds: props.localState.selectedVariantIds,
          }),
        },
        "比较所选",
      ),
    ),
    visibleItems.length
      ? h(
          "ul",
          { className: "concept-lab__grid" },
          ...visibleItems.map((item) =>
            h(
              "li",
              { key: item.id, className: "concept-lab__item" },
              item.thumbnailUrl
                ? h("img", {
                    className: "concept-lab__preview",
                    src: item.thumbnailUrl,
                    alt: `${item.title} · ${item.view}`,
                  })
                : h("div", { className: "concept-lab__preview", "aria-hidden": true }, item.view),
              h("strong", null, item.title),
              h("span", null, `${item.executionMode.toUpperCase()} · ${item.permissionStatus}`),
              h("span", null, `评审：${item.decision}`),
              h(
                "label",
                null,
                h("input", {
                  type: "checkbox",
                  checked: props.localState.selectedVariantIds.includes(item.id),
                  onChange: () => toggleVariant(props, item.id),
                }),
                "加入比较",
              ),
              h(
                "div",
                { className: "concept-lab__item-actions" },
                h(
                  "button",
                  {
                    type: "button",
                    onClick: () => props.commands.execute("concept.variant.comment", {
                      conceptId: props.presentation.conceptId,
                      variantId: item.id,
                    }),
                  },
                  "评论",
                ),
                h(
                  "button",
                  {
                    type: "button",
                    disabled: item.decision !== "proposed",
                    onClick: () => props.commands.execute("concept.variant.review", {
                      conceptId: props.presentation.conceptId,
                      variantId: item.id,
                      action: "approve",
                    }),
                  },
                  "批准",
                ),
                h(
                  "button",
                  {
                    type: "button",
                    disabled: item.decision !== "proposed",
                    onClick: () => props.commands.execute("concept.variant.review", {
                      conceptId: props.presentation.conceptId,
                      variantId: item.id,
                      action: "reject",
                    }),
                  },
                  "拒绝",
                ),
              ),
            ),
          ),
        )
      : h("p", { className: "concept-lab__empty" }, "还没有参考图。可以导入已有概念，无需图像生成集成。"),
  );
}


function toggleVariant(
  props: ConceptEditorProps<MoodboardPresentation>,
  variantId: string,
): void {
  const selected = props.localState.selectedVariantIds;
  props.updateLocalState({
    selectedVariantIds: selected.includes(variantId)
      ? selected.filter((value) => value !== variantId)
      : [...selected, variantId],
  });
}


function renderAvailability(
  availability: Exclude<MoodboardPresentation["availability"], { kind: "ready" }>,
  props: ConceptEditorProps<MoodboardPresentation>,
): ReactElement {
  if (availability.kind === "loading") {
    return h("section", { className: "concept-lab concept-lab--state" }, "正在加载概念…");
  }
  const commandId =
    availability.kind === "failed"
      ? availability.retryCommandId
      : availability.kind === "offline"
        ? availability.importCommandId
        : null;
  return h(
    "section",
    { className: `concept-lab concept-lab--state state-${availability.kind}` },
    h("p", null, availability.message),
    commandId
      ? h(
          "button",
          {
            type: "button",
            onClick: () => props.commands.execute(commandId, {
              conceptId: props.presentation.conceptId,
            }),
          },
          availability.kind === "offline" ? "改为导入概念" : "重试",
        )
      : null,
  );
}
