import sys
import unittest
from pathlib import Path


ADDON_ROOT = Path(__file__).resolve().parents[1] / "addon"
sys.path.insert(0, str(ADDON_ROOT))

from sceneops_forge_blender.addon_helpers import (  # noqa: E402
    bounding_box_geometry,
    material_records,
)


class Material(dict):
    def __init__(self, name, sceneops_id=None):
        super().__init__()
        self.name = name
        if sceneops_id:
            self["sceneops_id"] = sceneops_id


class AddonHelperTests(unittest.TestCase):
    def test_bounding_box_geometry_builds_six_faces_from_eight_corners(self):
        corners = [
            (-1, -2, -3),
            (-1, -2, 3),
            (-1, 2, 3),
            (-1, 2, -3),
            (1, -2, -3),
            (1, -2, 3),
            (1, 2, 3),
            (1, 2, -3),
        ]
        vertices, faces = bounding_box_geometry(corners)
        self.assertEqual(vertices, corners)
        self.assertEqual(len(faces), 6)
        self.assertEqual({index for face in faces for index in face}, set(range(8)))

    def test_material_records_preserve_names_and_optional_stable_ids(self):
        records = material_records(
            [Material("Key Brass", "mat_key_brass"), None, Material("Scratch")]
        )
        self.assertEqual(
            records,
            [
                {"material_id": "mat_key_brass", "name": "Key Brass"},
                {"material_id": None, "name": "Scratch"},
            ],
        )


if __name__ == "__main__":
    unittest.main()
