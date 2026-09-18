# lorascape/gui/widgets/hillshade.py
"""
고도 격자(2D 배열)를 음영기복도(hillshade) 이미지로 변환하는 순수 함수임.
Qt/PyQtGraph에 전혀 의존 안 해서 GUI 없이도 단위테스트 가능함.

원리: 태양이 특정 방위각(azimuth)·고도각(altitude)에서 비춘다고 가정하고,
지형의 기울기(경사)에 따라 명암을 계산함 - 표준 GIS 음영기복 알고리즘임.
"""
import numpy as np


def compute_hillshade(
    elevation: np.ndarray,
    azimuth_deg: float = 315.0,
    altitude_deg: float = 45.0,
    z_factor: float = 1.0,
) -> np.ndarray:
    """
    고도 배열을 0~255 범위의 밝기(uint8) 배열로 변환함.
    azimuth_deg=315(북서쪽)가 GIS 관례상 가장 자연스러운 음영 방향이라 기본값으로 씀.

    NaN(구멍난 픽셀)은 중간 밝기(128)로 채워서 화면에 이상하게 안 튀게 함.
    """
    elev = np.where(np.isnan(elevation), np.nanmean(elevation), elevation) * z_factor

    # 경사(gradient) 계산 - x/y 방향 기울기
    gy, gx = np.gradient(elev)
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)

    azimuth_rad = np.radians(360.0 - azimuth_deg + 90.0)
    altitude_rad = np.radians(altitude_deg)

    shaded = (
        np.sin(altitude_rad) * np.cos(slope)
        + np.cos(altitude_rad) * np.sin(slope) * np.cos(azimuth_rad - aspect)
    )
    shaded = np.clip(shaded, 0, 1)

    result = (shaded * 255).astype(np.uint8)

    # 원본에서 NaN이었던 픽셀은 중간 회색으로 덮어써서 "구멍"이 티 안 나게 함
    result = np.where(np.isnan(elevation), 128, result).astype(np.uint8)
    return result