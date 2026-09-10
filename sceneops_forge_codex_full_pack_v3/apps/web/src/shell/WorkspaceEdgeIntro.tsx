import { useEffect, useRef, useState } from 'react';
import { RegionPullHandles, type RegionSplitRequest } from './RegionPullHandles';
import './workspace-edge-intro.css';

const STORAGE_KEY = 'sceneops.workspace-edge-intro';
export function WorkspaceEdgeIntro({ instanceId, split, getBounds }: {
  instanceId: string; split: RegionSplitRequest; getBounds(): DOMRect;
}) {
  const [stage, setStage] = useState<'intro' | 'try' | 'done' | 'hidden'>(() => localStorage.getItem(STORAGE_KEY) ? 'hidden' : 'intro');
  const [phase, setPhase] = useState<'idle' | 'hover' | 'ready'>('idle');
  const primary = useRef<HTMLButtonElement>(null);
  useEffect(() => { if (stage === 'intro' || stage === 'done') primary.current?.focus(); }, [stage]);
  const dismiss = () => { localStorage.setItem(STORAGE_KEY, 'dismissed'); setStage('hidden'); };
  const complete = () => {
    if (stage !== 'try') return;
    localStorage.setItem(STORAGE_KEY, 'completed'); setStage('done');
  };
  return <>
    {stage !== 'intro' && stage !== 'done' && <RegionPullHandles instanceId={instanceId} split={split} getBounds={getBounds}
      onPhaseChange={setPhase} onPlaced={complete} />}
    {stage === 'intro' && <div className="edge-intro-shade" onKeyDown={event => {
      if (event.key === 'Escape') dismiss();
      if (event.key === 'Tab') {
        const buttons = event.currentTarget.querySelectorAll('button');
        if (event.shiftKey && event.target === buttons[0]) { event.preventDefault(); (buttons[buttons.length - 1] as HTMLButtonElement).focus(); }
        if (!event.shiftKey && event.target === buttons[buttons.length - 1]) { event.preventDefault(); (buttons[0] as HTMLButtonElement).focus(); }
      }
    }}>
      <section className="edge-intro-card" role="dialog" aria-modal="true" aria-labelledby="edge-intro-title">
        <span className="edge-intro-eyebrow">认识你的工作区</span>
        <h2 id="edge-intro-title">工具，藏在页面边缘</h2>
        <p>靠近左、右或下边缘，停一小会儿。卡片展开后，不用按住鼠标，移到合适位置再点击。</p>
        <div className="edge-intro-demo" role="img" aria-label="动画演示：鼠标靠近右边缘，停留后卡片变大，向内移动，点击形成工具分区">
          <div className="edge-demo-chat"><i/><i/><i/><span/></div>
          <div className="edge-demo-trigger"/>
          <div className="edge-demo-panel"><i/><i/><i/></div>
          <div className="edge-demo-card"><span/><span/></div>
          <div className="edge-demo-cursor"><svg viewBox="0 0 20 24"><path d="M2 2v17l5-5 4 8 3-2-4-7h7Z"/></svg><i/></div>
        </div>
        <ol className="edge-intro-steps"><li>靠近边缘</li><li>停留展开</li><li>移动，点击确认</li></ol>
        <footer><button onClick={dismiss}>跳过引导</button><button className="edge-intro-primary" ref={primary} onClick={() => setStage('try')}>我来试一试 →</button></footer>
      </section>
    </div>}
    {stage === 'try' && <>
      <div className="edge-intro-beacon is-left"/><div className="edge-intro-beacon is-right"/><div className="edge-intro-beacon is-bottom"/>
      <aside className="edge-intro-coach" aria-live="polite">
        <strong>{phase === 'ready' ? '现在移动鼠标，单击确认位置' : phase === 'hover' ? '对，就停在这里一小会儿' : '把鼠标移到页面左、右或下边缘'}</strong>
        <span>{phase === 'ready' ? '不需要按住鼠标 · Esc 可以取消重试' : '发光的边缘就是入口，试试右边 →'}</span>
        {phase !== 'ready' && <button onClick={dismiss}>跳过引导</button>}
      </aside>
    </>}
    {stage === 'done' && <aside className="edge-intro-coach is-done" role="status"><strong>就是这样，工具区已打开</strong><span>以后从左、右、下边缘唤出，选择工具就能继续工作。</span><button ref={primary} onClick={() => setStage('hidden')}>开始使用</button></aside>}
  </>;
}
