"""Scene-owned lighting, shared by the environment editor and generated game."""
import json
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,model_validator

class LightingModel(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)

class SceneShadow(LightingModel):
    map_size:int=Field(default=1024,ge=128,le=4096)
    extent:float=Field(default=14,gt=0)
    near:float=Field(default=1,gt=0)
    far:float=Field(default=60,gt=0)
    bias:float=0
    normal_bias:float=0

class SceneLight(LightingModel):
    id:str=Field(min_length=1,max_length=200)
    name:str=Field(min_length=1,max_length=200)
    type:Literal['ambient','hemisphere','directional','point','spot']
    color:str=Field(pattern=r'^#[0-9a-fA-F]{6}$')
    ground_color:str=Field(default='#242424',pattern=r'^#[0-9a-fA-F]{6}$')
    sky_direction:tuple[float,float,float]=(0,1,0)
    intensity:float=Field(default=1,ge=0)
    position:tuple[float,float,float]=(0,0,0)
    target:tuple[float,float,float]=(0,0,0)
    distance:float=Field(default=0,ge=0)
    angle:float=Field(default=.7,gt=0,le=1.5707963267948966)
    penumbra:float=Field(default=.4,ge=0,le=1)
    enabled:bool=True
    shadow:SceneShadow|None=None

    @model_validator(mode='after')
    def valid_sky_direction(self):
        if self.type=='hemisphere' and not any(self.sky_direction):
            raise ValueError('天空光方向不能为零向量。')
        return self

class SceneLighting(LightingModel):
    background:str=Field(default='#1b1b1b',pattern=r'^#[0-9a-fA-F]{6}$')
    exposure:float=Field(default=1,gt=0,le=10)
    lights:list[SceneLight]=Field(default_factory=list,max_length=64)
    source_refs:list[str]=Field(default_factory=list,max_length=32)

    @model_validator(mode='after')
    def unique_ids(self):
        if len({light.id for light in self.lights})!=len(self.lights):
            raise ValueError('场景灯光 ID 重复。')
        return self

class SaveSceneLighting(LightingModel):
    expected_version:int=Field(ge=0)
    lighting:SceneLighting

def scene_lighting_game_source(value):
    """Compile typed data to fixed Three.js constructors; names are quoted data."""
    if value is None:
        return 'export function applyProjectSceneLighting(_scene:THREE.Scene,_renderer:{toneMappingExposure:number}) {return false}\n'
    state=SceneLighting.model_validate(value)
    lines=['export function applyProjectSceneLighting(scene:THREE.Scene,renderer:{toneMappingExposure:number}) {',
        'scene.background = new THREE.Color('+json.dumps(state.background)+');',
        'renderer.toneMappingExposure = '+str(state.exposure)+';']
    for index,light in enumerate(state.lights):
        name='sceneLight'+str(index)
        args=[light.color,light.intensity]
        constructor={'ambient':'AmbientLight','hemisphere':'HemisphereLight','directional':'DirectionalLight','point':'PointLight','spot':'SpotLight'}[light.type]
        if light.type=='hemisphere':args=[light.color,light.ground_color,light.intensity]
        if light.type=='point':args += [light.distance]
        if light.type=='spot':args += [light.distance,light.angle,light.penumbra]
        lines += ['const '+name+' = new THREE.'+constructor+'('+','.join(json.dumps(v) for v in args)+');',
            name+'.name='+json.dumps(light.name)+';',name+'.userData.sceneops_id='+json.dumps(light.id)+';',
            name+'.visible='+str(light.enabled).lower()+';',name+'.position.set('+','.join(map(str,light.sky_direction if light.type=='hemisphere' else light.position))+');']
        if light.type in ('directional','spot'):
            lines += [name+'.target.position.set('+','.join(map(str,light.target))+');','scene.add('+name+'.target);']
        if light.shadow and light.type in ('directional','point','spot'):
            shadow=light.shadow
            lines += [name+'.castShadow=true;',name+f'.shadow.mapSize.set({shadow.map_size},{shadow.map_size});',
                name+f'.shadow.camera.near={shadow.near};',name+f'.shadow.camera.far={shadow.far};',
                name+f'.shadow.bias={shadow.bias};',name+f'.shadow.normalBias={shadow.normal_bias};']
            if light.type=='directional':
                for key,sign in [('left',-1),('right',1),('top',1),('bottom',-1)]:
                    lines.append(name+f'.shadow.camera.{key}={shadow.extent*sign};')
        lines.append('scene.add('+name+');')
    return '\n'.join([*lines,'return true;','}'])
