/** Dependency-free prop physics: fixed/kinematic OBBs and translating rigid bodies.
 * Fixed-step semi-implicit integration; no angular dynamics, cloth, or ragdoll.
 * Every collider retains the source sceneops_id. Does not mutate host gameplay.
 */
export const add=(a,b)=>a.map((v,i)=>v+b[i]);
export const sub=(a,b)=>a.map((v,i)=>v-b[i]);
export const mul=(a,s)=>a.map(v=>v*s);
export const dot=(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0);
export const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
export const length=a=>Math.sqrt(dot(a,a));
export const normalized=a=>mul(a,1/Math.max(length(a),1e-12));
export function finite3(value,name='vector') { if(!Array.isArray(value)||value.length!==3||!value.every(Number.isFinite))throw new Error(`Invalid ${name}`);return value; }
const axesIdentity=[[1,0,0],[0,1,0],[0,0,1]];
export function aabb(box){const e=[0,0,0];for(let i=0;i<3;i++)for(let j=0;j<3;j++)e[j]+=Math.abs(box.axes[i][j])*box.half[i];return {min:sub(box.center,e),max:add(box.center,e)};}
function overlaps(a,b){return a.min.every((v,i)=>v<=b.max[i]&&a.max[i]>=b.min[i]);}
export function sat(a,b){
  if(!overlaps(aabb(a),aabb(b)))return null;
  const delta=sub(a.center,b.center);let depth=Infinity,normal=null;
  const axes=[...a.axes,...b.axes,...a.axes.flatMap(x=>b.axes.map(y=>cross(x,y)))];
  for(const candidate of axes){const n=length(candidate);if(n<1e-8)continue;const axis=mul(candidate,1/n);
    const ra=a.axes.reduce((s,x,i)=>s+Math.abs(dot(x,axis))*a.half[i],0);
    const rb=b.axes.reduce((s,x,i)=>s+Math.abs(dot(x,axis))*b.half[i],0);
    const overlap=ra+rb-Math.abs(dot(delta,axis));if(overlap<=0)return null;
    if(overlap<depth){depth=overlap;normal=mul(axis,dot(delta,axis)<0?-1:1);}
  }
  return normal?{depth,normal}:null;
}
export class PropWorld{
  constructor({gravity=[0,-9.81,0],step=1/120}={}){
    finite3(gravity);if(!Number.isFinite(step)||step<=0||step>1/30)throw new Error('Invalid fixed step');
    this.gravity=gravity;this.step=step;this.accumulator=0;this.bodies=new Map();this.events=[];this.ticks=0;
  }
  addBody({id,position=[0,0,0],mode='fixed',mass=1,colliders=[],sleeping=false,friction=.65,restitution=.08,linearDamping=0,gravityScale=1}){
    if(typeof id!=='string'||!id||this.bodies.has(id))throw new Error('Missing or duplicate body ID');
    if(!['fixed','dynamic','kinematic','sensor'].includes(mode))throw new Error('Unsupported body mode');
    finite3(position);if(!Number.isFinite(linearDamping)||linearDamping<0||!Number.isFinite(gravityScale)||gravityScale<0)throw new Error('Invalid damping or gravity scale');
    if(!Number.isFinite(friction)||friction<0||!Number.isFinite(restitution)||restitution<0||restitution>1)throw new Error('Invalid contact coefficients');
    if(!Number.isFinite(mass)||mass<=0)throw new Error('Invalid mass');
    for(const c of colliders){finite3(c.center);finite3(c.half);if(c.half.some(x=>x<=0))throw new Error('Nonpositive collider');
      for(const axis of c.axes??axesIdentity)finite3(axis);}
    const body={id,position:[...position],velocity:[0,0,0],mode,mass,enabled:true,sleeping,friction,restitution,linearDamping,gravityScale,
      colliders:colliders.map(c=>({...c,center:[...c.center],half:[...c.half],axes:(c.axes??axesIdentity).map(a=>[...a])})),restTicks:0};
    this.bodies.set(id,body);return body;
  }
  removeBody(id){return this.bodies.delete(id);}
  boxes(body){return body.colliders.map(c=>({...c,center:add(body.position,c.center)}));}
  impulse(id,value){finite3(value);const b=this.bodies.get(id);if(!b||b.mode!=='dynamic')throw new Error('Not a dynamic body');b.velocity=add(b.velocity,mul(value,1/b.mass));b.sleeping=false;}
  advance(dt){if(!Number.isFinite(dt)||dt<0)throw new Error('Invalid dt');this.accumulator+=Math.min(dt,.1);
    while(this.accumulator+1e-12>=this.step){this.integrate();this.accumulator-=this.step;}}
  integrate(){
    const dt=this.step;this.ticks++;const active=[...this.bodies.values()].filter(b=>b.enabled);
    const moving=active.filter(b=>{if(b.mode!=='kinematic')return false;const signature=JSON.stringify([b.position,b.colliders]);const changed=b.previousKinematic!==undefined&&b.previousKinematic!==signature;b.previousKinematic=signature;return changed;});
    for(const b of active)if(b.mode==='dynamic'&&b.sleeping&&moving.some(k=>this.boxes(b).some(a=>this.boxes(k).some(c=>sat(a,c)))))b.sleeping=false;
    for(const body of active){if(body.mode!=='dynamic'||body.sleeping)continue;
      body.velocity=mul(add(body.velocity,mul(this.gravity,dt*body.gravityScale)),Math.exp(-body.linearDamping*dt));body.position=add(body.position,mul(body.velocity,dt));
      let supported=false;
      for(let iteration=0;iteration<3;iteration++)for(const other of active){
        if(other===body||(!other.enabled))continue;
        let done=false;
        for(const a of this.boxes(body)){for(const b of this.boxes(other)){
          const hit=sat(a,b);if(!hit)continue;
          if(other.mode==='sensor'){this.emit({type:'trigger',bodyId:body.id,otherId:other.id});continue;}
          const invA=1/body.mass,invB=other.mode==='dynamic'?1/other.mass:0,total=invA+invB;
          const correction=mul(hit.normal,hit.depth+1e-5);body.position=add(body.position,mul(correction,invA/total));
          if(invB){other.position=sub(other.position,mul(correction,invB/total));other.sleeping=false;}
          const relative=sub(body.velocity,other.velocity);const vn=dot(relative,hit.normal);
          if(vn<0){const impulse=-(1+Math.min(body.restitution,other.restitution))*vn/total;
            body.velocity=add(body.velocity,mul(hit.normal,impulse*invA));if(invB)other.velocity=sub(other.velocity,mul(hit.normal,impulse*invB));}
          const normalVelocity=mul(hit.normal,dot(body.velocity,hit.normal));const tangent=sub(body.velocity,normalVelocity);
          body.velocity=add(normalVelocity,mul(tangent,Math.max(0,1-Math.min(body.friction,other.friction)*dt*12)));
          supported ||= hit.normal[1]>.5;this.emit({type:'contact',bodyId:body.id,otherId:other.id,normal:hit.normal});done=true;break;
        }if(done)break;}
      }
      if(supported&&length(body.velocity)<.045){body.restTicks++;if(body.restTicks>50){body.sleeping=true;body.velocity=[0,0,0];}}
      else body.restTicks=0;
    }
  }
  emit(event){this.events.push({...event,tick:this.ticks});if(this.events.length>256)this.events.shift();}
  drainEvents(){const e=this.events;this.events=[];return e;}
}
