# lorascape/data/schema.py
"""
Node/GW 공통 데이터 구조 정의임.
엑셀에서 뭘 읽어오든 결국 이 형태로 통일해서 core 계산 함수들에 넘겨줌.
core 쪽(song_model, deygout 등)은 이 dataclass만 알면 되고, 엑셀 구조는 몰라도 됨
-> 나중에 엑셀 양식이 바뀌어도 core는 안 건드려도 되는 구조.

이번에 GUI 편집용 무선 링크 파라미터(Pt, Gt, Lt, Gr, Lr 등)를 추가함.
이 값들은 원래 엑셀에 없는 정보라서(장비 데이터시트에서 나오는 값들이라) 일단
업계 표준적인 기본값으로 깔아두고, GUI에서 사용자가 GW/Node 하나하나 선택해서
직접 고칠 수 있게 만들 예정임 - 이건 antenna_height_m을 1.5m 기본값으로 두고
GUI에서 고치게 한 것과 완전히 같은 패턴임.
"""
from dataclasses import dataclass
from typing import Optional

DEFAULT_ANTENNA_HEIGHT_M = 1.5

# GW 무선 파라미터 기본값임. 흔한 LoRa GW(예: 8채널 실외형) 스펙 기준으로 잡은 값이라
# 정확한 장비 스펙이 확보되면 그 값으로 교체하면 됨.
DEFAULT_GW_TX_POWER_DBM = 14.0
DEFAULT_GW_ANTENNA_GAIN_DBI = 6.0
DEFAULT_GW_CABLE_LOSS_DB = 1.0

# Node 무선 파라미터 기본값임. 대부분의 LoRa 단말은 안테나 이득/케이블 손실이
# 거의 없는 소형 내장 안테나를 쓰는 경우가 많아서 0으로 깔아둠.
DEFAULT_NODE_ANTENNA_GAIN_DBI = 0.0
DEFAULT_NODE_CABLE_LOSS_DB = 0.0
DEFAULT_NODE_MIN_RX_DBM = -126.6  # SF12 기준 수신감도 근사치 (참고용 표시값)
DEFAULT_NODE_INDOOR_LOSS_DB = 0.0  # 실외 설치가 기본이라 0


@dataclass
class GatewaySite:
    """GW(게이트웨이) 후보/설치 위치 정보임."""
    gw_id: str                     # 관리번호 또는 일련번호 (예: "수정고등-A-64") - GUI에서 callsign처럼 표시용으로도 씀
    region: str                    # 지역 (탄천/중앙공원/율동공원/위례공원/서판교)
    location_desc: str             # 상세위치 (예: "여수대교 인근")
    lat: float
    lon: float
    install_type: str              # 설치방법 원본 텍스트 (예: "기존 CCTV폴에 설치", "신규설치")
    power_source: str              # 전원 공급 방안 (예: "CCTV폴 전원 사용", "신규 수전신청")
    power_w: Optional[float] = None
    antenna_height_m: float = DEFAULT_ANTENNA_HEIGHT_M  # GUI에서 사용자가 직접 수정 가능한 값임

    # 아래부터 GUI 링크버짓 편집용 무선 파라미터임. 전부 GUI에서 개별 수정 가능.
    tx_power_dbm: float = DEFAULT_GW_TX_POWER_DBM
    antenna_gain_dbi: float = DEFAULT_GW_ANTENNA_GAIN_DBI
    cable_loss_db: float = DEFAULT_GW_CABLE_LOSS_DB
    enabled: bool = True            # GUI 체크박스로 이 GW를 분석에서 껐다 켰다 할 수 있게 하는 플래그

    comm_type: str = "LTE"         # 통신 방식 (예: "LTE", "자가&LTE", "KT&LTE")
    source_sheet: str = ""         # 어느 엑셀 시트에서 왔는지 (디버깅용 추적 정보)
    notes: str = ""


@dataclass
class NodeSite:
    """단말(Node) 위치 정보임."""
    node_id: str                   # 관리번호 (없으면 순번 기반 임시 ID 부여) - GUI에서 callsign처럼 표시용으로도 씀
    region: str
    location_desc: str
    lat: float
    lon: float
    device_type: str               # 설치물 유형 (예: "하천복합센서", "CCTV", "AI 영상 엣지 박스")
    install_type: str              # 설치방법 (예: "교량 슬라브 설치", "맨홀 내 설치")
    power_w: Optional[float] = None
    antenna_height_m: float = DEFAULT_ANTENNA_HEIGHT_M  # GUI에서 사용자가 직접 수정 가능한 값임

    # 아래부터 GUI 링크버짓 편집용 무선 파라미터임.
    antenna_gain_dbi: float = DEFAULT_NODE_ANTENNA_GAIN_DBI
    cable_loss_db: float = DEFAULT_NODE_CABLE_LOSS_DB
    min_rx_dbm: float = DEFAULT_NODE_MIN_RX_DBM       # 참고용 표시값 - 실제 연결 판정은 evaluate_connection의 SF 기준으로 함
    indoor_loss_db: float = DEFAULT_NODE_INDOOR_LOSS_DB

    source_sheet: str = ""
    notes: str = ""