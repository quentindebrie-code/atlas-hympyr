import math

import numpy as np
import pytest

from atlas_hympyr import geo


def test_haversine_toulouse_paris():
    # Toulouse -> Paris ~ 588 km à vol d'oiseau
    d = geo.haversine_km(43.6047, 1.4442, 48.8566, 2.3522)
    assert 580 < float(d) < 596


def test_area_one_degree_cell_at_45n():
    ring = [[0, 45], [0.1, 45], [0.1, 45.1], [0, 45.1], [0, 45]]
    area, lon, lat = geo.geometry_area_centroid({"type": "Polygon", "coordinates": [ring]})
    expected = 0.1 * 111.32 * math.cos(math.radians(45.05)) * 0.1 * 110.574
    assert area == pytest.approx(expected, rel=0.01)
    assert lon == pytest.approx(0.05, abs=1e-3)
    assert lat == pytest.approx(45.05, abs=1e-3)


def test_area_with_hole_and_multipolygon():
    outer = [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]
    hole = [[0.25, 0.25], [0.75, 0.25], [0.75, 0.75], [0.25, 0.75], [0.25, 0.25]]
    full, _, _ = geo.geometry_area_centroid({"type": "Polygon", "coordinates": [outer]})
    holed, _, _ = geo.geometry_area_centroid({"type": "Polygon", "coordinates": [outer, hole]})
    assert holed == pytest.approx(full * 0.75, rel=0.02)
    multi, _, _ = geo.geometry_area_centroid({"type": "MultiPolygon", "coordinates": [[outer], [outer]]})
    assert multi == pytest.approx(full * 2, rel=1e-6)


def test_unsupported_geometry():
    with pytest.raises(ValueError):
        geo.geometry_area_centroid({"type": "Point", "coordinates": [0, 0]})


def test_sinuosity_straight_line_is_zero():
    coords = [(1.0 + i * 0.001, 43.0) for i in range(100)]
    assert geo.sinuosity_deg_per_km(coords) == pytest.approx(0.0, abs=1e-6)


def test_sinuosity_zigzag_greater_than_gentle_curve():
    # tracé en lacets vs tracé presque droit : mêmes longueurs approximatives
    t = np.linspace(0, 1, 400)
    straight = list(zip(1.0 + 0.2 * t, 43.0 + 0.0005 * np.sin(6 * t), strict=True))
    zigzag = list(zip(1.0 + 0.2 * t, 43.0 + 0.01 * np.sin(120 * t), strict=True))
    assert geo.sinuosity_deg_per_km(zigzag) > 10 * geo.sinuosity_deg_per_km(straight)


def test_sinuosity_independent_of_vertex_density():
    t_dense = np.linspace(0, 1, 2000)
    t_sparse = np.linspace(0, 1, 500)

    def path(t):
        return list(zip(1.0 + 0.2 * t, 43.0 + 0.005 * np.sin(40 * t), strict=True))

    a = geo.sinuosity_deg_per_km(path(t_dense))
    b = geo.sinuosity_deg_per_km(path(t_sparse))
    assert a == pytest.approx(b, rel=0.05)


def test_cumulative_ascent_filters_noise():
    assert geo.cumulative_ascent([0, 10, 0, 10]) == 20
    assert geo.cumulative_ascent([0, 1, 0, 1, 0, 1]) == 0
    assert geo.cumulative_ascent([5]) == 0
    assert geo.cumulative_ascent([0, float("nan"), 12]) == 12
