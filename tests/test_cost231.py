"""COST-231 Hata 모델과 모델 선택 진입점 검증 테스트임."""
import math
import pytest

from lorascape.core.propagation import cost231, song_model
from lorascape.core.propagation.cost231 import path_loss
from lorascape.core.propagation.models import (
    base_path_loss, model_label, PROPAGATION_MODELS, DEFAULT_MODEL,
)


def test_known_value_from_hand_calculation():
    """f=1800MHz, hb=30m, hm=1.5m, d=1km, 중소도시: 3GPP 식을 손으로 풀면 136.197 dB임."""
    assert path_loss(1800, 30, 1.5, 1.0, "urban") == pytest.approx(136.197, abs=0.005)


def test_dense_urban_is_exactly_3db_above_urban():
    assert path_loss(920, 15, 1.5, 0.7, "dense_urban") - path_loss(920, 15, 1.5, 0.7, "urban") == pytest.approx(3.0)


def test_loss_grows_by_expected_slope_per_decade_of_distance():
    hb = 15.0
    slope = path_loss(920, hb, 1.5, 10.0) - path_loss(920, hb, 1.5, 1.0)
    assert slope == pytest.approx(44.9 - 6.55 * math.log10(hb))


def test_loss_increases_with_distance_and_decreases_with_base_height():
    assert path_loss(920, 15, 1.5, 2.0) > path_loss(920, 15, 1.5, 0.5)
    assert path_loss(920, 5, 1.5, 1.0) > path_loss(920, 30, 1.5, 1.0)


def test_suburban_and_open_corrections_match_hata_formulas():
    urban = path_loss(920, 15, 1.5, 1.0, "urban")
    lf = math.log10(920)
    assert path_loss(920, 15, 1.5, 1.0, "suburban") == pytest.approx(urban - 2 * math.log10(920 / 28) ** 2 - 5.4)
    assert path_loss(920, 15, 1.5, 1.0, "open") == pytest.approx(urban - 4.78 * lf ** 2 + 18.33 * lf - 40.94)


def test_environment_ordering_is_dense_urban_worst_open_best():
    vals = [path_loss(920, 15, 1.5, 1.0, e) for e in ("dense_urban", "urban", "suburban", "open")]
    assert vals == sorted(vals, reverse=True)


def test_invalid_environment_raises():
    with pytest.raises(ValueError):
        path_loss(920, 15, 1.5, 1.0, "underwater")


@pytest.mark.parametrize("args", [(0, 15, 1.5, 1.0), (920, 0, 1.5, 1.0), (920, 15, 0, 1.0), (920, 15, 1.5, 0)])
def test_non_positive_inputs_raise(args):
    with pytest.raises(ValueError):
        path_loss(*args)


# ── 모델 선택 진입점 ──

def test_base_path_loss_dispatches_to_each_model():
    args = (920.0, 15.0, 1.5, 0.8, "urban")
    assert base_path_loss("song", *args) == song_model.path_loss(*args)
    assert base_path_loss("cost231", *args) == cost231.path_loss(*args)


def test_the_two_models_actually_give_different_results():
    args = (920.0, 15.0, 1.5, 0.8, "urban")
    assert base_path_loss("song", *args) != pytest.approx(base_path_loss("cost231", *args), abs=0.01)


def test_unknown_model_raises_instead_of_silently_using_default():
    with pytest.raises(ValueError):
        base_path_loss("okumura", 920.0, 15.0, 1.5, 0.8, "urban")


def test_default_model_is_listed_and_labels_resolve():
    keys = [k for k, _ in PROPAGATION_MODELS]
    assert DEFAULT_MODEL in keys and set(keys) == {"song", "cost231"}
    assert model_label("cost231") == "COST-231 Hata"
    assert model_label("nope") == "nope"
