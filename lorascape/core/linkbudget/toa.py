# lorascape/core/linkbudget/toa.py
"""
ToA(Time on Air) 계산 모듈임. LoRa 패킷 하나가 공중에 떠 있는 시간(전송에 걸리는 시간)을
LoRaWAN 표준 공식(Semtech AN1200.13 문서 기반)으로 계산함.

트래픽 용량/충돌 분석(ALOHA 모델)에서 이 ToA 값을 '점유 시간'으로 그대로 씀.
"""
import math


def symbol_duration_s(sf: int, bandwidth_hz: float) -> float:
    """심볼 하나의 전송 시간(초). Ts = 2^SF / BW"""
    return (2 ** sf) / bandwidth_hz


def time_on_air_s(
    payload_bytes: int,
    sf: int,
    bandwidth_hz: float,
    coding_rate: int = 1,        # 1=4/5, 2=4/6, 3=4/7, 4=4/8 (LoRaWAN 기본은 4/5)
    preamble_symbols: int = 8,   # LoRaWAN 기본 프리앰블 심볼 수
    header_enabled: bool = True,  # explicit header 사용 여부 (LoRaWAN은 기본 True)
    low_data_rate_optimize: bool = None,  # None이면 SF/BW로 자동 판단
    crc_enabled: bool = True,
) -> float:
    """
    LoRa 패킷의 총 ToA(초)를 계산함. 공식은 프리앰블 시간 + 페이로드 시간 두 부분으로 나뉨.

    저데이터레이트 최적화(low_data_rate_optimize)는 SF11/12에서 250kHz 미만 대역폭 쓸 때
    자동으로 켜지는 게 LoRaWAN 표준 동작이라, 인자로 안 주면 자동 판단하게 만듦.
    """
    if low_data_rate_optimize is None:
        low_data_rate_optimize = (sf >= 11 and bandwidth_hz < 250_000)

    ts = symbol_duration_s(sf, bandwidth_hz)

    # 프리앰블 시간 = (preamble_symbols + 4.25) * Ts  (표준 공식의 4.25는 동기화용 고정 심볼수)
    t_preamble = (preamble_symbols + 4.25) * ts

    # 페이로드 심볼 수 계산 (표준 공식 그대로)
    de = 1 if low_data_rate_optimize else 0
    h = 0 if header_enabled else 1
    crc = 1 if crc_enabled else 0

    numerator = 8 * payload_bytes - 4 * sf + 28 + 16 * crc - 20 * h
    denominator = 4 * (sf - 2 * de)

    n_payload_symbols = 8 + max(math.ceil(numerator / denominator) * (coding_rate + 4), 0)

    t_payload = n_payload_symbols * ts

    return t_preamble + t_payload