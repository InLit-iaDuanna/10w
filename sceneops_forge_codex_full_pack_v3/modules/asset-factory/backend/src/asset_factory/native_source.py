"""Validate and preserve native Blender results before catalog registration."""
import json
import os
import re
import shutil
import struct
from pathlib import Path


def inspect_native_glb(path: Path) -> dict:
    raw = path.read_bytes()
    if len(raw) < 20 or struct.unpack_from('<4sII', raw) != (b'glTF', 2, len(raw)):
        raise ValueError('Blender 导出不是完整 GLB 2 文件。')
    size, kind = struct.unpack_from('<II', raw, 12)
    if kind != 0x4E4F534A or 20 + size > len(raw):
        raise ValueError('GLB 缺少可读取的 JSON chunk。')
    data = json.loads(raw[20:20+size])
    if not data.get('meshes') or not data.get('nodes'):
        raise ValueError('GLB 没有模型内容。')
    for item in [*data.get('buffers', []), *data.get('images', [])]:
        if item.get('uri') and not item['uri'].startswith('data:'):
            raise ValueError('运行 GLB 不能引用外部文件。')
    ids = [n.get('extras', {}).get('sceneops_id') for n in data['nodes']]
    present = [v for v in ids if v]
    if len(present) != len(set(present)):
        raise ValueError('GLB 源节点身份重复。')
    return data


def preserve_native_source(workspace_root, candidate_id, blend_path, glb_path):
    """Copy completed staging artifacts once; publication never points at an open editor file."""
    if re.fullmatch(r"blend_[0-9a-f]{32}", candidate_id) is None:
        raise ValueError("候选 ID 不是服务端登记的身份。")
    root = Path(workspace_root).resolve()
    sources = [Path(blend_path), Path(glb_path)]
    for source in sources:
        if (source.resolve() != source or not source.is_relative_to(root / 'blender')
                or not source.is_file()):
            raise ValueError('源文件不属于登记 Blender 工作区。')
    if sources[0].read_bytes()[:7] != b'BLENDER':
        raise ValueError('源文件不是 Blender 文件。')
    inspect_native_glb(sources[1])
    outputs = [root / 'assets' / 'blender' / (candidate_id + '.blend'),
               root / 'public' / 'sceneops-assets' / (candidate_id + '.glb')]
    for source, target in zip(sources, outputs):
        parent = root
        for part in target.relative_to(root).parts[:-1]:
            parent = parent / part
            if parent.is_symlink():
                raise ValueError('资产输出目录不能是符号链接。')
            parent.mkdir(exist_ok=True)
        if target.exists() or target.is_symlink():
            if target.is_symlink() or not target.is_file() or target.read_bytes() != source.read_bytes():
                raise ValueError('已有候选文件不同，保留双方内容，不能覆盖。')
            continue
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, 'wb') as stream, source.open('rb') as original:
            shutil.copyfileobj(original, stream)
    return {'blend_path': str(outputs[0]), 'preview_path': str(outputs[1]),
            'project_relative_path': outputs[1].relative_to(root).as_posix()}
