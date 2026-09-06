import { useEffect, useRef } from 'react';
import { useProduction, type ProductionStep } from '@sceneops/ai-agent-runtime';

/** Observe execution, never start it. Dismissal survives refresh in this tab. */
export function ProductionAutoOpen({ projectId, open, onError }: {
  projectId: string | null;
  open: (step: ProductionStep) => Promise<boolean>;
  onError: (error: unknown) => void;
}) {
  const production = useProduction(projectId);
  const queue = useRef(Promise.resolve());
  const scheduled = useRef(new Set<string>());
  const observed = useRef(new Map<string, Set<string>>());
  useEffect(() => {
    if (!projectId || !production.data) return;
    const initial = !observed.current.has(projectId);
    const known = observed.current.get(projectId) ?? new Set<string>();
    observed.current.set(projectId, known);
    for (const step of production.data?.steps ?? []) {
      if (production.data.tasks.find(task => task.id === step.task_id)?.authorization_card.task_profile === 'card-development') continue;
      const firstExecution = !!step.started_at && !known.has(step.id);
      if (step.started_at) known.add(step.id);
      if (step.state !== 'running' && (initial || !firstExecution)) continue;
      const key = `sceneops.production.opened.${step.project_id}.${step.task_id}.${step.module_id}`;
      if (scheduled.current.has(key) || sessionStorage.getItem(key)) continue;
      scheduled.current.add(key);
      queue.current = queue.current.then(async () => {
        if (await open(step)) sessionStorage.setItem(key, '1');
        else scheduled.current.delete(key);
      }).catch(onError);
    }
  }, [projectId, production.data, open, onError]);
  return null;
}
