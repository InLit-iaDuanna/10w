import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import type { components } from '../lab-api';
type S = components['schemas'];

function readAudio(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('无法读取音频，请重新选择文件。'));
    reader.onload = () => resolve(String(reader.result));
    reader.readAsDataURL(file);
  });
}

export function AudioLabPanel({ template, event, mixer: initialMixer, api, onProposal, allowSample = true, onMixerChange }: {
  template: 'home' | 'warehouse'; event: string; mixer: string; onProposal: () => void; allowSample?: boolean; onMixerChange?: (value: string) => void;
  api: { fixture: () => Promise<S['DemoAudio']>; inspectFixture: () => Promise<S['Inspection']>;
    inspect: (upload: S['Upload']) => Promise<S['Inspection']>;
    propose: (draft: S['BindingDraft']) => Promise<S['Proposal']> };
}) {
  const [mixer, setMixer] = useState(initialMixer);
  const [source, setSource] = useState('');
  const inspection = useMutation({ mutationFn: async (file?: File) => {
    if (file) {
      if (file.size > 4 * 1024 * 1024) throw new Error('本地演示支持最多 4 MiB 的 WAV 文件。');
      const dataUrl = await readAudio(file);
      const result = await api.inspect({ filename: file.name, data: dataUrl.split(',')[1] });
      setSource(dataUrl);
      return result;
    }
    const [audio, result] = await Promise.all([api.fixture(), api.inspectFixture()]);
    setSource(`data:audio/wav;base64,${audio.data}`);
    return result;
  } });
  const proposal = useMutation({ mutationFn: api.propose, onSuccess: onProposal });
  const analysis = inspection.data?.analysis;
  const busy = inspection.isPending || proposal.isPending;
  const load = (file?: File) => { inspection.reset(); proposal.reset(); setSource(''); inspection.mutate(file); };
  return <div className="module-grid"><div className="editor-main">
    <div className="section-heading"><h2>音频检视</h2><span className={`badge ${inspection.data?.mode || 'planned'}`}>{inspection.data?.mode || 'planned'} · {inspection.data ? '已分析' : '等待素材'}</span></div>
    <div className="audio-drop"><span className="large-symbol" aria-hidden="true">♫</span><h3>从一段声音开始</h3>
      <p>选择本机 PCM WAV，或加载内置确定性测试信号。</p>
      <div className="actions"><label className="file-button">选择 WAV 文件<input aria-label="选择 WAV 文件" type="file" accept=".wav,audio/wav" disabled={busy} onChange={e => { const file = e.target.files?.[0]; if (file) load(file); e.target.value = ''; }} /></label>
        {allowSample && <button disabled={busy} onClick={() => load()}>{inspection.isPending ? '分析中…' : '加载并分析演示音频'}</button>}</div>
      <small>16-bit PCM · 单 / 双声道 · ≤ 4 MiB · 不上传第三方服务</small>
    </div>
    {analysis && <><div className="section-heading"><h3>{inspection.data!.filename}</h3><small>振幅包络 · 16 个区间</small></div>
      <svg className="waveform" viewBox="0 0 640 150" role="img" aria-label="音频振幅包络">
        <path d="M0 75H640" stroke="#455050" />{analysis.waveform_peaks.map((peak, i) => <rect key={i} x={i * 40 + 7} y={75 - peak * 68} width="26" height={Math.max(1, peak * 136)} rx="3" fill="#58c8c5" />)}
      </svg><audio controls src={source} ref={element => { if (element) element.volume = .15; }} />
      <p className="muted">演示文件是测试信号，不是生产音效。默认低音量，请按需试听。</p>
      <div className="metrics"><div><small>时长</small><strong>{analysis.metadata.duration_seconds.toFixed(2)} s</strong></div><div><small>峰值</small><strong>{analysis.peak_dbfs.toFixed(2)} dBFS</strong></div><div><small>近似 RMS 响度</small><strong>{analysis.approximate_loudness_dbfs.toFixed(2)} dBFS</strong></div></div>
      <p className="muted">{analysis.metadata.sample_rate_hz} Hz · {analysis.metadata.channels} 声道 · {analysis.metadata.bit_depth} bit。RMS 不是 LUFS 测量。</p>
      {analysis.warnings.map(item => <p key={item} className="notice warning">{item}</p>)}
      <p className="notice">{inspection.data!.provenance_status}</p></>}
    {(inspection.error || proposal.error) && <p className="notice error" role="alert">{(inspection.error || proposal.error)?.message}</p>}
    {proposal.data && <p className="notice success">音频绑定提案已创建。资产未发布，Unity 未写入。</p>}
  </div><fieldset className="inspector" disabled={busy}><legend>事件绑定</legend>
    <label>目标事件<input readOnly value={event} /></label><label>Mixer 分组<input value={mixer} maxLength={100} onChange={e => { setMixer(e.target.value); onMixerChange?.(e.target.value); proposal.reset(); }} /></label>
    <p className="muted">此音效为可选反馈，不阻断游戏主线。分析结果仅在当前会话有效。</p>
    <button className="primary" disabled={!analysis || !mixer.trim() || busy} onClick={() => proposal.mutate({ template, event, mixer, asset_id: inspection.data!.id })}>创建音频绑定提案</button>
    <div className="notice warning"><strong>blocked · Unity 未连接</strong><p>可分析并审阅提案。发布需要真实资产来源、资产发布审批和在线适配器，本入口不执行。</p></div>
    <button disabled>生成音频 · 未连接生成服务</button>
  </fieldset></div>;
}
