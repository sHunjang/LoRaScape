# lorascape/data/site_inventory.py
"""
'_AIoT_실증__현장_설치_인프라_총괄표.xlsx' 파일을 읽어서
GatewaySite / NodeSite 리스트로 변환하는 모듈임.

이 엑셀은 헤더가 2줄짜리 구조임 (1행: 대분류 '기본 정보'/'설치'/'전원'/'통신'/'기타',
2행: 실제 컬럼명). pandas로 읽을 때 header=1로 2번째 행을 컬럼명으로 잡아야 함.

★ 엑셀 로딩 실패 시 명확한 에러를 던지도록 개선함 - 예전엔 필요한 시트가
하나도 없으면 조용히 빈 리스트를 반환해서, 사용자가 "왜 아무 반응이 없지?"
하고 헤매게 됨. 지금은 시트 목록부터 검사해서 원인을 정확히 알려줌.
"""
import math
import pandas as pd
from lorascape.data.schema import GatewaySite, NodeSite, DEFAULT_ANTENNA_HEIGHT_M

# GW 위치로 취급할 시트 이름들임. '스마트폴'은 GW를 얹는 폴이라 GW 후보지로 취급하고,
# 'RF 게이트웨이'가 실제 LoRa GW 설치 위치의 원본 데이터임.
GATEWAY_SHEETS = ["RF 게이트웨이", "스마트폴"]

# Node(단말)로 취급할 시트들임.
NODE_SHEETS = ["센서", "CCTV, MIC", "AI 엣지 박스", "기타 시설물"]


def _clean(value):
    """
    엑셀 셀 값 정리 함수임. '-' 나 빈 문자열, NaN을 전부 None으로 통일함.

    float NaN(엑셀 빈 셀이 pandas에서 NaN으로 읽히는 경우, 특히 좌표 컬럼)을
    문자열 빈값과 함께 처리해야 함 - 이걸 놓치면 NaN 좌표가 그대로 흘러들어가서
    K-means 같은 후속 계산에서 "Input X contains NaN" 에러로 터짐.
    """
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, str) and value.strip() in ("", "-", "TBD", "n/a"):
        return None
    return value


def load_gateways(xlsx_path: str) -> list[GatewaySite]:
    """
    총괄표 엑셀에서 GW 후보/설치 위치를 전부 읽어옴.
    안테나 높이는 일단 DEFAULT_ANTENNA_HEIGHT_M(1.5m)로 통일해서 넣어두고,
    GUI에서 사용자가 개별 GW 선택해서 값을 고칠 수 있음.

    엑셀에 GATEWAY_SHEETS 중 어느 것도 없으면 ValueError를 던짐 (조용히 빈 리스트
    반환하지 않음 - 호출부에서 이 예외를 잡아 사용자에게 원인을 그대로 보여줘야 함).
    """
    xl = pd.ExcelFile(xlsx_path)
    available_sheets = set(xl.sheet_names)
    matched_sheets = [s for s in GATEWAY_SHEETS if s in available_sheets]

    if not matched_sheets:
        raise ValueError(
            f"이 엑셀 파일에서 GW 데이터를 찾을 수 없습니다.\n"
            f"필요한 시트: {', '.join(GATEWAY_SHEETS)}\n"
            f"이 파일의 시트 목록: {', '.join(xl.sheet_names)}"
        )

    result = []
    for sheet in matched_sheets:
        df = pd.read_excel(xlsx_path, sheet_name=sheet, header=1)

        for idx, row in df.iterrows():
            lat = _clean(row.get("위도"))
            lon = _clean(row.get("경도"))
            if lat is None or lon is None:
                # 좌표 없는 행(빈 줄, 합계 줄 등)은 건너뜀
                continue

            gw = GatewaySite(
                gw_id=str(_clean(row.get("관리번호")) or f"{sheet}_{idx}"),
                region=str(_clean(row.get("지역")) or ""),
                location_desc=str(_clean(row.get("상세위치")) or ""),
                lat=float(lat),
                lon=float(lon),
                install_type=str(_clean(row.get("설치 방법")) or ""),
                power_source=str(_clean(row.get("전원 공급 방안")) or ""),
                power_w=_clean(row.get("소비전력(W)")),
                antenna_height_m=DEFAULT_ANTENNA_HEIGHT_M,
                comm_type=str(_clean(row.get("구분")) or "LTE"),
                source_sheet=sheet,
                notes=str(_clean(row.get("비고")) or ""),
            )
            result.append(gw)

    if not result:
        raise ValueError(
            f"'{', '.join(matched_sheets)}' 시트는 찾았지만, "
            f"위도/경도가 있는 유효한 행이 하나도 없습니다."
        )

    return result


def load_nodes(xlsx_path: str) -> list[NodeSite]:
    """총괄표 엑셀에서 Node(단말) 위치를 전부 읽어옴. load_gateways랑 검증 로직 동일함."""
    xl = pd.ExcelFile(xlsx_path)
    available_sheets = set(xl.sheet_names)
    matched_sheets = [s for s in NODE_SHEETS if s in available_sheets]

    if not matched_sheets:
        raise ValueError(
            f"이 엑셀 파일에서 Node 데이터를 찾을 수 없습니다.\n"
            f"필요한 시트: {', '.join(NODE_SHEETS)}\n"
            f"이 파일의 시트 목록: {', '.join(xl.sheet_names)}"
        )

    result = []
    for sheet in matched_sheets:
        df = pd.read_excel(xlsx_path, sheet_name=sheet, header=1)

        for idx, row in df.iterrows():
            lat = _clean(row.get("위도"))
            lon = _clean(row.get("경도"))
            if lat is None or lon is None:
                continue

            node = NodeSite(
                node_id=str(_clean(row.get("관리번호")) or f"{sheet}_{idx}"),
                region=str(_clean(row.get("지역")) or ""),
                location_desc=str(_clean(row.get("상세위치")) or ""),
                lat=float(lat),
                lon=float(lon),
                device_type=str(_clean(row.get("설치물 유형")) or ""),
                install_type=str(_clean(row.get("설치 방법")) or ""),
                power_w=_clean(row.get("소비전력(W)")),
                antenna_height_m=DEFAULT_ANTENNA_HEIGHT_M,
                source_sheet=sheet,
                notes=str(_clean(row.get("비고")) or ""),
            )
            result.append(node)

    if not result:
        raise ValueError(
            f"'{', '.join(matched_sheets)}' 시트는 찾았지만, "
            f"위도/경도가 있는 유효한 행이 하나도 없습니다."
        )

    return result