# lorascape/license/verifier.py
"""
로컬 HMAC-SHA256 기반 라이선스 인증 검증 모듈임.
서버 없이 동작해야 해서, 발급 프로그램(licenser_tool)이 미리 비밀키로 서명한 인증코드를
본체 프로그램이 같은 비밀키로 재계산해서 비교하는 방식임.

핵심 설계:
  - 비밀키는 exe에 내장 안 하고, exe 옆의 외부 파일(license.key)에서 읽어옴
  - 인증코드 비교 전에 반드시 normalize.py로 양쪽 다 정규화해서 비교함
    (이게 문서 5번 요구사항의 핵심 - 붙여넣기 실패 재발 방지)
  - 디버그 모드에서는 실패 시 입력값/기대값을 나란히 로그로 남김 (배포판에서는 숨김)

★ generate_auth_code는 issuer_core.py에서 그대로 가져다 씀 (재수출) - 발급
로직(licenser_tool)과 검증 로직(본체)이 같은 알고리즘을 반드시 써야 하는데,
예전엔 이 파일에 직접 구현되어 있어서 issuer_core.py와 따로 관리되다가
알고리즘이 갈라질 위험이 있었음. 지금은 issuer_core.py 하나로 합쳐서
양쪽 다 그 함수를 참조함.
"""
import hmac
import logging
from dataclasses import dataclass
from pathlib import Path

from lorascape.license.normalize import normalize_code, normalize_name
from lorascape.license.issuer_core import generate_auth_code  # noqa: F401 (호환성 유지용 재수출)

logger = logging.getLogger("lorascape.license")


@dataclass
class LicenseVerifyResult:
    """인증 검증 결과임. 성공/실패 여부와 디버그용 상세 정보를 같이 담음."""
    is_valid: bool
    reason: str = ""              # 실패 사유 (사용자에게 보여줄 간단한 메시지)
    debug_expected: str = ""      # 디버그 모드에서만 채워짐 (정규화된 기대값)
    debug_actual: str = ""        # 디버그 모드에서만 채워짐 (정규화된 입력값)


def load_secret_key(key_file_path: str) -> bytes:
    """
    exe 옆의 license.key 파일에서 비밀키를 읽어옴.
    파일이 없거나 비어있으면 명확한 에러를 던짐 (조용히 넘어가면 나중에 디버깅 지옥이라서).

    ★ 버그 수정: 인코딩을 "utf-8"로 읽으면 Windows PowerShell(Out-File -Encoding utf8)이
    파일 앞에 붙이는 BOM(\ufeff) 문자를 걸러내지 못해서, 비밀키 값이 미묘하게 달라져
    HMAC 서명 자체가 틀어지는 문제가 있었음. "utf-8-sig"로 읽으면 BOM이 있으면
    자동으로 제거하고, 없으면 그냥 일반 UTF-8처럼 동작해서 양쪽 다 안전함.
    """
    path = Path(key_file_path)
    if not path.exists():
        raise FileNotFoundError(
            f"라이선스 키 파일을 찾을 수 없음: {key_file_path} "
            f"(exe와 같은 폴더에 license.key가 있는지 확인 필요)"
        )

    content = path.read_text(encoding="utf-8-sig").strip()
    if not content:
        raise ValueError(f"라이선스 키 파일이 비어있음: {key_file_path}")

    return content.encode("utf-8")


def verify_auth_code(
    secret_key: bytes,
    company_name: str,
    input_auth_code: str,
    debug_mode: bool = False,
) -> LicenseVerifyResult:
    """
    사용자가 입력한 인증코드를 검증함. 본체 프로그램에서 이 함수를 씀.

    비교 순서가 중요함:
      1. 기대값(expected)을 회사명+비밀키로 재계산
      2. 기대값과 입력값 둘 다 normalize_code()로 정규화
      3. 정규화된 문자열끼리 비교

    debug_mode=True면 실패 시 정규화된 양쪽 값을 결과 객체에 담아서 반환함
    (배포판에서는 반드시 False로 둬서 이 정보가 사용자 화면에 노출 안 되게 해야 함).
    """
    expected_code = generate_auth_code(secret_key, company_name)

    expected_normalized = normalize_code(expected_code)
    actual_normalized = normalize_code(input_auth_code)

    is_valid = hmac.compare_digest(expected_normalized, actual_normalized)
    # hmac.compare_digest를 쓰는 이유: 일반 == 비교는 문자열 길이/내용에 따라 비교 시간이 미세하게
    # 달라져서 타이밍 공격에 취약할 수 있음. 로컬 검증이라 실질적 위협은 낮지만, 습관적으로
    # 비밀값 비교에는 항상 이 방식을 쓰는 게 안전함.

    if is_valid:
        logger.info("라이선스 인증 성공 (회사명: %s)", company_name)
        return LicenseVerifyResult(is_valid=True)

    # 실패 로그: 디버그 모드가 아니면 상세 값은 절대 안 남김 (배포판 유출 방지)
    if debug_mode:
        logger.debug(
            "라이선스 인증 실패 - 입력값(정규화): %s / 기대값(정규화): %s",
            actual_normalized, expected_normalized,
        )
        return LicenseVerifyResult(
            is_valid=False,
            reason="인증코드가 일치하지 않습니다.",
            debug_expected=expected_normalized,
            debug_actual=actual_normalized,
        )
    else:
        logger.warning("라이선스 인증 실패 (회사명: %s)", company_name)
        return LicenseVerifyResult(is_valid=False, reason="인증코드가 일치하지 않습니다.")