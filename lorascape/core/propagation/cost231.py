# lorascape/core/propagation/cost231.py
"""
COST-231 Hata 경로손실 모델임. Song's Model(song_model.py)과 같은 형태(주파수, 기지국 높이,
단말 높이, 거리, 환경)로 호출되게 만들어서 설정창에서 골라 바꿔 쓸 수 있게 함.

기본식 (3GPP TR 25.907 / 43.030의 COST-231 Hata):
  L = 46.3 + 33.9*log10(f) - 13.82*log10(hb) - a(hm) + (44.9 - 6.55*log10(hb))*log10(d) + Cm
  a(hm) = (1.1*log10(f) - 0.7)*hm - (1.56*log10(f) - 0.8)
  Cm    = 0 dB (중소도시, 교외)   /   3 dB (대도시 중심)
  (f: MHz, hb: 기지국 안테나 높이 m, hm: 단말 안테나 높이 m, d: km)

환경 4종 매핑 (Song's Model과 같은 이름을 씀):
  dense_urban -> Cm = 3 dB (대도시)
  urban       -> Cm = 0 dB (중소도시)
  suburban    -> urban 값에서 Hata 교외 보정 적용
  open        -> urban 값에서 Hata 개활지 보정 적용
  COST-231 자체에는 교외/개활지 식이 없어서 Okumura-Hata의 보정식을 씀 (TR 43.030도 시골 지역에는
  이 보정식을 2000MHz까지 쓸 수 있다고 함).

★ 적용 범위를 벗어난 값을 외삽함: 원래 1500~2000MHz, 기지국 30~200m, 단말 1~10m, 거리 1~20km용임.
  이 프로젝트의 920MHz, 1.5~15m, 수십m~수km는 범위 밖이라 절대값을 믿기보다 Song's Model과
  '비교'하는 용도로 봐야 함 (COST231_NOTE 참고).
"""
import math

VALID_ENVIRONMENTS = ("dense_urban", "urban", "suburban", "open")


def path_loss(fc_mhz: float, hb_m: float, hm_m: float, d_km: float, environment: str = "urban") -> float:
    """
    COST-231 Hata 경로손실(dB)을 반환함. 인자 순서는 song_model.path_loss와 같음.
    hb_m: 기지국(GW) 안테나 높이, hm_m: 단말(Node) 안테나 높이.
    """
    if environment not in VALID_ENVIRONMENTS:
        raise ValueError(f"알 수 없는 환경: {environment!r} (가능한 값: {', '.join(VALID_ENVIRONMENTS)})")
    if min(fc_mhz, hb_m, hm_m, d_km) <= 0:
        raise ValueError("주파수, 안테나 높이, 거리는 모두 0보다 커야 함")

    lf = math.log10(fc_mhz)
    lhb = math.log10(hb_m)
    a_hm = (1.1 * lf - 0.7) * hm_m - (1.56 * lf - 0.8)
    cm = 3.0 if environment == "dense_urban" else 0.0

    urban = (46.3 + 33.9 * lf - 13.82 * lhb - a_hm
             + (44.9 - 6.55 * lhb) * math.log10(d_km) + cm)

    if environment == "suburban":
        return urban - 2.0 * math.log10(fc_mhz / 28.0) ** 2 - 5.4
    if environment == "open":
        return urban - 4.78 * lf ** 2 + 18.33 * lf - 40.94
    return urban
