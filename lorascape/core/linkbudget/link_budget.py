# lorascape/core/linkbudget/link_budget.py
"""
링크 버짓(수신전력) 계산과 SNR, ADR(SF 자동결정) 로직임.
Song's Model / Deygout에서 나온 PL(경로손실) 값을 받아서
"이 Node가 이 GW에 실제로 연결 가능한가"를 판정하는 다음 단계 계산임.
"""
import math

# SF별 SNR 임계값(dB)임. 문서에 "대략적인 기준, 검증 필요"라고 명시되어 있어서
# 실측/데이터시트 값으로 나중에 교체될 수 있는 상수로 분리해둠.
SF_SNR_THRESHOLDS_DB = {
    7: -7.5,
    8: -10.0,
    9: -12.5,
    10: -15.0,
    11: -17.5,
    12: -20.0,
}


def rx_power_dbm(
    tx_power_dbm: float,
    gw_antenna_gain_dbi: float,
    gw_cable_loss_db: float,
    path_loss_db: float,
    node_antenna_gain_dbi: float,
    node_cable_loss_db: float,
    indoor_penetration_loss_db: float = 0.0,
) -> float:
    """
    수신전력 Pr(dBm) 계산함.
    Pr = Pt + Gt - Lt - PL + Gr - Lr - 실내투과손실
    실내투과손실은 옥외 설치가 기본이라 기본값 0으로 두고, 필요할 때만 값 넣으면 됨.
    """
    return (
        tx_power_dbm
        + gw_antenna_gain_dbi
        - gw_cable_loss_db
        - path_loss_db
        + node_antenna_gain_dbi
        - node_cable_loss_db
        - indoor_penetration_loss_db
    )


def thermal_noise_dbm(bandwidth_hz: float) -> float:
    """
    열잡음(dBm) 계산함. 열잡음 = -174 + 10*log10(대역폭_Hz)
    -174dBm/Hz는 상온(290K) 기준 열잡음 전력밀도의 표준값임 (물리 상수 성격이라 하드코딩).
    """
    return -174.0 + 10.0 * math.log10(bandwidth_hz)


def snr_db(rx_power_dbm_value: float, bandwidth_hz: float, receiver_noise_figure_db: float) -> float:
    """
    SNR(dB) 계산함. SNR = Pr - (열잡음 + 수신기잡음지수)
    수신기잡음지수(NF)는 실제 GW/트랜시버 데이터시트 값을 써야 정확한데,
    지금은 호출부에서 넘겨받는 파라미터로 처리함 (하드코딩 안 함).
    """
    noise_floor = thermal_noise_dbm(bandwidth_hz) + receiver_noise_figure_db
    return rx_power_dbm_value - noise_floor


def select_sf(snr_db_value: float) -> int:
    """
    ADR(SF 자동 결정) 로직임.
    현재 SNR이 만족하는 SF 임계값들 중에서, 가장 낮은 SF(=가장 빠른 전송속도)를 고름.
    -> SF가 낮을수록 임계값이 덜 관대하니(더 높은 SNR 요구), SF를 7부터 오름차순으로 검사해서
       처음으로 조건을 만족하는 SF를 반환하는 방식임.

    연결 자체가 불가능하면(SF12 임계값도 못 만족하면) None을 반환함.
    """
    for sf in sorted(SF_SNR_THRESHOLDS_DB.keys()):  # 7, 8, 9, ..., 12 순서로 검사
        if snr_db_value >= SF_SNR_THRESHOLDS_DB[sf]:
            return sf
    return None  # 어떤 SF로도 연결 불가능한 상태임 (커버리지 밖)