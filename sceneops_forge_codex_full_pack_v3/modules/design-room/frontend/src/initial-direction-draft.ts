import type { PlanningJourney } from './journey-client';

export type InitialDirectionDraft = {
  core_experience: string;
  perspective_style: string;
  simplified_scope: string;
  code_architecture: 'object-component' | 'ecs' | null;
};

/** Reuse actual planning fields or user text; this projection never confirms a direction. */
export function initialDirectionDraft(state?: PlanningJourney): InitialDirectionDraft {
  const direction = state?.initial_demo_direction;
  const outline = state?.outline;
  const userText = (state?.messages ?? []).filter(message => message.role === 'user')
    .map(message => message.text).join('\n');
  return {
    core_experience: (direction?.core_experience ?? outline?.experience ?? userText).slice(0, 1000),
    perspective_style: direction?.perspective_style ?? '',
    simplified_scope: (direction?.simplified_scope ?? outline?.scope ?? '').slice(0, 1000),
    code_architecture: direction?.code_architecture ?? state?.technical_plan?.code_architecture ?? null,
  };
}
