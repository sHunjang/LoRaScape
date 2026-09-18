"""issuer_core.py 검증 테스트임 - verifier.py와 알고리즘이 일치하는지도 확인함."""
from lorascape.license.issuer_core import generate_secret_key, generate_auth_code
from lorascape.license.verifier import verify_auth_code


def test_generate_secret_key_produces_hex_string():
    key = generate_secret_key()
    assert isinstance(key, str)
    int(key, 16)  # hex로 파싱 가능해야 함 (아니면 예외 발생)


def test_generate_secret_key_is_random():
    assert generate_secret_key() != generate_secret_key()


def test_generate_auth_code_deterministic_for_same_input():
    secret = b"fixed-secret"
    code1 = generate_auth_code(secret, "회사명")
    code2 = generate_auth_code(secret, "회사명")
    assert code1 == code2


def test_generate_auth_code_issued_here_verifies_in_verifier():
    """
    이 파일(issuer_core)에서 발급한 코드가 verifier.verify_auth_code로 실제 검증되는지 확인함.
    두 파일의 알고리즘이 어긋나면 이 테스트가 바로 잡아냄 (가장 중요한 회귀 방지 테스트).
    """
    secret = generate_secret_key().encode("utf-8")
    company = "테스트 발급 회사"
    code = generate_auth_code(secret, company)

    result = verify_auth_code(secret, company, code)
    assert result.is_valid is True