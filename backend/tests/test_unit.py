"""Unit tests for haversine_mi, rideshare_estimates, and the fit-score formula."""
import math
import pytest

from app.scrapers.base import haversine_mi
from app.scrapers.transport import rideshare_estimates


# ---------------------------------------------------------------------------
# haversine_mi
# ---------------------------------------------------------------------------

class TestHaversineMi:
    def test_same_point_is_zero(self):
        assert haversine_mi(40.7128, -74.0060, 40.7128, -74.0060) == 0.0

    def test_quarter_circle_along_equator(self):
        # (0,0) → (0,90): a quarter of Earth's circumference
        expected = math.pi / 2 * 3958.8
        assert haversine_mi(0, 0, 0, 90) == pytest.approx(expected, rel=1e-6)

    def test_half_circle_along_equator(self):
        # (0,0) → (0,180): antipodal along the equator = half circumference
        expected = math.pi * 3958.8
        assert haversine_mi(0, 0, 0, 180) == pytest.approx(expected, rel=1e-6)

    def test_nyc_to_la(self):
        dist = haversine_mi(40.7128, -74.0060, 34.0522, -118.2437)
        assert dist == pytest.approx(2446, rel=0.01)

    def test_symmetric(self):
        d1 = haversine_mi(40.7128, -74.0060, 34.0522, -118.2437)
        d2 = haversine_mi(34.0522, -118.2437, 40.7128, -74.0060)
        assert d1 == pytest.approx(d2)

    def test_returns_float(self):
        assert isinstance(haversine_mi(0, 0, 1, 1), float)


# ---------------------------------------------------------------------------
# rideshare_estimates
# ---------------------------------------------------------------------------

class TestRidshareEstimates:
    def test_returns_two_services(self):
        result = rideshare_estimates(40.7128, -74.0060, 34.0522, -118.2437)
        assert len(result) == 2
        assert {r["service"] for r in result} == {"Uber", "Lyft"}

    def test_required_keys(self):
        result = rideshare_estimates(0, 0, 0, 0)
        expected_keys = {"service", "est_low", "est_high", "distance_mi", "deeplink", "note"}
        for entry in result:
            assert expected_keys <= entry.keys()

    def test_est_low_less_than_est_high(self):
        result = rideshare_estimates(40.7128, -74.0060, 34.0522, -118.2437)
        for entry in result:
            assert entry["est_low"] < entry["est_high"]

    def test_zero_distance_base_fares(self):
        result = rideshare_estimates(0, 0, 0, 0)
        uber = next(r for r in result if r["service"] == "Uber")
        lyft = next(r for r in result if r["service"] == "Lyft")
        assert uber["est_low"] == pytest.approx(3.5, abs=0.01)
        assert uber["est_high"] == pytest.approx(5.0, abs=0.01)
        assert lyft["est_low"] == pytest.approx(3.0, abs=0.01)
        assert lyft["est_high"] == pytest.approx(4.8, abs=0.01)

    def test_fare_grows_with_distance(self):
        near = rideshare_estimates(0, 0, 0, 0.1)
        far = rideshare_estimates(0, 0, 0, 10)
        uber_near = next(r for r in near if r["service"] == "Uber")
        uber_far = next(r for r in far if r["service"] == "Uber")
        assert uber_far["est_low"] > uber_near["est_low"]
        assert uber_far["est_high"] > uber_near["est_high"]

    def test_distance_mi_matches_haversine(self):
        result = rideshare_estimates(40.7128, -74.0060, 34.0522, -118.2437)
        expected = round(haversine_mi(40.7128, -74.0060, 34.0522, -118.2437), 1)
        for entry in result:
            assert entry["distance_mi"] == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Fit-score formula  (mirrors search_festivals() in app/main.py)
# ---------------------------------------------------------------------------

def _fit(genre_hit: bool, in_window: bool, dist_ok: bool, runtime_ok: bool, fee_ok: bool) -> int:
    """Direct mirror of the scoring formula in search_festivals()."""
    return int(35 * genre_hit + 25 * in_window + 20 * dist_ok + 10 * runtime_ok + 10 * fee_ok)


class TestFitScore:
    def test_perfect_match_is_100(self):
        assert _fit(True, True, True, True, True) == 100

    def test_runtime_miss_is_90(self):
        assert _fit(True, True, True, False, True) == 90

    def test_fee_miss_is_90(self):
        assert _fit(True, True, True, True, False) == 90

    def test_runtime_and_fee_miss_is_80(self):
        # Minimum score for a festival that passes the radius/genre/window filter
        assert _fit(True, True, True, False, False) == 80

    def test_individual_weights(self):
        assert _fit(True, False, False, False, False) == 35   # genre
        assert _fit(False, True, False, False, False) == 25   # in_window
        assert _fit(False, False, True, False, False) == 20   # dist
        assert _fit(False, False, False, True, False) == 10   # runtime
        assert _fit(False, False, False, False, True) == 10   # fee

    def test_all_false_is_zero(self):
        assert _fit(False, False, False, False, False) == 0
