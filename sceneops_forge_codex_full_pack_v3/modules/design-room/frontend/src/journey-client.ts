import { requestJson, requestEventStream } from '../../../../packages/api-client/frontend/src/index.ts';
import type { components } from './generated/journey-api';
export type PlanningJourney = components['schemas']['PlanningJourney'];
export type JourneyCommand = components['schemas']['JourneyCommand'];
export type JourneyOutline = components['schemas']['Outline'];
export type JourneyCard = components['schemas']['ProductionCard'];
export type JourneyStreamEvent = components['schemas']['JourneyStreamEvent'];
export type JourneyQuestion = components['schemas']['PlanningQuestion'];
export type JourneyChange = components['schemas']['JourneyChange'];
export type JourneyMessage = components['schemas']['JourneyMessage'];
export const journeyKey = (id: string) => ['planning-journey', id] as const;
export const journeyClient = {
  get: (id: string, signal?: AbortSignal) => requestJson<PlanningJourney>(`/api/design/journeys/${encodeURIComponent(id)}`, { signal }),
  command: (id: string, body: JourneyCommand, signal?: AbortSignal) => requestJson<PlanningJourney>(`/api/design/journeys/${encodeURIComponent(id)}/command`, { body, signal }),
  stream: async (id: string, body: JourneyCommand, onEvent: (event: JourneyStreamEvent) => void, signal: AbortSignal) => {
    let result: PlanningJourney | undefined;
    await requestEventStream<JourneyStreamEvent>(`/api/design/journeys/${encodeURIComponent(id)}/command/stream`, body, event => {
      if (event.type === 'error') throw new Error(event.text);
      if (event.type === 'complete' && event.state) result = event.state;
      onEvent(event);
    }, signal);
    if (!result) throw new Error('连接已中断，回复尚未确认保存。请重新读取后决定是否重试。');
    return result;
  },
};
