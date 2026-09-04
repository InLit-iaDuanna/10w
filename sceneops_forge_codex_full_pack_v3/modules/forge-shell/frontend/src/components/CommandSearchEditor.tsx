import React from 'react';
import type { EditorHostProps } from '../contracts.ts';

export default function CommandSearchEditor(props: EditorHostProps): React.ReactElement {
  return (
    <section aria-label="命令搜索" data-state={props.suspended ? 'disconnected' : 'ready'}>
      <label>
        命令搜索
        <input type="search" placeholder="输入命令或工具名称" disabled={props.suspended} />
      </label>
    </section>
  );
}
