from types import SimpleNamespace
import pytest
from world_composer import EnvironmentSceneService,EnvironmentSceneError,SceneLighting,SaveSceneLighting,scene_lighting_game_source

def test_scene_lighting_versions_and_conflicts_preserve_previous(tmp_path):
    service=EnvironmentSceneService(tmp_path/'scene.db',SimpleNamespace(exists=lambda p:p=='project'),None,None)
    lighting=SceneLighting(lights=[{'id':'key','name':'Key','type':'directional','color':'#fff1d5','intensity':3.4,'position':[-7,17,10]}])
    first=service.save_lighting('project',SaveSceneLighting(expected_version=0,lighting=lighting))
    changed=lighting.model_copy(update={'exposure':1.25})
    second=service.save_lighting('project',SaveSceneLighting(expected_version=1,lighting=changed))
    with pytest.raises(EnvironmentSceneError):service.save_lighting('project',SaveSceneLighting(expected_version=1,lighting=lighting))
    assert service.get('project',1).lighting==lighting
    assert service.get('project').lighting==changed
    assert first.objects==second.objects==[]
    with pytest.raises(ValueError):SceneLighting(lights=[lighting.lights[0],lighting.lights[0]])
    with pytest.raises(ValueError):SceneLighting(exposure=float('nan'))
    from world_composer.scene_lighting import SceneLight
    sky=SceneLight(id='sky',name='Sky',type='hemisphere',color='#ffffff')
    assert sky.sky_direction==(0,1,0)
    with pytest.raises(ValueError):SceneLight(id='sky',name='Sky',type='hemisphere',color='#ffffff',sky_direction=(0,0,0))
