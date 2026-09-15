# lorascape/data/schema.py
"""
Node/GW 공통 데이터 구조 정의임.
엑셀에서 뭘 읽어오든 결국 이 형태로 통일해서 core 계산 함수들에 넘겨줌.
core 쪽(song_model, deygout 등)은 이 dataclass만 알면 되고, 엑셀 구조는 몰라도 됨
-> 나중에 엑셀 양식이 바뀌어도 core는 안 건드려도 되는 구조.
"""
from dataclasses import dataclass
from typing import Optional

# 안테나 높이 기본값임. 실측값이 없어서 일단 이 값으로 깔아두고,
# GUI에서 사용자가 GW/Node 하나하나 선택해서 직접 값을 수정할 수 있게 만들 예정임.
# (즉 이 상수는 '최초 로딩 시 초기값'일 뿐이고, 최종 계산에 쓰이는 값은 사용자가 고친 값임)
DEFAULT_ANTENNA_HEIGHT_M = 1.5


@dataclass
class GatewaySite:
    """GW(게이트웨이) 후보/설치 위치 정보임."""
    gw_id: str                     # 관리번호 또는 일련번호 (예: "수정고등-A-64")
    region: str                    # 지역 (탄천/중앙공원/율동공원/위례공원/서판교)
    location_desc: str             # 상세위치 (예: "여수대교 인근")
    lat: float
    lon: float
    install_type: str              # 설치방법 원본 텍스트 (예: "기존 CCTV폴에 설치", "신규설치")
    power_source: str              # 전원 공급 방안 (예: "CCTV폴 전원 사용", "신규 수전신청")
    power_w: Optional[float] = None
    antenna_height_m: float = DEFAULT_ANTENNA_HEIGHT_M  # GUI에서 사용자가 직접 수정 가능한 값임
    comm_type: str = "LTE"         # 통신 방식 (예: "LTE", "자가&LTE", "KT&LTE")
    source_sheet: str = ""         # 어느 엑셀 시트에서 왔는지 (디버깅용 추적 정보)
    notes: str = ""


@dataclass
class NodeSite:
    """단말(Node) 위치 정보임."""
    node_id: str                   # 관리번호 (없으면 순번 기반 임시 ID 부여)
    region: str
    location_desc: str
    lat: float
    lon: float
    device_type: str               # 설치물 유형 (예: "하천복합센서", "CCTV", "AI 영상 엣지 박스")
    install_type: str              # 설치방법 (예: "교량 슬라브 설치", "맨홀 내 설치")
    power_w: Optional[float] = None
    antenna_height_m: float = DEFAULT_ANTENNA_HEIGHT_M  # GUI에서 사용자가 직접 수정 가능한 값임
    source_sheet: str = ""
    notes: str = ""