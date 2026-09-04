from __future__ import annotations


BOUNDING_BOX_FACES = (
    (0, 1, 2, 3),
    (4, 7, 6, 5),
    (0, 4, 5, 1),
    (3, 2, 6, 7),
    (0, 3, 7, 4),
    (1, 5, 6, 2),
)


def bounding_box_geometry(bound_box):
    vertices = [tuple(float(coordinate) for coordinate in corner) for corner in bound_box]
    if len(vertices) != 8 or any(len(vertex) != 3 for vertex in vertices):
        raise ValueError("Blender bounding box must contain eight 3D corners")
    return vertices, list(BOUNDING_BOX_FACES)


def material_records(materials):
    return [
        {
            "material_id": material.get("sceneops_id"),
            "name": material.name,
        }
        for material in materials
        if material is not None
    ]
