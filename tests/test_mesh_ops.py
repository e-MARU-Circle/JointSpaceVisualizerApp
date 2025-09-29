import pyvista as pv
import pytest

from app.logging_config import configure_logging
from app.services import (
    MeshOperationError,
    compute_distance,
    create_custom_colormap,
    save_colored_mesh,
)

configure_logging()


def _shifted_spheres():
    source = pv.Sphere(radius=0.5, center=(0.0, 0.0, 0.0))
    target = pv.Sphere(radius=0.5, center=(0.0, 0.0, 2.0))
    return source, target


def test_create_custom_colormap_range():
    lut = create_custom_colormap()
    assert pytest.approx(lut.scalar_range[0]) == 0.0
    assert pytest.approx(lut.scalar_range[1]) == 5.0


def test_compute_distance_produces_distance_array():
    source, target = _shifted_spheres()
    result, min_distance = compute_distance(source, target)

    assert 'Distance' in result.point_data
    assert min_distance is not None
    assert pytest.approx(min_distance, rel=1e-2) == 1.0


def test_save_colored_mesh(tmp_path):
    source, target = _shifted_spheres()
    result, _ = compute_distance(source, target)
    lut = create_custom_colormap()

    output_path = tmp_path / "colored.ply"
    save_colored_mesh(result, lut, str(output_path))

    assert output_path.exists()


def test_save_colored_mesh_missing_distance(tmp_path):
    mesh = pv.Sphere(radius=0.5)
    lut = create_custom_colormap()
    output_path = tmp_path / "colored_missing.ply"

    with pytest.raises(MeshOperationError):
        save_colored_mesh(mesh, lut, str(output_path))
