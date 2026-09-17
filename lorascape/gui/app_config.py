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
    "heatmap_opacity": 0.85,
    "heatmap_grid_size": 40,
}


# 설정창 콤보박스에 보여줄 프리셋임. (grid_size, 라벨) 순서.
# 라벨에 "빠름/보통/정밀/매우 정밀"처럼 체감 속도를 같이 적어서, 숫자만 봐서는
# 감이 안 오는 사용자도 고를 수 있게 함.
HEATMAP_GRID_SIZE_PRESETS = [
    (20, "20 x 20 (빠름, 거친 화질)"),
    (40, "40 x 40 (기본, 보통 속도)"),
    (60, "60 x 60 (정밀, 느림)"),
    (80, "80 x 80 (매우 정밀, 매우 느림)"),
    (100, "100 x 100 (최고 정밀, 최고 느림)"),
]


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