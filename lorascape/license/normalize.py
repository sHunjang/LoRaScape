"""
인증코드 / 회사명 정규화 규칙 모듈임.

★★★ 중요 ★★★
이 파일은 licenser_tool\\normalize.py 랑 반드시 100% 똑같이 유지되어야 함.
발급 프로그램(licenser_tool)이랑 인증 프로그램(본체)이 서로 다른 정규화 규칙을 쓰면
"분명히 방금 발급받은 코드인데 인증 실패"하는 문제가 재발함 - 이게 예전 프로젝트에서
계속 터졌던 버그의 원인이었음.

수정할 일 생기면 여기 고치고 나서 scripts\\sync_normalize.ps1로 licenser_tool 쪽도
같이 동기화해야 함. 한쪽만 고치면 바로 사고남.
"""
import re
import unicodedata

# 눈에 안 보이는 유니코드 문자들임. 복사/붙여넣기 할 때 클립보드에 섞여 들어오는 경우가 은근 많음.
ZERO_WIDTH_CHARS = ["\u200b", "\u200c", "\u200d", "\ufeff"]


def normalize_code(raw: str) -> str:
    """
    인증코드 문자열 정규화 함수임.
    처리 순서: 앞뒤 공백 제거 -> 눈에 안 보이는 문자 제거 -> 하이픈 제거 -> 중간 공백/개행 제거 -> 대문자 통일

    "ABCDE-FGHIJ" 랑 "abcde fghij" 랑 " ABCDEFGHIJ\n" 이 셋 다 같은 값으로 취급되게 만드는 게 목적임.
    """
    if raw is None:
        return ""
    s = raw.strip()
    for zw in ZERO_WIDTH_CHARS:
        s = s.replace(zw, "")
    s = s.replace("-", "")
    s = re.sub(r"\s+", "", s)  # 중간에 탭이나 개행 섞여 들어와도 다 제거
    s = s.upper()
    return s


def normalize_name(raw: str) -> str:
    """
    회사명/사용자명 정규화 함수임. normalize_code랑 규칙이 살짝 다름
    (이쪽은 단어 사이 공백은 1칸으로 남겨둠 - 회사명은 붙여쓰면 안 되니까).

    NFKC 정규화 넣은 이유: 전각/반각 문자나 자모 결합 형태가 다르게 입력돼도
    같은 문자로 인식되게 하기 위함 (한글/특수문자 섞인 회사명 대응).
    """
    if raw is None:
        return ""
    s = raw.strip()
    for zw in ZERO_WIDTH_CHARS:
        s = s.replace(zw, "")
    s = re.sub(r"\s+", " ", s)  # 여러 칸 공백은 1칸으로 압축
    s = unicodedata.normalize("NFKC", s)
    return s.upper()