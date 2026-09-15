"""
Song's Model 기반 SmartCity 전파 손실 계산 모듈임.
core 쪽 코드는 PyQt5 같은 UI 코드를 절대 import하면 안 됨 (계산 로직만 순수하게 유지).
"""
import math

# 환경 분류는 4가지로 고정임. 나중에 DSM 기반 자동분류(environment.py)에서 이 값들을 그대로 씀.
ENV_DENSE_URBAN = "dense_urban"
ENV_URBAN = "urban"
ENV_SUBURBAN = "suburban"
ENV_OPEN = "open"


def basic_path_loss(fc_mhz: float, hb_m: float, d_km: float) -> float:
    """
    기본 경로손실(BPL) 계산 함수임.
    fc_mhz: 반송 주파수 (예: LoRa 920MHz 대역)
    hb_m: GW 안테나 높이 (m 단위, 지면 기준)
    d_km: GW-Node 사이 직선거리 (km 단위. m 아니고 km이니까 헷갈리면 안 됨)

    수식은 문서에서 확정된 그대로 옮긴 거라 임의로 바꾸면 안 되는 부분임.
    """
    return (
        39.25
        + 35.15 * math.log10(fc_mhz)
        - 19.21 * math.log10(hb_m)
        + (42.5 - 5.2 * math.log10(hb_m)) * math.log10(d_km)
    )


def ahm_correction(env: str, hm_m: float, fc_mhz: float) -> float:
    """
    환경별 보정항(ahm) 계산 함수임.
    hm_m: 단말(Node) 안테나 높이. GW 높이(hb_m)랑 다른 변수니까 인자 순서 주의.

    환경별로 계수가 다 다르게 생겨서 if/elif로 분기 처리함.
    나중에 환경 종류 추가될 일 없을 것 같아서 딕셔너리 대신 그냥 조건문으로 짬.
    """
    if env == ENV_DENSE_URBAN:
        return 18.9 * math.log10(hm_m) - 1.29 * math.log10(fc_mhz) - 11.5
    elif env == ENV_URBAN:
        return 18.4 * math.log10(hm_m) - 0.99 * math.log10(fc_mhz) + 2.0
    elif env == ENV_SUBURBAN:
        return 17.2 * math.log10(hm_m) - 0.6 * math.log10(fc_mhz) - 2.7
    elif env == ENV_OPEN:
        # Open 환경은 fc(주파수) 항이 아예 없음. 문서 수식 그대로임 (오타 아님).
        return 17.2 * math.log10(hm_m) + 13
    else:
        # 잘못된 env 문자열이 들어오면 조용히 넘어가지 말고 바로 터뜨림.
        # 이게 있어야 GUI 쪽에서 콤보박스 값 매핑 실수했을 때 바로 잡아낼 수 있음.
        raise ValueError(f"Unknown environment: {env}")


def path_loss(fc_mhz: float, hb_m: float, hm_m: float, d_km: float, env: str) -> float:
    """
    최종 경로손실 PL = BPL - ahm.
    이 함수 하나만 GUI/최적화 로직에서 호출하면 됨. basic_path_loss랑 ahm_correction은
    내부 계산용으로 쪼개둔 거고, 외부에서는 이 함수만 쓰면 되는 구조임.
    """
    bpl = basic_path_loss(fc_mhz, hb_m, d_km)
    ahm = ahm_correction(env, hm_m, fc_mhz)
    return bpl - ahm