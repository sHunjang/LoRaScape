# lorascape/core/correction_hook.py
"""
Song's Model 계산값을 보정하는 확장 포인트임 (문서 6번 요구사항).

지금 당장은 보정 모델을 학습시킬 데이터(Song's 계산값 vs 실측/ATDI 비교 데이터)가
부족해서 실제 ML 로직은 안 넣음. 대신 "나중에 트리 기반 회귀모델(랜덤포레스트/XGBoost)을
끼워 넣을 자리"만 미리 만들어둠.

핵심 설계: Song's Model이 회사 솔루션의 핵심이고, AI는 그걸 대체하는 게 아니라
'계산 끝난 값에 보정치를 더하는' 후처리 레이어로만 존재함. 그래서 인터페이스도
"입력 특성 받아서 보정값(dB) 하나 돌려주는" 아주 단순한 형태로 감.
"""
from dataclasses import dataclass, field
from typing import Optional, Protocol


@dataclass
class CorrectionFeatures:
    """
    보정 모델에 넣을 입력 특성들임. 전부 core 계산 과정에서 이미 나오는 중간값들이라
    별도로 새로 계산할 필요 없이, gw_placement.py 같은 호출부에서 그대로 채워서 넘기면 됨.
    """
    distance_km: float
    elevation_diff_m: float          # GW-Node 간 고도차 (지형 기복 정도)
    terrain_std_m: float             # 경로상 DSM 표준편차 (주변 건물밀도 근사치)
    is_los: bool                     # 완전 LOS 여부
    diffraction_loss_db: float       # Deygout이 계산한 회절 손실값
    environment: str                 # Song's Model 환경 분류 (dense_urban/urban/suburban/open)


class CorrectionModel(Protocol):
    """
    보정 모델이 갖춰야 할 최소 인터페이스임. 실제 모델(랜덤포레스트든 XGBoost든)이
    이 predict 메서드 하나만 구현하면 apply_correction()에 바로 꽂아 쓸 수 있음.
    """
    def predict(self, features: CorrectionFeatures) -> float:
        ...


def apply_correction(
    path_loss_db: float,
    features: CorrectionFeatures,
    model: Optional[CorrectionModel] = None,
) -> float:
    """
    경로손실 계산의 최종 반환 직전에 호출하는 함수임 (문서 6번 요구사항 그대로).

    model이 None이면(=아직 학습된 보정 모델이 없으면) 그냥 원래 값을 그대로 통과시킴.
    나중에 데이터 쌓여서 모델이 생기면, 호출부에서 model 인자만 넘겨주면 되고
    이 함수 자체나 gw_placement.py 쪽 호출 코드는 안 건드려도 됨.
    """
    if model is None:
        return path_loss_db  # 보정 모델 없음 -> 그냥 통과

    correction_db = model.predict(features)
    return path_loss_db + correction_db