"""Build detailed v4 geometry into versioned paths while preserving earlier files."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
import generate as g
import expand as e
import expand_v3 as v3
import detail_assets as a
import detail_scenes as s

BASE=g.ROOT
DEST=BASE/'revisions/v4'

def emit(key,label,category,objects,description,kind,spawns=None):
    g.export(key,objects)
    record=g.entry(key,label,category,objects,description=description,spawns=spawns)
    record['kind']=kind;record['version']=4
    record['glb_path']='revisions/v4/'+record['glb_path']
    record['preview_path']='revisions/v4/'+record['preview_path']
    record['source']['generator']='modules/asset-library/builtin-assets/source/detail_collection.py'
    if kind=='character':
        record['silhouette_family']=f'{g.PACK}/{key}-v4'
    g.presentation(objects,kind=='scene')
    bpy.context.scene.render.filepath=str(g.ROOT/'previews'/f'{key}.png')
    bpy.ops.render.render(write_still=True);g.clean_presentation()
    return record

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--only',default='')
    opts=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    selected=set(opts.only.split(',')) if opts.only else None
    g.ROOT=DEST
    for folder in ['glb','previews']:(DEST/folder).mkdir(parents=True,exist_ok=True)
    document=json.loads((BASE/'catalog.json').read_text())
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    g.BUILDERS.update(e.NEW);g.BUILDERS.update(v3.NEW);g.BUILDERS.update(a.PROPS);g.BUILDERS.update(a.CHARACTERS)
    g.bake_assets();bpy.context.view_layer.update()
    additions=[]
    for key,(label,category,_) in {**a.PROPS,**a.CHARACTERS}.items():
        if selected and key not in selected:continue
        kind='character' if key in a.CHARACTERS else 'prop'
        record=emit(key,label,category,g.ASSETS[key],f'可跨场景复用的{label}。独立网格与材质；角色为静态造型，尚未绑定骨骼。' if kind=='character' else f'可跨场景独立摆放的{label}，包含结构分件与材质。',kind)
        additions.append(record)
        for obj in g.ASSETS[key]:obj.hide_render=True;obj.hide_set(True)
        print('DETAILED_ASSET',key,flush=True)
    themes=[(t,e.scene) for t in e.THEMES]+[(t,v3.scene) for t in v3.THEMES]+[(t,s.extra_scene) for t in s.EXTRA]
    for (theme,label,style,genres),builder in themes:
        key='world-'+theme
        if selected and key not in selected:continue
        g.SCENES[key]=None;g.CURRENT_SCENE=key;g.INSTANCE_COUNTS.clear();g.OBJECTS.clear()
        builder(theme)
        if builder!=s.extra_scene:s.enrich(theme)
        objects=list(g.OBJECTS)
        for i,obj in enumerate(objects):
            if 'sceneops_id' not in obj:obj['sceneops_id']=f'{g.PACK}/{key}/detail-{i}'
        bpy.context.view_layer.update()
        saved=[]
        if theme=='pbr-workshop':
            for name,metallic,roughness in [('copper',.85,.28),('metal',.92,.3),('cream',0,.45),('wood_light',0,.6)]:
                node=next(n for n in g.mat(name).node_tree.nodes if n.type=='BSDF_PRINCIPLED')
                saved.append((node,node.inputs['Metallic'].default_value,node.inputs['Roughness'].default_value))
                node.inputs['Metallic'].default_value=metallic;node.inputs['Roughness'].default_value=roughness
        record=emit(key,label,'场景 · '+style,objects,
          f'{style}主题，包含人物、分件设施与环境细节。适用方向：{genres}。静态搭建资产；玩法、骨骼动画、碰撞及导航需在项目中制作。',
          'scene',[(0,-6,.12),(1,-4,.12)])
        record['reusable_asset_ids']=[f'{g.PACK}-{asset}' for asset in g.INSTANCE_COUNTS]
        record['art_style']='体素' if theme=='voxel-village' else '纸艺' if theme=='paper-garden' else 'PBR材质' if theme=='pbr-workshop' else '低多边形'
        record['game_genres']=genres.split('、')
        additions.append(record)
        for node,metallic,roughness in saved:
            node.inputs['Metallic'].default_value=metallic;node.inputs['Roughness'].default_value=roughness
        for obj in objects:bpy.data.objects.remove(obj,do_unlink=True)
        print('DETAILED_SCENE',key,record['triangle_count'],flush=True)
    updated={entry['asset_id']:entry for entry in additions}
    entries=[updated.pop(entry['asset_id'],entry) for entry in document['entries']]
    document['entries']=entries+list(updated.values());document['version']=4
    counts={kind:sum(entry['kind']==kind for entry in document['entries']) for kind in ['scene','prop','character']}
    document['description']=f"{counts['scene']} 套场景、{counts['prop']} 件建筑与物件、{counts['character']} 个角色；提供跨场景复用资产，以及体素、纸艺与 PBR 材质示例。每项附生成提示词。"
    (BASE/'catalog.json').write_text(json.dumps(document,ensure_ascii=False,indent=2)+'\n')
    print('DETAILED_COMPLETE',counts,flush=True)

if __name__=='__main__':main()
