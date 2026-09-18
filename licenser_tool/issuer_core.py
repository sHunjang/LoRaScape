# lorascape/license/issuer_core.py
"""
인증코드 발급 핵심 로직임. verifier.py의 generate_auth_code와 완전히 동일한
알고리즘을 써야만 발급된 코드가 본체에서 검증됨 - 그래서 normalize.py와 똑같이
이 파일도 licenser_tool/에 동기화되어야 함 (scripts/sync_license_shared.ps1 참고).

try/except import는 이 파일이 두 군데(패키지 안 lorascape/license/, 그리고
독립 스크립트 폴더 licenser_tool/)에서 그대로 동작해야 해서 필요함 - 패키지
컨텍스트에서는 절대경로 import가, 독립 스크립트 컨텍스트에서는 같은 폴더의
normalize.py를 바로 import하는 게 필요함.
"""
import hashlib
import hmac
import secrets

try:
    from lorascape.license.normalize import normalize_name
except ImportError:
    from normalize import normalize_name


def generate_secret_key(length: int = 32) -> str:
    """
    새 비밀키를 무작위로 생성함. secrets 모듈을 씀 (random 모듈은 암호용으로 부적합).
    hex 문자열로 반환해서 license.key 파일에 그대로 텍스트로 저장 가능하게 함.
    """
    return secrets.token_hex(length)


def generate_auth_code(secret_key: bytes, company_name: str) -> str:
    """
    회사명 기반 인증코드를 생성함. verifier.py의 동일 함수와 반드시 알고리즘이
    같아야 함 - 여기서 만든 코드가 본체(verifier.verify_auth_code)에서
    검증되어야 하니까.
    """
    normalized_name = normalize_name(company_name)
    signature = hmac.new(secret_key, normalized_name.encode("utf-8"), hashlib.sha256)
    raw_code = signature.hexdigest().upper()[:32]
    return "-".join(raw_code[i:i + 8] for i in range(0, len(raw_code), 8))