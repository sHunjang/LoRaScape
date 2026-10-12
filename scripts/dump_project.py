# scripts/dump_project.py
"""
프로젝트 파일(.lsproj)의 내용을 읽기 전용으로 출력하는 확인용 스크립트임. 앱이 열려 있어도 쓸 수 있고,
SQLite 표준 모듈만 써서 lorascape를 설치하지 않은 PC에서도 돌아감 (현장 노트북 점검용).

  python scripts/dump_project.py <프로젝트 파일>              # 요약
  python scripts/dump_project.py <프로젝트 파일> <ID 일부>     # 그 ID를 가진 장비의 상세 (예: GW 이름 일부)
"""
import os
import sqlite3
import sys
from pathlib import Path


def open_readonly(path: str) -> sqlite3.Connection:
    if not os.path.exists(path):
        raise SystemExit(f"파일이 없습니다: {path}")
    try:
        return sqlite3.connect(f"{Path(path).resolve().as_uri()}?mode=ro", uri=True)   # 실수로 쓰지 않도록 읽기 전용
    except sqlite3.OperationalError:
        return sqlite3.connect(path)


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    path = sys.argv[1]
    needle = sys.argv[2] if len(sys.argv) > 2 else None
    conn = open_readonly(path)
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        meta = dict(conn.execute("SELECT key, value FROM meta"))
    except sqlite3.DatabaseError:
        raise SystemExit("LoRaScape 프로젝트 파일이 아니거나 손상된 파일입니다.")

    print(f"파일: {path}  ({os.path.getsize(path):,} bytes)")
    print(f"프로젝트 이름: {meta.get('project_name', '')!r} | 스키마 v{version} | 만든 시각 {meta.get('created_at', '')}")

    print("\n[장비 수]")
    for kind, n in conn.execute("SELECT kind, COUNT(*) FROM devices GROUP BY kind ORDER BY kind"):
        print(f"  {kind}: {n}개")

    print("\n[프로젝트 기본값 (공장 기본값과 다르게 바꾼 것만 저장됨)]")
    rows = conn.execute("SELECT kind, param, value FROM defaults ORDER BY kind, param").fetchall()
    for kind, param, value in rows:
        print(f"  {kind}.{param} = {value}")
    if not rows:
        print("  (없음 - 모두 공장 기본값)")

    print("\n[직접 입력/가져온 성능 값 (이 장비들만 기본값을 따르지 않음)]")
    rows = conn.execute("SELECT kind, id, param, value, source FROM device_params "
                        "ORDER BY kind, id, param").fetchall()
    for kind, did, param, value, source in rows[:40]:
        print(f"  {kind:8s} {did:28s} {param:18s} = {value:<8} ({source})")
    if len(rows) > 40:
        print(f"  ... 외 {len(rows) - 40}개")
    if not rows:
        print("  (없음 - 모든 장비가 기본값 사용 중)")

    if needle:
        print(f"\n[ID에 '{needle}'가 들어간 장비]")
        found = conn.execute("SELECT kind, id, lat, lon, position FROM devices WHERE id LIKE ? ORDER BY kind, position",
                             (f"%{needle}%",)).fetchall()
        for kind, did, lat, lon, pos in found:
            params = conn.execute("SELECT param, value, source FROM device_params WHERE kind = ? AND id = ?",
                                  (kind, did)).fetchall()
            extra = ", ".join(f"{p}={v}({s})" for p, v, s in params) or "개별 값 없음(기본값 사용)"
            print(f"  {kind} {did} | 위도 {lat:.6f} 경도 {lon:.6f} | #{pos} | {extra}")
        if not found:
            print("  (없음)")
    conn.close()


if __name__ == "__main__":
    main()