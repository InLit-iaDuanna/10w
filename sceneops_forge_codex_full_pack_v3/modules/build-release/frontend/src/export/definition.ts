export const exportEditorDefinition = {
  id: 'build.export', title: '导出', icon: 'package', category: 'build',
  load: () => import('./ExportEditor'), defaultPlacement: 'center',
  minWidth: 340, minHeight: 320, singleton: false,
  requiredPermissions: ['build:read'], requiredIntegrations: [], optionalIntegrations: ['artifact-store', 'build-runner'],
  initialState: () => ({}), serializeState: () => ({}), restoreState: () => ({}),
};
