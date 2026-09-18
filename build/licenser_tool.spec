# build/licenser_tool.spec
"""
라이선스 발급 도구 PyInstaller 스펙임. 본체와 완전히 독립적으로 패키징함 -
PyQt5 외에 다른 무거운 의존성이 없어서 스펙이 단순함.
"""
block_cipher = None

a = Analysis(
    ["../licenser_tool/keygen_gui.py"],
    pathex=["../licenser_tool"],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LoRaScape_Licenser",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="LoRaScape_Licenser",
)