export const characterAnimationKeys = {
  all: ['character-animation'] as const,
  bundle: (projectId: string, characterId: string) =>
    [...characterAnimationKeys.all, 'bundle', projectId, characterId] as const,
  inspection: (characterId: string, rigVersionId: string) =>
    [...characterAnimationKeys.all, 'inspection', characterId, rigVersionId] as const,
  preview: (previewArtifactId: string) =>
    [...characterAnimationKeys.all, 'preview', previewArtifactId] as const,
};
