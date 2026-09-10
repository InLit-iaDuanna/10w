import React from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './markdown-message.css';

/** Model prose is rendered, never executed; remote images do not load implicitly. */
export function MarkdownMessage({ text }: { text: string }) {
  return <div className="sceneops-markdown"><Markdown remarkPlugins={[[remarkGfm, {singleTilde:false}]]} skipHtml components={{
    a: ({ children, href }) => <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>,
    img: ({ alt }) => <span className="markdown-image-reference">[图片：{alt || '未自动加载'}]</span>,
  }}>{text}</Markdown></div>;
}
