# lorascape/gui/app_config.py
"""
앱 설정(마지막에 선택했던 파일 경로 등)을 JSON 파일로 저장/로드하는 모듈임.
사용자 홈 폴더 아래 숨김 폴더에 저장함 - exe로 배포됐을 때도 사용자별로
독립적인 설정이 유지되게 하려고 (Program Files 안에 쓰기 권한 없는 경우가
많아서, 홈 폴더가 안전한 선택임).
"""
import json
import os

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".lorascape")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_CONFIG = {
    "shp_path": "",
    "dem_path": "",
    "dsm_path": "",
    "xlsx_path": "",
    "fc_mhz": 920.0,
    "bandwidth_hz": 125000.0,
    "receiver_noise_figure_db": 6.0,
    "environment": "urban",
    "coverage_target": 0.9,
    "max_additional": 15,
    # ★ 추가: 히트맵 표시 진하기임. 처음 만들 때 0.65로 잡았는데 실제로 보니
    # 너무 연하게 보여서, 사용자가 직접 조절할 수 있게 설정에 노출함.
    "heatmap_opacity": 0.85,
}


def load_config() -> dict:
    """설정 파일을 읽어옴. 파일이 없거나 깨져있으면 기본값을 반환함 (에러 안 던짐 -
    첫 실행이거나 설정파일이 손상된 상황 둘 다 '빈 설정'으로 취급하면 되니까)."""
    if not os.path.exists(CONFIG_PATH):
        return dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = dict(DEFAULT_CONFIG)
        merged.update(data)
        return merged
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_CONFIG)


def save_config(config: dict):
    """설정을 JSON 파일로 저장함. 폴더가 없으면 만듦."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)