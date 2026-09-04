import type { EditorStateFrameProps, ExecutionMode } from '../types';
import './editor.css';

const modeLabels: Record<ExecutionMode, string> = {
  live: 'LIVE',
  cached: 'CACHED',
  mock: 'MOCK',
  planned: 'PLANNED',
  blocked: 'BLOCKED',
};

export default function EditorStateFrame<TData>({ title, state, children }: EditorStateFrameProps<TData>) {
  return (
    <section className="character-animation-editor" aria-label={title}>
      <header className="character-animation-editor__header">
        <h2>{title}</h2>
        <span className="character-animation-mode" data-mode={state.mode} aria-label={`执行模式：${modeLabels[state.mode]}`}>
          {modeLabels[state.mode]}
        </span>
      </header>
      <div className="character-animation-editor__body">{renderState(state, children)}</div>
    </section>
  );
}

function renderState<TData>(
  state: EditorStateFrameProps<TData>['state'],
  children: EditorStateFrameProps<TData>['children'],
) {
  if (state.kind === 'ready') return children(state.data);
  const classes = `character-animation-state character-animation-state--${state.kind}`;
  return (
    <div role={state.kind === 'failure' || state.kind === 'offline' ? 'alert' : 'status'}>
      <p className={classes}>{state.message ?? '正在加载角色与动画数据…'}</p>
      {'retry' in state && state.retry ? <button onClick={state.retry}>重试</button> : null}
    </div>
  );
}
