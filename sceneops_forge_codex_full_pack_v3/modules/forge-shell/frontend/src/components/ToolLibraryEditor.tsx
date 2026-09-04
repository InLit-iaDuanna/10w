import React from 'react';
import type { EditorHostProps } from '../contracts.ts';

export default function ToolLibraryEditor(props: EditorHostProps): React.ReactElement {
  if (props.suspended) return <section aria-label="工具库已暂停">工具库已暂停</section>;
  return (
    <section aria-label="工具库" data-state="ready">
      <h2>工具库</h2>
      <p>搜索已启用模块提供的编辑器，并选择标签、拆分、抽屉、浮动或弹出位置。</p>
    </section>
  );
}
