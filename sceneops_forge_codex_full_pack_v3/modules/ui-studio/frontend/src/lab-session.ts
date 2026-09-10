/** Convert the canonical folder-project identity into the UUID required by lab APIs. */
export function labSessionForProject(projectId: string): string {
  const compact = /^prj_([0-9a-f]{32})$/i.exec(projectId)?.[1];
  if (!compact) throw new Error('当前项目身份不能用于高级工作台，请重新打开本地项目。');
  return `${compact.slice(0, 8)}-${compact.slice(8, 12)}-${compact.slice(12, 16)}-${compact.slice(16, 20)}-${compact.slice(20)}`;
}
