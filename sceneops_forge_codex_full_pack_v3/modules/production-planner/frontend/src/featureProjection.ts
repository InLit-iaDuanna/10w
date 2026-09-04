import type {DocumentVersion,FeatureSpec} from '../../../design-room/frontend/src/index.ts';
import type {FeaturePlanningSnapshot,Workstream} from './generated/lab-contracts.ts';
/** Explicit full production template; does not infer workstreams from keywords. */
export function projectFeatureForPlanning(version:DocumentVersion<FeatureSpec>):FeaturePlanningSnapshot {
 if(version.document.status!=='ready-for-planning')throw new Error('设计尚未确认，请先完成准备度检查。');
 const workstreams:Workstream[]=['design','concept','asset','animation','world','logic','ui','audio','vfx','render','build','test'];
 return {feature_ref:{project_id:version.document.projectId,feature_id:version.document.featureSpecId,revision:version.versionNumber},source_contract_version:'design.feature-spec@1',title:version.document.title,summary:version.document.goal,source_mode:version.mode,
 acceptance_criteria:version.document.acceptanceCriteria.map(c=>({criterion_id:c.criterionId,statement:`${c.given}；${c.when}；${c.then}`,workstreams,required_evidence:version.document.requiredTests.filter(t=>t.linkedCriterionIds.includes(c.criterionId)).map(t=>t.level)}))};
}
