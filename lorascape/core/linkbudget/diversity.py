# lorascape/core/linkbudget/diversity.py
"""
매크로 다이버시티(하나의 Node를 여러 GW가 동시에 수신하는 경우) 계산과
Pure ALOHA 기반 트래픽 충돌 분석(PDR) 계산임.
"""
import math


def macro_diversity_combine(rx_powers_dbm: list) -> float:
    """
    여러 GW가 같은 Node 신호를 동시에 수신했을 때, 합산 이득을 계산함.
    dB는 로그 스케일이라 그냥 더하면 안 되고, 반드시 선형(mW) 단위로 바꿔서 합산한 다음
    다시 dB로 환산해야 함 (문서 요구사항 그대로).
    """
    if not rx_powers_dbm:
        raise ValueError("rx_powers_dbm은 최소 1개 이상의 값이 있어야 함")

    # dBm -> mW 변환: mW = 10^(dBm/10)
    total_mw = sum(10 ** (p / 10) for p in rx_powers_dbm)

    # mW -> dBm 변환: dBm = 10*log10(mW)
    return 10 * math.log10(total_mw)


def aloha_pdr(normalized_load_g: float) -> float:
    """
    Pure ALOHA 모델 기반 PDR(패킷 성공 전달률) 계산함.
    PDR = e^(-2G)   (G = 정규화된 트래픽 부하)

    G가 커질수록(트래픽이 몰릴수록) 충돌 확률이 높아져서 PDR이 지수적으로 떨어지는 게 핵심임.
    """
    return math.exp(-2 * normalized_load_g)