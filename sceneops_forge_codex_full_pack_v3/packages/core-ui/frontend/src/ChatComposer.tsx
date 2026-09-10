import type { FormEventHandler, ReactNode } from 'react';
import './chat.css';

/** Shared presentation; each conversation retains its own draft and execution policy. */
export function ChatComposer({ input, options, actions, notice, onSubmit, className = '' }: {
  input: ReactNode;
  options: ReactNode;
  actions: ReactNode;
  notice?: ReactNode;
  onSubmit: FormEventHandler<HTMLFormElement>;
  className?: string;
}) {
  return <form className={`sceneops-chat-composer ${className}`} onSubmit={onSubmit}>
    {input}
    <div className="sceneops-chat-toolbar"><div className="sceneops-chat-options">{options}</div><div className="sceneops-chat-send">{actions}</div></div>
    {notice}
  </form>;
}
