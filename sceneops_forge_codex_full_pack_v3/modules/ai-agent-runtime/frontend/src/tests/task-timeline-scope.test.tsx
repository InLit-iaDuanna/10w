import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { expect, test } from 'vitest';
import { AgentTaskActivity, AgentTaskTimeline } from '../AgentTaskWorkbench';

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

test('an empty workspace does not show or request unrelated agent task history', async () => {
  const host = document.createElement('div');
  const root = createRoot(host);
  const requests: string[] = [];
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async input => {
    requests.push(String(input));
    throw new Error('empty workspace must not request global task history');
  };
  try {
    await act(async () => root.render(<><AgentTaskTimeline projectId={null} /><AgentTaskActivity projectId={null} /></>));
    expect(host.textContent).toBe('');
    expect(requests).toEqual([]);
  } finally {
    globalThis.fetch = originalFetch;
    await act(async () => root.unmount());
  }
});
