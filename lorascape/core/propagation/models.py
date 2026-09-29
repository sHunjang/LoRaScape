# lorascape/core/propagation/models.py
"""
기본 경로손실 모델(Song's Model / COST-231 Hata) 선택용 진입점임.
GW-Node 링크 계산, 히트맵, 보고서가 전부 이 함수를 거치게 해서, 설정창에서 고른 모델이
모든 계산에 똑같이 적용되게 함 (모델 이름은 설정 파일의 propagation_model 값).
지형 회절손실(Deygout)은 모델과 무관하게 그 위에 더해짐.
"""
from lorascape.core.propagation import cost231, song_model

DEFAULT_MODEL = "song"

# (설정 파일에 저장되는 키, 화면에 보이는 이름) - 설정창 콤보박스와 보고서가 같이 씀
PROPAGATION_MODELS = [
    ("song", "Song's Model (기본)"),
    ("cost231", "COST-231 Hata"),
]

_FUNCS = {
    "song": song_model.path_loss,
    "cost231": cost231.path_loss,
}

# 설정창에서 COST-231을 골랐을 때 보여줄 안내문임
COST231_NOTE = (
    "COST-231 Hata의 원래 적용 범위는 주파수 1500~2000MHz, 기지국 안테나 30~200m, 거리 1~20km입니다. "
    "이 프로젝트의 조건(920MHz, 낮은 안테나, 수십m~수km)은 범위 밖이라 값을 외삽해서 씁니다. "
    "절대값보다 Song's Model과의 비교용으로 보세요."
)


def model_label(model: str) -> str:
    """모델 키의 화면 표시 이름을 반환함 (모르는 키는 키 그대로)."""
    return dict(PROPAGATION_MODELS).get(model, model)


def base_path_loss(model: str, fc_mhz: float, hb_m: float, hm_m: float, d_km: float,
                   environment: str = "urban") -> float:
    """
    선택한 모델로 기본 경로손실(dB)을 계산함. 모르는 모델 이름은 조용히 기본 모델로 대체하지 않고
    에러를 냄 - 설정이 잘못됐는데도 다른 모델로 계산한 결과를 믿게 되는 게 더 위험해서임.
    """
    try:
        fn = _FUNCS[model]
    except KeyError:
        raise ValueError(f"알 수 없는 전파 모델: {model!r} (가능한 값: {', '.join(_FUNCS)})") from None
    return fn(fc_mhz, hb_m, hm_m, d_km, environment)
