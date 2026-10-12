# lorascape/data/project_db.py
"""
프로젝트 파일(SQLite) 저장 계층임. 현장 하나 = 파일 하나(.lsproj)라서 복사/백업/메일 전달이 쉽고,
설치 업체가 노트북 여러 대, 현장 여러 곳을 다뤄도 데이터가 섞이지 않음. Qt에 의존하지 않음.

★ 핵심 설계 - '값 하나하나가 어디서 왔는지'를 기억하는 기본값 계층:
    장비의 성능 값(안테나 높이, 이득 등) = 그 장비에 직접 입력된 값(있으면) -> 없으면 프로젝트 기본값
    프로젝트 기본값 = 사용자가 바꾼 값(있으면) -> 없으면 데이터클래스 기본값(공장 기본값)
  그래서 (1) 위치 파일(ID, 위도, 경도)만 가져와도 바로 계산이 되고, (2) 기본값을 바꾸면 직접 입력 안 한
  장비 전체에 적용되고, (3) '실제 입력 N개 / 추정(기본값) M개'를 보고서에 낼 수 있음.
  공장 기본값은 schema.py 데이터클래스의 필드 기본값을 그대로 읽음 (값을 두 곳에 적어두면 어긋나므로).

저장 방식 두 가지:
  - sync_*   : 화면의 목록이 '정답'일 때 씀 (목록창에서 수정/삭제/추가, 지도 드래그). 현재 DB 값과 다른
               성능 값은 사용자가 직접 입력한 것으로 기록하고, 목록에서 빠진 장비는 삭제함.
  - import_* : 파일에서 가져올 때 씀 (엑셀/CSV). 같은 ID는 위치와 설명만 갱신하고, 사용자가 직접 입력한 성능 값은
               덮어쓰지 않고, 파일에 없는 기존 장비는 지우지 않고 알려줌 (다시 가져왔다고 입력해 둔 값이 날아가면 안 되므로).
"""
from __future__ import annotations

import dataclasses
import json
import math
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

KIND_GATEWAY = "gateway"
KIND_NODE = "node"
KINDS = (KIND_GATEWAY, KIND_NODE)

SCHEMA_VERSION = 1
APP_MARKER = "lorascape-project"          # 우리 프로젝트 파일인지 확인하는 표식

SOURCE_IMPORT = "import"                  # 파일에서 가져온 값
SOURCE_USER = "user"                      # 사용자가 화면에서 직접 입력한 값

# 값 하나하나에 출처를 붙이는 성능 파라미터임. 데이터클래스에 없는 이름은 자동으로 무시함.
GW_PARAMS = ("antenna_height_m", "tx_power_dbm", "antenna_gain_dbi", "cable_loss_db")
NODE_PARAMS = ("antenna_height_m", "antenna_gain_dbi", "cable_loss_db", "min_rx_dbm", "indoor_loss_db")

# 가져오기를 다시 해도 덮어쓰면 안 되는, 사용자가 화면에서 직접 조작하는 설명 필드임.
USER_CONTROLLED_ATTRS = frozenset({"enabled"})


class ProjectError(Exception):
    """프로젝트 파일 관련 오류의 공통 부모임."""


class ProjectFormatError(ProjectError):
    """LoRaScape 프로젝트 파일이 아니거나 손상된 경우임."""


class ProjectTooNewError(ProjectError):
    """이 프로그램보다 새로운 버전이 만든 프로젝트 파일임 (열면 데이터가 깨질 수 있어서 거부함)."""


@dataclass
class ImportReport:
    added: int = 0
    updated: int = 0
    unchanged: int = 0
    missing_ids: list = field(default_factory=list)    # DB에는 있는데 이번 파일에는 없는 ID (삭제하지 않음)
    protected: list = field(default_factory=list)      # [(id, param)] 사용자 입력 보호로 덮어쓰지 않은 값


# ── 스키마와 마이그레이션 ────────────────────────────────────────────────

def _migrate_to_v1(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE defaults (
            kind TEXT NOT NULL, param TEXT NOT NULL, value REAL NOT NULL,
            PRIMARY KEY (kind, param));
        CREATE TABLE devices (
            kind TEXT NOT NULL, id TEXT NOT NULL,
            lat REAL NOT NULL, lon REAL NOT NULL,
            attrs TEXT NOT NULL,
            position INTEGER NOT NULL,
            PRIMARY KEY (kind, id));
        CREATE TABLE device_params (
            kind TEXT NOT NULL, id TEXT NOT NULL, param TEXT NOT NULL,
            value REAL NOT NULL,
            source TEXT NOT NULL CHECK (source IN ('import', 'user')),
            PRIMARY KEY (kind, id, param),
            FOREIGN KEY (kind, id) REFERENCES devices (kind, id) ON DELETE CASCADE ON UPDATE CASCADE);
    """)


# 버전 N으로 올리는 함수임. 새 기능(장비 모델 프로파일, 해발고도 컬럼 등)은 여기에 v2, v3로 추가하면 됨.
MIGRATIONS = {1: _migrate_to_v1}


def _spec(kind: str):
    """(데이터클래스, ID 필드명, 성능 파라미터 이름 튜플)을 돌려줌."""
    from lorascape.data.schema import GatewaySite, NodeSite
    if kind == KIND_GATEWAY:
        return GatewaySite, "gw_id", GW_PARAMS
    if kind == KIND_NODE:
        return NodeSite, "node_id", NODE_PARAMS
    raise ValueError(f"알 수 없는 장비 종류: {kind!r}")


def _factory_defaults(kind: str) -> dict:
    """데이터클래스 필드 기본값에서 공장 기본값을 읽음 (기본값이 없는 필드는 파라미터로 취급 안 함)."""
    cls, _, params = _spec(kind)
    out = {}
    for f in dataclasses.fields(cls):
        if f.name in params and f.default is not dataclasses.MISSING and f.default is not None:
            out[f.name] = float(f.default)
    return out


def _close(a: float, b: float) -> bool:
    return math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-9)


def _json_default(o):
    if hasattr(o, "item"):          # numpy 스칼라
        return o.item()
    raise TypeError(f"JSON으로 저장할 수 없는 값: {type(o).__name__}")


class ProjectDB:
    """프로젝트 파일 하나를 여는 객체임. GUI 메인 스레드에서만 쓸 것 (SQLite 연결이 스레드 전용이라서)."""

    def __init__(self, conn: sqlite3.Connection, path: str):
        self._conn = conn
        self.path = path

    # ── 생성/열기/닫기 ─────────────────────────────────────

    @classmethod
    def create(cls, path: str, name: str = "", app_version: str = "") -> "ProjectDB":
        if os.path.exists(path):
            raise FileExistsError(path)          # 기존 프로젝트를 실수로 덮어쓰지 않음
        conn = sqlite3.connect(path)
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            with conn:
                for version in sorted(MIGRATIONS):
                    MIGRATIONS[version](conn)
                conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
                conn.executemany("INSERT INTO meta (key, value) VALUES (?, ?)", [
                    ("app", APP_MARKER), ("project_name", name),
                    ("created_at", datetime.now().isoformat(timespec="seconds")),
                    ("created_with", app_version),
                ])
        except Exception:
            conn.close()
            if os.path.exists(path):
                os.remove(path)                  # 만들다 실패한 반쪽짜리 파일을 남기지 않음
            raise
        return cls(conn, path)

    @classmethod
    def open(cls, path: str) -> "ProjectDB":
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        conn = sqlite3.connect(path)
        try:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            row = conn.execute("SELECT value FROM meta WHERE key = 'app'").fetchone()
        except sqlite3.DatabaseError as e:
            conn.close()
            raise ProjectFormatError(f"LoRaScape 프로젝트 파일이 아닙니다: {path}") from e
        if row is None or row[0] != APP_MARKER:
            conn.close()
            raise ProjectFormatError(f"LoRaScape 프로젝트 파일이 아닙니다: {path}")
        if version > SCHEMA_VERSION:
            conn.close()
            raise ProjectTooNewError(
                f"이 프로젝트는 더 새로운 버전의 프로그램(스키마 v{version})으로 만들어졌습니다. "
                f"이 프로그램은 v{SCHEMA_VERSION}까지 지원합니다. 프로그램을 업데이트하세요."
            )
        conn.execute("PRAGMA foreign_keys = ON")
        if version < SCHEMA_VERSION:
            with conn:                           # 옛 프로젝트를 한 단계씩 올림 (실패하면 전부 되돌림)
                for v in range(version + 1, SCHEMA_VERSION + 1):
                    MIGRATIONS[v](conn)
                conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        return cls(conn, path)

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def backup_to(self, dest_path: str, overwrite: bool = False):
        """열려 있는 상태에서도 안전하게 복사함 (파일을 그냥 복사하면 쓰는 도중의 상태가 섞일 수 있음)."""
        if os.path.exists(dest_path):
            if not overwrite:
                raise FileExistsError(dest_path)
            os.remove(dest_path)
        dest = sqlite3.connect(dest_path)
        try:
            self._conn.backup(dest)
        finally:
            dest.close()

    # ── 메타 ──────────────────────────────────────────────

    def get_meta(self, key: str, default: str = "") -> str:
        row = self._conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row else default

    def set_meta(self, key: str, value: str):
        with self._conn:
            self._conn.execute("INSERT INTO meta (key, value) VALUES (?, ?) "
                               "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, str(value)))

    @property
    def name(self) -> str:
        return self.get_meta("project_name")

    # ── 프로젝트 기본값 ────────────────────────────────────

    @staticmethod
    def params(kind: str) -> tuple:
        """그 종류에서 출처를 추적하는 성능 파라미터 이름들임."""
        return tuple(_factory_defaults(kind))

    @staticmethod
    def factory_defaults(kind: str) -> dict:
        return _factory_defaults(kind)

    def get_defaults(self, kind: str) -> dict:
        """프로젝트 기본값 = 공장 기본값 위에 사용자가 바꾼 값을 덮은 것임."""
        out = _factory_defaults(kind)
        for param, value in self._conn.execute("SELECT param, value FROM defaults WHERE kind = ?", (kind,)):
            if param in out:
                out[param] = value
        return out

    def set_default(self, kind: str, param: str, value: float):
        """기본값을 바꿈. 공장 기본값과 같으면 저장된 덮어쓰기를 지워서 DB를 깔끔하게 유지함."""
        factory = _factory_defaults(kind)
        if param not in factory:
            raise ValueError(f"기본값을 바꿀 수 없는 항목: {param!r}")
        with self._conn:
            if _close(value, factory[param]):
                self._conn.execute("DELETE FROM defaults WHERE kind = ? AND param = ?", (kind, param))
            else:
                self._conn.execute(
                    "INSERT INTO defaults (kind, param, value) VALUES (?, ?, ?) "
                    "ON CONFLICT(kind, param) DO UPDATE SET value = excluded.value", (kind, param, float(value)))

    def reset_default(self, kind: str, param: str):
        with self._conn:
            self._conn.execute("DELETE FROM defaults WHERE kind = ? AND param = ?", (kind, param))

    # ── 장비 개별 성능 값 ──────────────────────────────────

    def set_param(self, kind: str, device_id: str, param: str, value: float, source: str = SOURCE_USER):
        if param not in _factory_defaults(kind):
            raise ValueError(f"알 수 없는 성능 항목: {param!r}")
        if source not in (SOURCE_IMPORT, SOURCE_USER):
            raise ValueError(f"알 수 없는 출처: {source!r}")
        with self._conn:
            if self._conn.execute("SELECT 1 FROM devices WHERE kind = ? AND id = ?", (kind, device_id)).fetchone() is None:
                raise KeyError(f"{kind} {device_id!r}가 프로젝트에 없습니다")
            self._conn.execute(
                "INSERT INTO device_params (kind, id, param, value, source) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(kind, id, param) DO UPDATE SET value = excluded.value, source = excluded.source",
                (kind, device_id, param, float(value), source))

    def clear_param(self, kind: str, device_id: str, param: str):
        """개별 값을 지워서 그 장비가 기본값을 따르게 함."""
        with self._conn:
            self._conn.execute("DELETE FROM device_params WHERE kind = ? AND id = ? AND param = ?",
                               (kind, device_id, param))

    def _explicit(self, kind: str) -> dict:
        """{장비 ID: {파라미터: (값, 출처)}}"""
        out: dict = {}
        for did, param, value, source in self._conn.execute(
                "SELECT id, param, value, source FROM device_params WHERE kind = ?", (kind,)):
            out.setdefault(did, {})[param] = (value, source)
        return out

    def data_fidelity(self, kind: str) -> dict:
        """
        파라미터별로 '직접 입력한 장비 수 / 기본값(추정)을 쓰는 장비 수'를 셈. 보고서에 데이터 충실도를 표시하는 용도임.
        반환: {"total": 장비 수, "params": {파라미터: {"explicit": n, "default": m}}}
        """
        total = self._conn.execute("SELECT COUNT(*) FROM devices WHERE kind = ?", (kind,)).fetchone()[0]
        params = {p: {"explicit": 0, "default": total} for p in _factory_defaults(kind)}
        for param, n in self._conn.execute(
                "SELECT param, COUNT(*) FROM device_params WHERE kind = ? GROUP BY param", (kind,)):
            if param in params:
                params[param] = {"explicit": n, "default": total - n}
        return {"total": total, "params": params}

    # ── 읽기 ──────────────────────────────────────────────

    def load(self, kind: str) -> list:
        cls, id_field, _ = _spec(kind)
        defaults = self.get_defaults(kind)
        explicit = self._explicit(kind)
        names = {f.name for f in dataclasses.fields(cls)}
        out = []
        for did, lat, lon, attrs_json in self._conn.execute(
                "SELECT id, lat, lon, attrs FROM devices WHERE kind = ? ORDER BY position", (kind,)):
            kwargs = {k: v for k, v in json.loads(attrs_json).items() if k in names}
            kwargs.update({id_field: did, "lat": lat, "lon": lon})
            for p, default in defaults.items():
                kwargs[p] = explicit.get(did, {}).get(p, (default, None))[0]
            out.append(cls(**kwargs))
        return out

    def load_gateways(self) -> list:
        return self.load(KIND_GATEWAY)

    def load_nodes(self) -> list:
        return self.load(KIND_NODE)

    # ── 쓰기: 화면 목록이 정답일 때 ─────────────────────────

    @staticmethod
    def _split(obj, kind: str):
        """객체를 (ID, 위도, 경도, 성능값 dict, 설명 필드 JSON, 설명 필드 dict)로 나눔."""
        cls, id_field, _ = _spec(kind)
        param_names = set(_factory_defaults(kind))
        attrs = {f.name: getattr(obj, f.name) for f in dataclasses.fields(cls)
                 if f.name not in (id_field, "lat", "lon") and f.name not in param_names}
        values = {p: float(getattr(obj, p)) for p in param_names}
        return (getattr(obj, id_field), float(obj.lat), float(obj.lon), values,
                json.dumps(attrs, ensure_ascii=False, sort_keys=True, default=_json_default), attrs)

    @staticmethod
    def _check_unique(ids: list, kind: str):
        seen, dup = set(), []
        for i in ids:
            if i in seen and i not in dup:
                dup.append(i)
            seen.add(i)
        if dup:
            raise ValueError(f"{kind} ID가 중복됩니다: {', '.join(map(str, dup[:10]))}"
                             + (" 외" if len(dup) > 10 else ""))

    def sync(self, kind: str, objs, delete_missing: bool = True):
        """
        목록 전체를 DB에 맞춤. 현재 DB 값과 다른 성능 값은 사용자 입력으로 기록하고,
        delete_missing이면 목록에 없는 장비를 삭제함. 한 트랜잭션이라 중간에 실패하면 전부 되돌아감.
        """
        cls, id_field, params = _spec(kind)
        objs = list(objs)
        self._check_unique([getattr(o, id_field) for o in objs], kind)       # 쓰기 전에 먼저 검사
        defaults = self.get_defaults(kind)
        with self._conn:
            existing = {r[0] for r in self._conn.execute("SELECT id FROM devices WHERE kind = ?", (kind,))}
            explicit = self._explicit(kind)
            for pos, obj in enumerate(objs):
                did, lat, lon, values, attrs_json, _ = self._split(obj, kind)
                if did in existing:
                    self._conn.execute("UPDATE devices SET lat = ?, lon = ?, attrs = ?, position = ? "
                                       "WHERE kind = ? AND id = ?", (lat, lon, attrs_json, pos, kind, did))
                else:
                    self._conn.execute("INSERT INTO devices (kind, id, lat, lon, attrs, position) "
                                       "VALUES (?, ?, ?, ?, ?, ?)", (kind, did, lat, lon, attrs_json, pos))
                for p, v in values.items():
                    current = explicit.get(did, {}).get(p, (defaults[p], None))[0]
                    if not _close(v, current):
                        self._conn.execute(
                            "INSERT INTO device_params (kind, id, param, value, source) VALUES (?, ?, ?, ?, ?) "
                            "ON CONFLICT(kind, id, param) DO UPDATE SET value = excluded.value, source = excluded.source",
                            (kind, did, p, v, SOURCE_USER))
            if delete_missing:
                keep = {getattr(o, id_field) for o in objs}
                for did in existing - keep:
                    self._conn.execute("DELETE FROM devices WHERE kind = ? AND id = ?", (kind, did))

    def sync_gateways(self, objs, delete_missing: bool = True):
        self.sync(KIND_GATEWAY, objs, delete_missing)

    def sync_nodes(self, objs, delete_missing: bool = True):
        self.sync(KIND_NODE, objs, delete_missing)

    # ── 쓰기: 파일에서 가져올 때 ───────────────────────────

    def import_devices(self, kind: str, objs) -> ImportReport:
        """
        파일에서 읽은 장비를 병합함.
          - 새 ID: 추가함. 성능 값이 공장 기본값과 다르면 '가져온 값'으로 기록함
            (파일에 값이 있었는지 객체만으로는 알 수 없어서, 기본값과 다른 값만 파일에서 온 것으로 봄).
          - 같은 ID: 위치와 설명만 갱신함. 사용자가 직접 입력한 값은 덮어쓰지 않고 report.protected에 남김.
          - 파일에 없는 기존 ID: 삭제하지 않고 report.missing_ids로 알려줌.
        """
        cls, id_field, params = _spec(kind)
        objs = list(objs)
        self._check_unique([getattr(o, id_field) for o in objs], kind)
        factory = _factory_defaults(kind)
        report = ImportReport()
        with self._conn:
            rows = {r[0]: (r[1], r[2], r[3]) for r in self._conn.execute(
                "SELECT id, lat, lon, attrs FROM devices WHERE kind = ?", (kind,))}
            explicit = self._explicit(kind)
            next_pos = self._conn.execute(
                "SELECT COALESCE(MAX(position), -1) + 1 FROM devices WHERE kind = ?", (kind,)).fetchone()[0]
            seen = set()
            for obj in objs:
                did, lat, lon, values, attrs_json, attrs = self._split(obj, kind)
                seen.add(did)
                is_new = did not in rows
                changed = is_new
                if is_new:
                    self._conn.execute("INSERT INTO devices (kind, id, lat, lon, attrs, position) "
                                       "VALUES (?, ?, ?, ?, ?, ?)", (kind, did, lat, lon, attrs_json, next_pos))
                    next_pos += 1
                else:
                    old_lat, old_lon, old_attrs_json = rows[did]
                    merged = json.loads(old_attrs_json)
                    for k, v in attrs.items():
                        if k not in USER_CONTROLLED_ATTRS:         # 화면에서 직접 켜고 끄는 값은 보존함
                            merged[k] = json.loads(json.dumps(v, default=_json_default))
                    new_attrs_json = json.dumps(merged, ensure_ascii=False, sort_keys=True, default=_json_default)
                    if not (_close(old_lat, lat) and _close(old_lon, lon)) or new_attrs_json != old_attrs_json:
                        changed = True
                        self._conn.execute("UPDATE devices SET lat = ?, lon = ?, attrs = ? WHERE kind = ? AND id = ?",
                                           (lat, lon, new_attrs_json, kind, did))
                for p, v in values.items():
                    if _close(v, factory[p]):
                        continue                                    # 기본값과 같으면 파일의 값으로 보지 않음
                    prev = explicit.get(did, {}).get(p)
                    if prev is not None and prev[1] == SOURCE_USER:
                        if not _close(prev[0], v):
                            report.protected.append((did, p))        # 사용자 입력이 우선
                        continue
                    if prev is None or not _close(prev[0], v):
                        changed = True
                        self._conn.execute(
                            "INSERT INTO device_params (kind, id, param, value, source) VALUES (?, ?, ?, ?, ?) "
                            "ON CONFLICT(kind, id, param) DO UPDATE SET value = excluded.value, source = excluded.source",
                            (kind, did, p, v, SOURCE_IMPORT))
                if is_new:
                    report.added += 1
                elif changed:
                    report.updated += 1
                else:
                    report.unchanged += 1
            report.missing_ids = [i for i in rows if i not in seen]
        return report

    def import_gateways(self, objs) -> ImportReport:
        return self.import_devices(KIND_GATEWAY, objs)

    def import_nodes(self, objs) -> ImportReport:
        return self.import_devices(KIND_NODE, objs)
