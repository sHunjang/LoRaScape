# build/lorascape.spec
"""
LoRaScape 본체 PyInstaller 스펙 파일임.

rasterio/sklearn/scipy는 C 확장 모듈과 데이터 파일이 많아서 PyInstaller가
자동으로 못 찾는 게 흔함 - 그래서 collect_all로 통째로 긁어옴 (용량은 늘지만
누락 에러보다 안전함). PyQt5.QtWebEngine 관련 리소스(html/js/폰트)도
누락되면 지도가 빈 화면으로만 뜨는 조용한 실패가 나서 명시적으로 챙김.
"""
from PyInstaller.utils.hooks import collect_all, collect_data_files
import os

block_cipher = None

# 무거운 의존성들은 collect_all로 datas/binaries/hiddenimports를 한 번에 다 긁어옴
datas = []
binaries = []
hiddenimports = []

for pkg in ["rasterio", "sklearn", "scipy", "folium", "branca", "pyproj", "fiona"]:
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass  # fiona처럼 아예 안 쓰는 게 있을 수도 있어서 실패해도 무시함

# 우리 앱 자체의 리소스(월드맵 이미지 등)
datas += [
    (os.path.join("..", "lorascape", "gui", "assets"), "lorascape/gui/assets"),
]

# PyQt5 관련 - QWebEngine 리소스가 누락되면 지도가 빈 화면으로 뜸
hiddenimports += [
    "PyQt5.QtWebEngineWidgets",
    "PyQt5.QtWebChannel",
    "PyQt5.QtPrintSupport",  # QWebEngine이 내부적으로 요구하는 경우가 있음
]

# matplotlib 백엔드 - Qt5Agg 명시 안 하면 headless 백엔드로 잘못 잡히는 경우 있음
hiddenimports += ["matplotlib.backends.backend_qt5agg"]

a = Analysis(
    ["../scripts/run_app.py"],
    pathex=["..", "../lorascape"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LoRaScape",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX 압축은 rasterio/Qt 계열 dll에서 종종 문제를 일으켜서 끔
    console=True,  # ★ 처음엔 True로 - 에러 메시지를 콘솔에서 봐야 디버깅 가능함. 안정화되면 False로.
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="LoRaScape",
)