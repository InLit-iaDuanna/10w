"""Small, fixed luminance samples: no renderer, model or remote service."""

from .lab_contracts import LabImage

# Each character is one luminance sample. Both candidates preserve the door.
ROOM = (
    "1111111111111111",
    "1222222222222221",
    "1223333333333221",
    "1233444444333221",
    "1233555555333221",
    "1233566665333221",
    "1233566665333221",
    "1233566665333221",
    "1233566675333221",
    "1233566665333221",
    "1233566665333221",
    "1233555555333221",
    "1223333333333221",
    "1222222222222221",
    "1111111111111111",
    "0000000000000000",
)


def sample_images():
    base = [int(char) * 28 for row in ROOM for char in row]
    warm, bright = list(base), list(base)
    for y in range(3, 11):
        for x in range(10, 14):
            index = y * 16 + x
            warm[index] = min(255, base[index] + 28)
            bright[index] = min(255, base[index] + 56)
    depth = [224 - (y * 8) for y in range(16) for _ in range(16)]
    normal = [96 if x < 5 else 160 for _ in range(16) for x in range(16)]
    ids = [220 if 5 <= x <= 8 and 5 <= y <= 10 else 30
           for y in range(16) for x in range(16)]
    values = {
        "beauty": (base, "原始 Beauty"), "depth": (depth, "Depth 示例"),
        "normal": (normal, "Normal 示意（单通道）"),
        "albedo": (base, "Albedo 示例"), "object_id": (ids, "Object ID 掩码"),
        "material_id": (ids, "Material ID 示例"),
        "warm": (warm, "A · 柔和补光"), "bright": (bright, "B · 更亮补光"),
    }
    return {key: LabImage(width=16, height=16, values=pixels, label=label)
            for key, (pixels, label) in values.items()}


def door_mask():
    return [5 <= x <= 8 and 5 <= y <= 10 for y in range(16) for x in range(16)]
