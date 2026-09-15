"""
Deygout 회절 손실 모델임. 지형/건물 때문에 시선(LOS)이 막힐 때 추가로 발생하는 손실을 계산함.
Song's Model만으로는 지형 장애물을 못 잡아내서 이 모듈이 별도로 필요함.
"""
import math


def free_space_path_loss(fc_mhz: float, d_km: float) -> float:
    """
    자유공간 경로손실(PL_FS)임. 장애물이 아예 없다고 가정했을 때의 이론적 최소 손실값.
    Deygout 계산에서 기준선(baseline) 역할로 씀.
    """
    return 20 * math.log10(fc_mhz) + 20 * math.log10(d_km) - 27.5492


def fresnel_v(h_eff_m: float, d1_m: float, d2_m: float, fc_mhz: float) -> float:
    """
    Fresnel-Kirchhoff 회절 파라미터 v 계산 함수임.
    h_eff_m: LOS 직선에서 장애물 꼭대기까지 수직으로 튀어나온 높이 (m).
             장애물이 LOS보다 낮으면 이 값이 음수가 될 수 있음 (그래서 diffraction_loss_j에서 v<=0 분기 처리함).
    d1_m, d2_m: 장애물 기준으로 GW/Node까지 각각 거리 (여기는 m 단위, path_loss 쪽 km이랑 헷갈리면 안 됨).
    """
    wavelength = 3e8 / (fc_mhz * 1e6)  # fc는 MHz 단위로 들어오니까 Hz로 변환해서 파장 계산
    return h_eff_m * math.sqrt(2 * (d1_m + d2_m) / (wavelength * d1_m * d2_m))


def diffraction_loss_j(v: float) -> float:
    """
    v값에 따른 회절 손실 J(v) 계산.
    구간이 3개로 나뉘는 구조임 (v<=0 / 0<v<=2.4 / v>2.4) - 문서 수식 그대로 옮긴 거라
    경계값(2.4)이나 계수 임의로 손대면 안 됨.
    """
    if v <= 0:
        # 장애물이 프레넬 존 밖에 있다는 뜻 -> 회절로 인한 추가 손실 없음
        return 0.0
    elif v <= 2.4:
        return 6.02 + 9.11 * v + 1.27 * v ** 2
    else:
        return 13.0 + 20 * math.log10(v)


def deygout_recursive(profile: list, fc_mhz: float, max_order: int = 2) -> float:
    """
    여기가 제일 복잡한 부분임. 아직 구현 안 하고 뼈대만 잡아둔 상태.

    profile: GW에서 Node까지 이어지는 지형 프로파일 샘플 리스트.
             [(거리_m, 고도_m), (거리_m, 고도_m), ...] 형태로 받을 예정.

    앞으로 할 일 (TODO):
      1. 전체 구간에서 v값이 제일 큰 지점(=주 장애물) 찾기
      2. 주 장애물 기준 1차 손실 = J(v_주) + 13dB 로 계산
      3. 주 장애물을 기준으로 경로를 (GW~주장애물) / (주장애물~Node) 두 구간으로 쪼갬
      4. 쪼갠 구간 안에서 각각 다시 v 최대인 지점(2차 장애물) 찾아서
         2차 손실 = J(v_2차) + 7dB 씩 추가 (max_order까지 재귀)
      5. 최종 회절 손실 LD_t = 1차 손실 + 2차 손실들 합

    max_order 기본값 2는 "2단계까지만 재귀 돈다"는 의미임 (문서 권장값).
    지금은 미구현 상태라 호출하면 바로 에러 나게 해둠 - 나중에 여기 채워야 함.
    """
    raise NotImplementedError