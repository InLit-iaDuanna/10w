import React from 'react';
import type { AudioEditorState } from '../types';

type Props = { state: AudioEditorState; onRetry?: () => void };

const copy: Record<AudioEditorState['viewState'], string> = {
  loading: '正在读取音频任务与波形…',
  empty: '还没有音频任务。可从钥匙拾取或门解锁事件创建一个。',
  ready: '音频任务已就绪。映射发布前仍需 ChangeSet 批准。',
  failed: '音频分析失败；原始文件不会被修改。',
  offline: 'Unity 未连接；可分析并保存映射提案，但不能发布。',
  disabled: '音频工作室已被功能开关禁用。',
  'permission-denied': '你没有访问此音频工作室操作的权限。',
};

export default function AudioStudioEditor({ state, onRetry }: Props): React.ReactElement {
  const retryable = state.viewState === 'failed' || state.viewState === 'offline';
  return <section aria-label="音频工作室" data-execution-mode={state.mode}>
    <h2>音频工作室</h2>
    <p>{copy[state.viewState]}</p>
    <p>执行模式：{state.mode}</p>
    {state.selectedAssetId ? <p>音频资产：{state.selectedAssetId}</p> : null}
    {state.selectedEvent ? <p>事件：{state.selectedEvent}</p> : null}
    {state.viewState === 'ready' && state.analysis ? <section aria-label="音频分析">
      <h3>波形与格式</h3>
      <div aria-label="16 桶波形">{state.analysis.waveformPeaks.map((peak, index) => <meter key={index} min={0} max={1} value={peak} aria-label={`波形 ${index + 1}`} />)}</div>
      <p>{state.analysis.format} · {state.analysis.channels} 声道 · {state.analysis.sampleRateHz} Hz · {state.analysis.bitDepth}-bit · {state.analysis.durationSeconds} 秒</p>
      <p>峰值 {state.analysis.peakDbfs} dBFS；近似响度 {state.analysis.approximateLoudnessDbfs} dBFS</p>
      {state.analysis.warnings.length ? <ul>{state.analysis.warnings.map(warning => <li key={warning}>{warning}</li>)}</ul> : <p>未发现峰值或响度警告。</p>}
    </section> : null}
    {state.viewState === 'ready' && state.mapping ? <section aria-label="事件与 Unity 映射">
      <h3>事件绑定与 Unity 映射</h3>
      <p>事件：{state.mapping.gameplayEvent} → 资产：{state.mapping.audioAssetId}</p>
      <p>对象：{state.mapping.targetSceneopsId} · AudioSource：{state.mapping.audioSourceName} · Mixer：{state.mapping.mixerGroup}</p>
    </section> : null}
    {state.errorMessage ? <p role="alert">{state.errorMessage}</p> : null}
    {retryable ? <button type="button" onClick={onRetry}>重试</button> : null}
  </section>;
}
