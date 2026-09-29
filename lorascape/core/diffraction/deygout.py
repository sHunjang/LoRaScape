# lorascape/core/diffraction/deygout.py
"""
Deygout 회절 손실 모델임. 지형/건물 때문에 시선(LOS)이 막힐 때 추가로 발생하는 손실을 계산함.
Song's Model만으로는 지형 장애물을 못 잡아내서 이 모듈이 별도로 필요함.
"""
import math

# 다중 장애물 보정에서 쓰는 상수들임 (문서 2번 요구사항 그대로).
MULTI_OBSTACLE_LOSS_PER_OBS_DB = 8.0
MULTI_OBSTACLE_LOSS_CAP_DB = 80.0
MULTI_OBSTACLE_THRESHOLD_COUNT = 5  # 장애물이 이 개수 넘어가면 재귀 대신 다중 보정으로 전환함 (임의 기준값 - 조정 가능)


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
             장애물이 LOS보다 낮으면 이 값이 음수가 될 수 있음.
    d1_m, d2_m: 장애물 기준으로 GW/Node까지 각각 거리 (m 단위).
    """
    wavelength = 3e8 / (fc_mhz * 1e6)
    return h_eff_m * math.sqrt(2 * (d1_m + d2_m) / (wavelength * d1_m * d2_m))


def diffraction_loss_j(v: float) -> float:
    """v값에 따른 회절 손실 J(v) 계산. 구간 3개로 나뉘는 구조임 (문서 수식 그대로)."""
    if v <= 0:
        return 0.0
    elif v <= 2.4:
        return 6.02 + 9.11 * v + 1.27 * v ** 2
    else:
        return 13.0 + 20 * math.log10(v)


def _rebase_distances(sub_profile: list) -> list:
    """
    구간의 첫 지점을 거리 0으로 다시 맞춘 프로파일을 반환함 (원본은 건드리지 않음).
    프로파일의 거리는 '전체 경로의 시작점' 기준이라, 뒤쪽 구간(주 장애물~Node)을 그대로
    쓰면 LOS 보간 비율과 d1이 틀어짐 - 구간 계산 전에 반드시 이걸 거쳐야 함.
    """
    d0 = sub_profile[0][0]
    return [(d - d0, e) for d, e in sub_profile]


def _line_of_sight_height(profile: list, tx_height: float, rx_height: float) -> list:
    """
    profile의 각 지점에서 '시선(LOS) 직선 대비 얼마나 튀어나왔는지(h_eff)'를 계산하는 내부 함수임.

    profile: [(거리_m, 지면고도_m), ...] - dem_loader.get_elevation_profile()이 주는 형태 그대로.
             거리는 이 profile의 첫 지점이 0이어야 함 (구간을 잘라 쓸 때는 _rebase_distances 사용).
    tx_height, rx_height: 첫/끝 지점의 '고도값 위로 얼마나 띄웠는지'임.
             GW/Node는 각자의 안테나 높이(schema.py의 antenna_height_m)이고,
             주 장애물 꼭대기를 끝점으로 쓸 때는 0임 (profile의 고도가 이미 꼭대기 높이라서).

    반환값: [(거리_m, h_eff_m), ...] - h_eff가 양수면 장애물이 LOS를 뚫고 올라온 거고,
            음수면 LOS 아래에 있는 거임 (=장애물 아님).
    """
    if len(profile) < 2:
        raise ValueError("profile은 최소 2개 지점(GW, Node) 이상이어야 함")

    d_total, _ = profile[-1]
    gw_ground = profile[0][1]
    node_ground = profile[-1][1]

    # 안테나 절대 고도 = 지면고도 + 안테나 높이임. 이게 실제 전파가 지나가는 시작/끝점 높이.
    tx_abs = gw_ground + tx_height
    rx_abs = node_ground + rx_height

    result = []
    for dist, ground_elev in profile:
        # 이 지점에서 LOS 직선의 높이를 선형보간으로 구함
        if d_total == 0:
            los_height = tx_abs
        else:
            t = dist / d_total
            los_height = tx_abs + (rx_abs - tx_abs) * t

        # profile의 고도가 곧 이 지점의 장애물 꼭대기 높이임. DEM(지형)을 넘기면 지형만,
        # 건물이 포함된 표면모델(DSM) 값을 넘기면 건물까지 반영됨 - 이 함수는 어느 쪽이든
        # 그대로 동작함 (DSM을 실제로 연결하는 건 DemLoader 쪽 과제임).
        # 이게 LOS보다 위로 튀어나온 정도 = h_eff
        h_eff = ground_elev - los_height
        result.append((dist, h_eff))

    return result


def _find_main_obstacle(profile_with_heff: list, fc_mhz: float) -> tuple:
    """
    주 장애물(v값이 최대인 지점)을 찾는 내부 함수임.
    양 끝점(GW, Node 자기 자신)은 장애물 후보에서 제외함 (자기 자신은 장애물이 아니니까).

    반환값: (index, v_max, h_eff, d1, d2) 또는 장애물이 전혀 없으면 None.
    """
    d_total = profile_with_heff[-1][0]
    best = None  # (v, index, h_eff, d1, d2)

    for i in range(1, len(profile_with_heff) - 1):
        dist, h_eff = profile_with_heff[i]
        d1 = dist
        d2 = d_total - dist
        if d1 <= 0 or d2 <= 0:
            continue  # 양 끝점과 겹치는 경우 스킵 (분모 0 방지)

        v = fresnel_v(h_eff, d1, d2, fc_mhz)
        if best is None or v > best[0]:
            best = (v, i, h_eff, d1, d2)

    if best is None or best[0] <= 0:
        return None  # 장애물이 없거나 전부 LOS 아래에 있음 (=회절 없음)

    v, idx, h_eff, d1, d2 = best
    return idx, v, h_eff, d1, d2


def _count_obstacles(profile_with_heff: list) -> int:
    """h_eff > 0인(=LOS 위로 튀어나온) 지점 개수를 셈. 다중 장애물 보정 여부 판단용."""
    return sum(1 for _, h_eff in profile_with_heff if h_eff > 0)


def deygout_recursive(
    profile: list,
    fc_mhz: float,
    tx_height: float,
    rx_height: float,
    max_order: int = 2,
    _order: int = 1,
) -> float:
    """
    Deygout 재귀 계산 메인 함수임.

    profile: [(거리_m, 지면고도_m), ...] GW->Node 순서로 정렬된 지형 샘플. 첫 점=GW, 끝점=Node.
    fc_mhz: 반송 주파수
    tx_height, rx_height: GW/Node 안테나 높이 (지면 기준, m)
    max_order: 재귀 최대 깊이 (기본 2단계 - 문서 권장값)
    _order: 내부적으로 재귀 깊이 추적용 (외부에서 호출할 땐 신경 안 써도 됨 - 기본값 그대로 두면 됨)

    반환값: 총 회절 손실 LD_t (dB). 장애물이 없으면 0.0을 반환함.

    ★ 수정 이력: 2차 회절(주 장애물 기준으로 경로를 둘로 쪼개 다시 계산하는 부분)에 버그가 있었음.
      (1) 주 장애물 꼭대기를 끝점으로 쓸 때 안테나 높이에 h_eff(LOS 대비 돌출량)를 넣고 있었음.
          꼭대기 높이는 profile의 고도 자체라 높이는 0이어야 함 - 돌출량을 또 더해서 끝점이
          실제보다 h_eff만큼 높게 계산됐음.
      (2) 뒤쪽 구간(주 장애물~Node)의 거리가 전체 경로 기준 그대로라 LOS 보간과 d1이 틀렸음.
      같은 지형에서 경로 방향만 뒤집어도 손실이 수십 dB 달라지는 증상으로 드러났음
      (정방향/역방향 결과가 같아야 정상임 - tests/test_deygout_second_order.py).
    """
    profile_with_heff = _line_of_sight_height(profile, tx_height, rx_height)

    # 다중 장애물 보정 분기임: 장애물이 너무 많으면 재귀 대신 단순 보정식으로 감 (문서 요구사항)
    n_obs = _count_obstacles(profile_with_heff)
    if n_obs > MULTI_OBSTACLE_THRESHOLD_COUNT:
        # 이 경로는 회절 손실이 아니라 "PL_FS 대비 추가 손실" 개념이라
        # 순수 회절손실 LD_t 값으로 바로 못 돌려주고, 상한 캡을 적용한 손실값을 그대로 반환함.
        # (호출부에서 이 값을 그냥 LD_t처럼 더해서 쓰면 됨 - 문서 4번 수식 그대로)
        return min(n_obs * MULTI_OBSTACLE_LOSS_PER_OBS_DB, MULTI_OBSTACLE_LOSS_CAP_DB)

    main = _find_main_obstacle(profile_with_heff, fc_mhz)
    if main is None:
        return 0.0  # 장애물 없음 -> 회절 손실 없음 (완전 LOS 또는 준-LOS)

    idx, v_main, h_eff, d1, d2 = main
    loss_1st = diffraction_loss_j(v_main) + 13.0

    if _order >= max_order:
        # 재귀 깊이 한계 도달 -> 1차 손실만 반환
        return loss_1st

    # 주 장애물 꼭대기를 새 끝점으로 삼아 경로를 GW~주장애물 / 주장애물~Node 두 구간으로 쪼갬.
    # 뒤쪽 구간은 거리를 0부터 다시 시작하도록 맞춰야 함 (_rebase_distances 참고).
    left_profile = profile[: idx + 1]
    right_profile = _rebase_distances(profile[idx:])

    loss_2nd_total = 0.0

    # 왼쪽 구간(GW~주장애물)에 장애물이 2개 이상 있어야 2차 계산 의미가 있음 (양 끝점만 있으면 스킵)
    if len(left_profile) > 2:
        # 주 장애물 꼭대기 = profile의 고도 자체이므로 그 끝점의 '띄운 높이'는 0임
        left_heff = _line_of_sight_height(left_profile, tx_height, 0.0)
        sub_main = _find_main_obstacle(left_heff, fc_mhz)
        if sub_main is not None:
            _, v_sub, _, _, _ = sub_main
            loss_2nd_total += diffraction_loss_j(v_sub) + 7.0

    if len(right_profile) > 2:
        right_heff = _line_of_sight_height(right_profile, 0.0, rx_height)
        sub_main = _find_main_obstacle(right_heff, fc_mhz)
        if sub_main is not None:
            _, v_sub, _, _, _ = sub_main
            loss_2nd_total += diffraction_loss_j(v_sub) + 7.0

    return loss_1st + loss_2nd_total
