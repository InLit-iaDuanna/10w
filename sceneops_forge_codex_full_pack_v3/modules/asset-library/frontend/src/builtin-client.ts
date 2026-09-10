import { requestJson } from '@sceneops/api-client';
import type { components } from './generated/builtin-assets-api';

export type BuiltinAsset = components['schemas']['BuiltinAsset'];
export type BuiltinCatalog = components['schemas']['BuiltinCatalog'];
export const builtinAssets = {
  list: (signal?: AbortSignal) => requestJson<BuiltinCatalog>('/api/builtin-assets', {signal}),
  adopt: (assetId: string, projectId: string) => requestJson<components['schemas']['SaveProjectAssetResult']>(
    `/api/builtin-assets/${encodeURIComponent(assetId)}/adopt`, {body:{project_id:projectId}}),
};
