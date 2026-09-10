import {useState} from 'react';
import {useQuery,useMutation,useQueryClient} from '@tanstack/react-query';
import {workspaceClient} from '../../../../packages/workspace-client/frontend/src/index.ts';
import {localServers,localServerKey,type LocalServerInfo} from './local-server-client';
import './local-servers.css';

export function LocalServerPanel() {
  const cache=useQueryClient();
  const query=useQuery({queryKey:localServerKey,queryFn:({signal})=>localServers.list(signal),refetchInterval:3000,retry:false});
  const projects=useQuery({queryKey:['workspace-projects'],queryFn:()=>workspaceClient.projects(),retry:false});
  const [selected,setSelected]=useState<LocalServerInfo|null>(null);
  const stop=useMutation({mutationFn:(id:string)=>localServers.stop(id),onSuccess:()=>setSelected(null),
    onSettled:()=>{void cache.invalidateQueries({queryKey:localServerKey});void cache.invalidateQueries({queryKey:['agent-tasks']});}});
  const names=new Map((projects.data?.projects??[]).map(project=>[project.project_id,project.name]));
  return <section className="local-servers" aria-label="本地服务管理">
    <header><div><h2>本地服务</h2><p>每 3 秒更新 · 关闭不用的服务可释放端口</p></div><button type="button" disabled={query.isFetching} onClick={()=>void query.refetch()}>刷新</button></header>
    {query.isPending && <p role="status">正在查找本地服务…</p>}
    {query.error && <p role="alert">读取失败：{query.error.message}。下方已有内容可能不是最新状态。</p>}
    {stop.error && <p role="alert">关闭失败：{stop.error.message}</p>}
    {stop.data && <p role="status">{stop.data.message}</p>}
    {selected && <section className="local-server-confirm" aria-label="关闭服务确认">
      <strong>关闭 {selected.name}？</strong><p>端口 {selected.endpoints.map(endpoint=>endpoint.port).join('、')}。使用这些端口的页面会断开，需要重新启动服务后才能访问。</p>
      <button type="button" disabled={stop.isPending} onClick={()=>stop.mutate(selected.id)}>{stop.isPending?'正在关闭…':'确认关闭'}</button>
      <button type="button" disabled={stop.isPending} onClick={()=>setSelected(null)}>取消</button>
    </section>}
    <div className="local-server-list">
      {query.data && !query.data.servers.length && <p>当前没有发现监听中的本地服务。</p>}
      {query.data?.servers.map(server=><article key={server.id} className="local-server-row">
        <div className="local-server-heading"><strong>{server.name}</strong><span>PID {server.pid}</span></div>
        <p>{server.project_id ? names.get(server.project_id)??'项目服务' : server.managed?'工作台管理的服务':'其他本地服务'}</p>
        <div className="local-server-endpoints">{server.endpoints.map(endpoint=><code key={`${endpoint.host}:${endpoint.port}`}>{endpoint.host}:{endpoint.port}</code>)}</div>
        <div className="local-server-action">{server.can_stop?<button type="button" disabled={stop.isPending} onClick={()=>{stop.reset();setSelected(server);}}>关闭服务</button>:<span>{server.stop_reason??'仅供查看'}</span>}</div>
      </article>)}
    </div>
  </section>;
}
