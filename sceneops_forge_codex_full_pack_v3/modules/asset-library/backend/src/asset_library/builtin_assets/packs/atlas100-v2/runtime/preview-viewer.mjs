/** Local, dependency-free textured GLB inspection. No external CDN or project mutations.
 * Direct-light GGX preview, not a path tracer or a verified host-game render.
 */
import {parseGLB} from './glb-document.mjs';
import {multiply,lookAt,perspective,transform} from './math.mjs';
import {PropWorld} from './physics-core.mjs';
const VS=`attribute vec3 aPosition;attribute vec3 aNormal;attribute vec4 aTangent;attribute vec2 aUV;
uniform mat4 uVP;uniform vec3 uOffset;varying vec3 vWorld;varying vec3 vNormal;varying vec4 vTangent;varying vec2 vUV;
void main(){vWorld=aPosition+uOffset;vNormal=aNormal;vTangent=aTangent;vUV=aUV;gl_Position=uVP*vec4(vWorld,1.);}`;
const FS=`precision highp float;varying vec3 vWorld;varying vec3 vNormal;varying vec4 vTangent;varying vec2 vUV;
uniform sampler2D uBase;uniform sampler2D uNormal;uniform sampler2D uORM;uniform sampler2D uEmissive;uniform vec3 uEye;uniform float uGlow;
const float PI=3.14159265;
void main(){vec3 base=pow(texture2D(uBase,vUV).rgb,vec3(2.2));vec3 n=normalize(vNormal);vec3 t=normalize(vTangent.xyz-n*dot(n,vTangent.xyz));vec3 b=cross(n,t)*vTangent.w;
vec3 nm=texture2D(uNormal,vUV).xyz*2.-1.;nm.xy*=.55;n=normalize(mat3(t,b,n)*nm);
vec3 orm=texture2D(uORM,vUV).rgb;float rough=clamp(orm.g,.06,1.);float metal=orm.b;vec3 v=normalize(uEye-vWorld),l=normalize(vec3(3.,6.,4.)),h=normalize(v+l);
float nl=max(dot(n,l),0.),nv=max(dot(n,v),.001),nh=max(dot(n,h),0.),vh=max(dot(v,h),0.);float a=rough*rough,a2=a*a;float d=a2/(PI*pow(nh*nh*(a2-1.)+1.,2.));float k=pow(rough+1.,2.)/8.;float g=nv/(nv*(1.-k)+k)*nl/(nl*(1.-k)+k);
vec3 f0=mix(vec3(.04),base,metal),f=f0+(1.-f0)*pow(1.-vh,5.);vec3 spec=d*g*f/max(4.*nv*nl,.001);vec3 diffuse=(1.-f)*(1.-metal)*base/PI;
vec3 col=(diffuse+spec)*nl*3.2+base*.23*orm.r+pow(texture2D(uEmissive,vUV).rgb,vec3(2.2))*uGlow;col=col/(col+vec3(1.));gl_FragColor=vec4(pow(col,vec3(1./2.2)),1.);}`;
export class PreviewViewer{
 constructor(canvas,onStatus=()=>{}){this.canvas=canvas;this.status=onStatus;this.gl=canvas.getContext('webgl',{antialias:true,alpha:false});if(!this.gl)throw new Error('WebGL 不可用：仍可查看清单、下载模型及 proofs/ 中的实际网格动画。');
  const g=this.gl;const shader=(type,src)=>{const s=g.createShader(type);g.shaderSource(s,src);g.compileShader(s);if(!g.getShaderParameter(s,g.COMPILE_STATUS))throw new Error(g.getShaderInfoLog(s));return s;};
  const vs=shader(g.VERTEX_SHADER,VS),fs=shader(g.FRAGMENT_SHADER,FS);this.program=g.createProgram();g.attachShader(this.program,vs);g.attachShader(this.program,fs);g.linkProgram(this.program);g.deleteShader(vs);g.deleteShader(fs);if(!g.getProgramParameter(this.program,g.LINK_STATUS))throw new Error(g.getProgramInfoLog(this.program));
  this.loc={};for(const n of ['uVP','uOffset','uEye','uBase','uNormal','uORM','uEmissive','uGlow'])this.loc[n]=g.getUniformLocation(this.program,n);this.attributes=['aPosition','aNormal','aTangent','aUV'].map(n=>g.getAttribLocation(this.program,n));
  this.records=[];this.textures=[];this.yaw=.65;this.pitch=.36;this.radius=8;this.target=[0,1,0];this.time=0;this.offset=[0,0,0];this.paused=false;this.disposed=false;this.physics=null;this.last=0;
  this.events=new AbortController();let dragging=false,px=0,py=0;const opts={signal:this.events.signal};
  canvas.addEventListener('pointerdown',e=>{dragging=true;px=e.clientX;py=e.clientY;canvas.setPointerCapture(e.pointerId);},opts);
  canvas.addEventListener('pointermove',e=>{if(!dragging)return;this.yaw-=(e.clientX-px)*.008;this.pitch=Math.max(-.1,Math.min(1.4,this.pitch+(e.clientY-py)*.008));px=e.clientX;py=e.clientY;},opts);
  canvas.addEventListener('pointerup',()=>dragging=false,opts);canvas.addEventListener('wheel',e=>{e.preventDefault();this.radius=Math.max(.2,this.radius*Math.exp(e.deltaY*.001));},{...opts,passive:false});this.frame=requestAnimationFrame(t=>this.render(t));
 }
 async load(url){const generation=this.loadGeneration=(this.loadGeneration??0)+1;this.abort?.abort();this.abort=new AbortController();const signal=this.abort.signal;const r=await fetch(url,{signal});if(!r.ok)throw new Error(`GLB 读取失败 ${r.status}`);const model=parseGLB(await r.arrayBuffer());if(signal.aborted)throw new Error('Load cancelled');
  this.clear();this.model=model;this.clip=null;this.time=0;this.physics=null;this.offset=[0,0,0];const g=this.gl;
  try{for(const blob of model.images()){const objectURL=URL.createObjectURL(blob);try{const img=new Image();img.src=objectURL;await img.decode();if(signal.aborted)throw new Error('Load cancelled');const texture=g.createTexture();g.bindTexture(g.TEXTURE_2D,texture);g.pixelStorei(g.UNPACK_FLIP_Y_WEBGL,false);g.texImage2D(g.TEXTURE_2D,0,g.RGBA,g.RGBA,g.UNSIGNED_BYTE,img);g.texParameteri(g.TEXTURE_2D,g.TEXTURE_WRAP_S,g.REPEAT);g.texParameteri(g.TEXTURE_2D,g.TEXTURE_WRAP_T,g.REPEAT);g.texParameteri(g.TEXTURE_2D,g.TEXTURE_MAG_FILTER,g.LINEAR);g.texParameteri(g.TEXTURE_2D,g.TEXTURE_MIN_FILTER,g.LINEAR_MIPMAP_LINEAR);g.generateMipmap(g.TEXTURE_2D);this.textures.push(texture);}finally{URL.revokeObjectURL(objectURL);}}
   model.doc.nodes.forEach((n,i)=>{if(n.mesh===undefined)return;for(const p of model.doc.meshes[n.mesh].primitives){const a=p.attributes,arrays=[model.array(a.POSITION),model.array(a.NORMAL),model.array(a.TANGENT),model.array(a.TEXCOORD_0)],buffers=arrays.map(v=>{const b=g.createBuffer();g.bindBuffer(g.ARRAY_BUFFER,b);g.bufferData(g.ARRAY_BUFFER,v,g.DYNAMIC_DRAW);return b;});this.records.push({node:i,mesh:p,arrays,buffers,count:arrays[0].length/3,skin:n.skin===undefined?null:model.doc.skins[n.skin],j:a.JOINTS_0===undefined?null:model.array(a.JOINTS_0),w:a.WEIGHTS_0===undefined?null:model.array(a.WEIGHTS_0)});}});
   const bounds=this.updateGeometry();this.extent=Math.max(...bounds.max.map((v,i)=>v-bounds.min[i]));this.target=bounds.min.map((v,i)=>(v+bounds.max[i])/2);this.radius=Math.max(this.extent*1.9,1.2);this.restTarget=[...this.target];this.restRadius=this.radius;
   return {clips:model.doc.animations??[],triangles:this.records.reduce((s,r)=>s+r.count/3,0),nodes:this.records.length};
  }catch(e){if(generation===this.loadGeneration)this.clear();throw e;}
 }
 setClip(name){this.clip=(this.model?.doc.animations??[]).find(c=>c.name===name)??null;this.time=0;this.paused=false;this.updateGeometry();}
 updateGeometry(){if(!this.model)return;const world=this.model.pose(this.clip,this.time),g=this.gl;const min=[Infinity,Infinity,Infinity],max=[-Infinity,-Infinity,-Infinity];
  for(const r of this.records){const [base,norm,tang]=r.arrays,p=new Float32Array(base.length),n=new Float32Array(norm.length),t=new Float32Array(tang.length);const matrices=r.skin?this.model.skinMatrices(r.skin,world):[world.get(r.node)];
   for(let i=0;i<r.count;i++){const v=base.subarray(i*3,i*3+3),vn=norm.subarray(i*3,i*3+3),vt=tang.subarray(i*4,i*4+3);for(let k=0;k<(r.skin?4:1);k++){const weight=r.skin?r.w[i*4+k]:1;if(!weight)continue;const m=matrices[r.skin?r.j[i*4+k]:0],a=transform(m,v),b=transform(m,vn,true),c=transform(m,vt,true);for(let j=0;j<3;j++){p[i*3+j]+=a[j]*weight;n[i*3+j]+=b[j]*weight;t[i*4+j]+=c[j]*weight;}}t[i*4+3]=tang[i*4+3];for(let j=0;j<3;j++){min[j]=Math.min(min[j],p[i*3+j]);max[j]=Math.max(max[j],p[i*3+j]);}}
   for(const [i,data] of [p,n,t].entries()){g.bindBuffer(g.ARRAY_BUFFER,r.buffers[i]);g.bufferSubData(g.ARRAY_BUFFER,0,data);}
  }return {min,max};
 }
 demoPickup(binding){if(!binding?.interaction.actions.includes('pick_up'))throw new Error('这是静态构件，不启用拾取演示。');this.physics=null;this.offset=[0,Math.max(1,this.extent*.6),0];this.target=[...this.restTarget];this.target[1]+=this.offset[1]/2;this.radius=this.restRadius*1.3;}
 demoDrop(binding){if(!binding?.interaction.actions.includes('drop'))throw new Error('这是静态构件，不启用掉落演示。');const world=new PropWorld();world.addBody({id:'preview-floor',position:[0,-.25,0],colliders:[{center:[0,0,0],half:[50,.25,50]}]});const start=this.offset[1]>.1?[...this.offset]:[0,Math.max(1,this.extent*.7),0];world.addBody({id:'preview-prop',position:start,mode:'dynamic',mass:binding.body.mass_kg,colliders:binding.colliders.map(c=>({center:c.center_m,half:c.half_extents_m,axes:c.axes}))});this.physics=world;this.target=[...this.restTarget];this.target[1]+=start[1]/2;this.radius=this.restRadius*1.4;this.setClip('');this.offset=start;}
 render(timestamp){if(this.disposed)return;const dt=Math.min((timestamp-(this.last||timestamp))/1000,.05);this.last=timestamp;const g=this.gl;
  if(this.model&&this.clip&&!this.paused){this.time+=dt;const duration=Math.max(...this.clip.samplers.map(s=>this.model.array(s.input).at(-1)));if(this.time>duration)this.time=this.clip.extras?.loop?this.time%duration:duration;this.updateGeometry();}
  if(this.physics){this.physics.advance(dt);this.offset=[...this.physics.bodies.get('preview-prop').position];}
  const ratio=Math.min(devicePixelRatio||1,2),w=Math.floor(this.canvas.clientWidth*ratio),h=Math.floor(this.canvas.clientHeight*ratio);if(w&&h&&(w!==this.canvas.width||h!==this.canvas.height)){this.canvas.width=w;this.canvas.height=h;}g.viewport(0,0,this.canvas.width,this.canvas.height);g.clearColor(.04,.055,.08,1);g.clear(g.COLOR_BUFFER_BIT|g.DEPTH_BUFFER_BIT);g.enable(g.DEPTH_TEST);g.disable(g.CULL_FACE);g.useProgram(this.program);
  const eye=[this.target[0]+this.radius*Math.sin(this.yaw)*Math.cos(this.pitch),this.target[1]+this.radius*Math.sin(this.pitch),this.target[2]+this.radius*Math.cos(this.yaw)*Math.cos(this.pitch)];const vp=multiply(perspective(.7,this.canvas.width/Math.max(this.canvas.height,1),.02,Math.max(1000,this.radius*10)),lookAt(eye,this.target));g.uniformMatrix4fv(this.loc.uVP,false,new Float32Array(vp));g.uniform3fv(this.loc.uEye,eye);g.uniform3fv(this.loc.uOffset,this.offset);
  if(this.model)for(const r of this.records){const mat=this.model.doc.materials[r.mesh.material],mr=mat.pbrMetallicRoughness;const textures=[mr.baseColorTexture.index,mat.normalTexture.index,mr.metallicRoughnessTexture.index,mat.emissiveTexture.index];textures.forEach((id,i)=>{g.activeTexture(g.TEXTURE0+i);g.bindTexture(g.TEXTURE_2D,this.textures[this.model.doc.textures[id].source]);g.uniform1i(this.loc[['uBase','uNormal','uORM','uEmissive'][i]],i);});g.uniform1f(this.loc.uGlow,mat.emissiveFactor?.[0]??0);r.buffers.forEach((buffer,i)=>{g.bindBuffer(g.ARRAY_BUFFER,buffer);g.enableVertexAttribArray(this.attributes[i]);g.vertexAttribPointer(this.attributes[i],[3,3,4,2][i],g.FLOAT,false,0,0);});g.drawArrays(g.TRIANGLES,0,r.count);}
  this.frame=requestAnimationFrame(t=>this.render(t));
 }
 clear(){for(const r of this.records)for(const b of r.buffers)this.gl.deleteBuffer(b);for(const t of this.textures)this.gl.deleteTexture(t);this.records=[];this.textures=[];this.model=null;}
 dispose(){this.disposed=true;cancelAnimationFrame(this.frame);this.abort?.abort();this.events.abort();this.clear();this.gl.deleteProgram(this.program);}
}
