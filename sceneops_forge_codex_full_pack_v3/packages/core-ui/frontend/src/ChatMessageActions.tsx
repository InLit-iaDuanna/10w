import './chat.css';
import {useState} from 'react';

export function ChatMessageActions({text}: {text: string}) {
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState('');
  const copy = async () => {
    try { await navigator.clipboard.writeText(text); setCopied(true); setError(''); }
    catch { setError('无法复制，请选择正文复制。'); }
  };
  return <div className="sceneops-chat-message-actions">
    <button type="button" title={copied ? '已复制' : '复制回复'} aria-label={copied ? '已复制' : '复制回复'} onClick={() => void copy()}>
      <svg aria-hidden="true" viewBox="0 0 24 24">{copied ? <path d="m5 12 4 4L19 6" /> : <><rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3" /></>}</svg>
    </button>
    {error && <span role="status">{error}</span>}
  </div>;
}
