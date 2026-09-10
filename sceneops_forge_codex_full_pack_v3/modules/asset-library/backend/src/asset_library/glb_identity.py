"""Assign missing identities once on explicit first import; existing IDs never change."""
from copy import deepcopy
from uuid import uuid4


def assign_glb_identities(document):
    result = deepcopy(document)
    for collection, key, prefix in [('nodes', 'sceneops_id', 'obj_'),
                                    ('materials', 'lookdevSourceMaterialId', 'material_'),
                                    ('animations', 'sceneops_id', 'clip_')]:
        seen = set()
        for item in result.get(collection, []):
            extras = item.setdefault('extras', {})
            identity = extras.setdefault(key, prefix + uuid4().hex)
            if not isinstance(identity, str) or not identity.strip() or identity != identity.strip() or identity in seen:
                raise ValueError('模型包含无效或重复身份：' + collection)
            seen.add(identity)
    for mesh in result.get('meshes', []):
        for primitive in mesh.get('primitives', []):
            if 'material' not in primitive:
                raise ValueError('模型网格缺少明确材质，先在源模型指定材质。')
            if len(mesh['primitives']) > 1:
                primitive.setdefault('extras', {}).setdefault('sceneops_id', 'obj_' + uuid4().hex)
    return result
