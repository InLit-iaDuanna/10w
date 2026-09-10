import { useState } from 'react';
import { MarkdownMessage } from '../../../../packages/core-ui/frontend/src/index.ts';
import type { JourneyQuestion } from './journey-client';

export function PlanningQuestionCard({ question, disabled, answered, locked = false, onAnswer, onCustom }: {
  question: JourneyQuestion; disabled: boolean; answered: boolean; locked?: boolean;
  onAnswer: (index: number) => void; onCustom: () => void;
}) {
  const [selected, setSelected] = useState(question.recommended_index);
  if (answered || locked) return <details className="journey-question-answered"><summary>{answered ? '已回答' : '此步骤已结束'} · {question.prompt}</summary>
    {question.options.map((option, index) => <p key={index}>{option.label} — {option.description}</p>)}</details>;
  return <section className="journey-question" aria-label="当前对齐问题">
    <MarkdownMessage text={question.prompt} />
    <div role="radiogroup" aria-label="选择你的答案">{question.options.map((option, index) => <label key={index} className={selected === index ? 'selected' : ''}>
      <input type="radio" name="planning-answer" checked={selected === index} disabled={disabled} onChange={() => setSelected(index)} />
      <span><strong>{option.label}{index === question.recommended_index && <small>推荐</small>}</strong><span>{option.description}</span></span>
    </label>)}</div>
    <footer><button type="button" disabled={disabled} onClick={onCustom}>自己补充</button>
      <button type="button" disabled={disabled} onClick={() => onAnswer(selected)}>确认并继续 <span aria-hidden="true">↵</span></button></footer>
  </section>;
}
