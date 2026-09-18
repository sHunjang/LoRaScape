"""
correction_hook.py 검증 테스트임. 실제 ML 모델은 없어서, 인터페이스가 의도대로
동작하는지(모델 없으면 통과, 모델 있으면 보정값 반영)만 확인함.
"""
from lorascape.core.correction_hook import (
    apply_correction,
    CorrectionFeatures,
    CorrectionModel,
)


def _make_features():
    return CorrectionFeatures(
        distance_km=1.5,
        elevation_diff_m=10.0,
        terrain_std_m=5.0,
        is_los=True,
        diffraction_loss_db=0.0,
        environment="urban",
    )


def test_apply_correction_passthrough_when_no_model():
    """모델이 없으면 원래 path loss 값이 그대로 나와야 함."""
    features = _make_features()
    result = apply_correction(130.0, features, model=None)
    assert result == 130.0


class _FakeCorrectionModel:
    """테스트용 가짜 보정 모델임. 항상 +5dB를 더하는 단순한 구현."""
    def predict(self, features: CorrectionFeatures) -> float:
        return 5.0


def test_apply_correction_adds_model_output_when_model_present():
    """모델이 있으면 predict() 결과가 path loss에 더해져야 함."""
    features = _make_features()
    model = _FakeCorrectionModel()
    result = apply_correction(130.0, features, model=model)
    assert result == 135.0


def test_apply_correction_model_receives_features():
    """모델의 predict()가 넘겨준 features를 실제로 받는지 확인함 (인터페이스 계약 검증)."""
    received = {}

    class _CapturingModel:
        def predict(self, features: CorrectionFeatures) -> float:
            received["features"] = features
            return 0.0

    features = _make_features()
    apply_correction(130.0, features, model=_CapturingModel())

    assert received["features"] is features
    assert received["features"].distance_km == 1.5