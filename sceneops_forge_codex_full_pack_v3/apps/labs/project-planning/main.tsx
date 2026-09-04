import React,{useState} from 'react';
import {createRoot} from 'react-dom/client';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {loadIntakePanel,type ProjectIntakeRecord} from '../../../modules/project-intake/frontend/src/index.ts';
import {loadDesignPanel} from '../../../modules/design-room/frontend/src/index.ts';
import {loadPlanningPanel,createPlanningClient,projectFeatureForPlanning} from '../../../modules/production-planner/frontend/src/index.ts';
import './style.css';
const IntakePanel=React.lazy(loadIntakePanel),DesignPanel=React.lazy(loadDesignPanel),PlanningPanel=React.lazy(loadPlanningPanel);
const queryClient=new QueryClient();const client=createPlanningClient();
function App(){const [project,setProject]=useState<{intake:ProjectIntakeRecord,brief:string}|null>(null);const [planId,setPlanId]=useState('');const [tab,setTab]=useState('intake');
 return <><header><strong>SceneOps <span>FORGE</span></strong><span>工作台 02 / 项目设计与生产计划</span><small>隔离会话 · mock</small></header><nav aria-label="工作步骤">{[['intake','01 项目入口'],['design','02 设计规格'],['plan','03 生产计划']].map(([id,title])=><button className={tab===id?'active':'secondary'} key={id} disabled={id==='design'&&!project||id==='plan'&&!planId} onClick={()=>setTab(id)}>{title}</button>)}</nav><main>
 <div hidden={tab!=='intake'}><IntakePanel onReady={(intake,brief)=>{setProject({intake,brief});setPlanId('');setTab('design')}}/></div>
 {project&&<div hidden={tab!=='design'}><DesignPanel key={project.intake.intakeId} {...project} onPlan={async version=>{const result=await client.create({snapshot:projectFeatureForPlanning(version)});setPlanId(result.plan.plan_id);setTab('plan')}}/></div>}
 {planId&&<div hidden={tab!=='plan'}><PlanningPanel key={planId} client={client} planId={planId}/></div>}</main><footer>本地设计与规划服务 · 刷新页面丢失设计会话，重启 API 丢失计划 · 外部执行 blocked</footer></>}
createRoot(document.getElementById('root')!).render(<QueryClientProvider client={queryClient}><React.Suspense fallback={<p>正在加载工作台…</p>}><App/></React.Suspense></QueryClientProvider>);
