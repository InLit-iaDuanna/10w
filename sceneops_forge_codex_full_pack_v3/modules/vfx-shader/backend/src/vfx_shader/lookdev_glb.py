"""GLB container operations preserve binary geometry and explicit object identity."""
import json
import struct
from uuid import uuid4
from .lookdev_models import LookdevError


def read_glb(data):
    if len(data) < 20 or data[:4] != b'glTF' or struct.unpack_from('<II', data, 4) != (2, len(data)):
        raise LookdevError('INVALID_GLB', '文件不是完整的 GLB 2 模型。', 422)
    chunks, offset = [], 12
    while offset < len(data):
        if offset + 8 > len(data):
            raise LookdevError('INVALID_GLB', '模型数据块头不完整。', 422)
        length, kind = struct.unpack_from('<II', data, offset)
        offset += 8
        if offset + length > len(data):
            raise LookdevError('INVALID_GLB', '模型数据块不完整。', 422)
        chunks.append((kind, data[offset:offset + length]))
        offset += length
    if not chunks or chunks[0][0] != 0x4E4F534A:
        raise LookdevError('INVALID_GLB', '模型缺少 JSON 数据。', 422)
    try:
        return json.loads(chunks[0][1]), chunks[1:]
    except ValueError as error:
        raise LookdevError('INVALID_GLB', '模型 JSON 无效。', 422) from error


def write_glb(document, chunks):
    data = json.dumps(document, separators=(',', ':'), ensure_ascii=False).encode()
    data += b' ' * (-len(data) % 4)
    body = b''.join(struct.pack('<II', len(value), kind) + value for kind, value in [(0x4E4F534A, data), *chunks])
    return b'glTF' + struct.pack('<II', 2, len(body) + 12) + body


def normalize_glb(data):
    document, chunks = read_glb(data)
    for node in document.get('nodes', []):
        if 'mesh' in node or 'KHR_lights_punctual' in node.get('extensions', {}):
            node.setdefault('extras', {}).setdefault('sceneops_id', 'obj_' + uuid4().hex)
    for material in document.get('materials', []):
        material.setdefault('extras', {}).setdefault('lookdevSourceMaterialId', 'material_' + uuid4().hex)
    for mesh in document.get('meshes', []):
        if len(mesh.get('primitives', [])) > 1:
            for primitive in mesh['primitives']:
                primitive.setdefault('extras', {}).setdefault('sceneops_id', 'obj_' + uuid4().hex)
    identities = set()
    for node in document.get('nodes', []):
        if 'mesh' not in node:
            continue
        parent_id = node['extras']['sceneops_id']
        if not isinstance(parent_id, str) or not parent_id.strip() or parent_id != parent_id.strip():
            raise LookdevError('INVALID_IDENTITY', '模型对象身份无效。', 422)
        primitives = document['meshes'][node['mesh']].get('primitives', [])
        node_ids = [parent_id] if len(primitives) <= 1 else [parent_id + ':' + item['extras']['sceneops_id'] for item in primitives]
        for identity in node_ids:
            if identity in identities:
                raise LookdevError('DUPLICATE_IDENTITY', '模型包含重复对象身份，请先修复源资产。', 422)
            identities.add(identity)
    return write_glb(document, chunks)


def apply_pbr(data, state):
    """Change only material assignments and properties; geometry bytes stay intact."""
    from copy import deepcopy
    document, chunks = read_glb(data)
    objects = {item['id']: item for item in state['objects']}
    materials = {item['id']: item for item in state['materials']}
    seen = set()
    document.setdefault('materials', [])
    for node in document.get('nodes', []):
        if 'mesh' not in node:
            continue
        original = document['meshes'][node['mesh']]
        mesh = deepcopy(original)
        node_id = node['extras']['sceneops_id']
        for slot, primitive in enumerate(mesh['primitives']):
            object_id = node_id if len(mesh['primitives']) == 1 else node_id + ':' + primitive['extras']['sceneops_id']
            selected = objects.get(object_id)
            if selected is None:
                raise LookdevError('IDENTITY_MISMATCH', '文档未绑定模型对象：'+object_id, 422)
            seen.add(object_id)
            binding = next((item for item in selected['materialSlots'] if item['slot'] == 0), None)
            if binding is None:
                raise LookdevError('MATERIAL_SLOT_MISSING', '文档缺少模型对象的材质槽：'+object_id, 422)
            state_material = materials[binding['materialId']]
            source = deepcopy(document['materials'][primitive['material']]) if 'material' in primitive else {}
            if source.get('extras', {}).get('lookdevSourceMaterialId') != binding['sourceMaterialId']:
                raise LookdevError('MATERIAL_SLOT_MISMATCH', '模型材质槽身份已变化：'+object_id+':'+binding['sourceMaterialId'], 422)
            source.setdefault('extras', {})['lookdevMaterialId'] = state_material['id']
            patch_material(source, state_material)
            primitive['material'] = len(document['materials'])
            document['materials'].append(source)
        node['mesh'] = len(document['meshes'])
        document['meshes'].append(mesh)
    if seen != set(objects):
        raise LookdevError('IDENTITY_MISMATCH', '源模型缺少文档对象：'+', '.join(sorted(set(objects)-seen)), 422)
    used = set(document.get('extensionsUsed', []))
    for material in document['materials']:
        used.update(material.get('extensions', {}))
    if used:
        document['extensionsUsed'] = sorted(used)
    return write_glb(document, chunks)


def patch_material(material, state):
    def linear_color(value):
        rgb = [int(value[index:index + 2], 16) / 255 for index in (1, 3, 5)]
        return [channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4 for channel in rgb]
    pbr = material.setdefault('pbrMetallicRoughness', {})
    color = pbr.get('baseColorFactor', [1, 1, 1, 1])[:3] if state.get('colorOverrides', {}).get('baseColor') is False else linear_color(state['baseColor'])
    pbr.update(baseColorFactor=[*color, state['opacity']], metallicFactor=state['metalness'], roughnessFactor=state['roughness'])
    material['name'] = state['name']
    if state.get('colorOverrides', {}).get('emissive') is not False:
        material['emissiveFactor'] = linear_color(state['emissive'])
    material['alphaMode'] = state['alphaMode']
    material['alphaCutoff'] = state['alphaCutoff']
    if 'normalTexture' in material:
        material['normalTexture']['scale'] = state['normalScale']
    extensions = material.setdefault('extensions', {})
    extensions['KHR_materials_emissive_strength'] = {'emissiveStrength': state['emissiveIntensity']}
    extensions.setdefault('KHR_materials_transmission', {})['transmissionFactor'] = state['transmission']
    extensions.setdefault('KHR_materials_ior', {})['ior'] = state['ior']
    extensions.setdefault('KHR_materials_clearcoat', {}).update(clearcoatFactor=state['clearcoat'], clearcoatRoughnessFactor=state['clearcoatRoughness'])
