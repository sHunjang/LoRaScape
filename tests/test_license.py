"""
license/verifier.py 검증 테스트임.
문서에 명시된 4가지 시나리오를 그대로 테스트로 옮김:
  1. 새로 생성한 비밀키로 발급한 코드가 즉시 인증되는지
  2. 기존 비밀키를 다시 불러와 발급한 코드가 인증되는지
  3. 회사명에 공백/특수문자 섞여도 정상 동작하는지
  4. 인증코드 복사 시 앞뒤 공백/개행 섞여도 정상 인증되는지
"""
import pytest
from lorascape.license.verifier import (
    generate_auth_code,
    verify_auth_code,
    load_secret_key,
    LicenseVerifyResult,
)

SECRET = b"test-secret-key-for-unit-test"


def test_scenario1_freshly_generated_code_verifies_immediately():
    """시나리오 1: 새로 생성한 비밀키로 발급한 코드가 즉시 인증되는지."""
    company = "테스트 주식회사"
    code = generate_auth_code(SECRET, company)
    result = verify_auth_code(SECRET, company, code)
    assert result.is_valid is True


def test_scenario2_key_reloaded_from_file_still_verifies(tmp_path):
    """시나리오 2: 기존에 발급해둔 비밀키를 파일에서 다시 불러와도 인증되는지."""
    key_file = tmp_path / "license.key"
    key_file.write_text("my-persisted-secret-key", encoding="utf-8")

    # 발급 시점: 키 파일에서 로드해서 코드 생성
    loaded_key_1 = load_secret_key(str(key_file))
    company = "성남시"
    code = generate_auth_code(loaded_key_1, company)

    # 인증 시점: 같은 키 파일을 다시(별도로) 로드해서 검증 - 파일 재로딩 시나리오 재현
    loaded_key_2 = load_secret_key(str(key_file))
    result = verify_auth_code(loaded_key_2, company, code)
    assert result.is_valid is True


def test_scenario3_company_name_with_spaces_and_special_chars():
    """시나리오 3: 회사명에 공백/특수문자 섞여도 정상 동작하는지."""
    company = "  (주) 솔루윈스 - 성남지사  "
    code = generate_auth_code(SECRET, company)
    result = verify_auth_code(SECRET, company, code)
    assert result.is_valid is True

    # 공백 표기가 살짝 다른 버전으로 검증해도 같은 결과가 나와야 함 (normalize_name 덕분)
    company_variant = "(주)솔루윈스-성남지사"
    result_variant = verify_auth_code(SECRET, company_variant, code)
    assert result_variant.is_valid is True


def test_scenario4_auth_code_with_surrounding_whitespace_and_newlines():
    """시나리오 4: 인증코드 복사 시 앞뒤 공백/개행 섞여도 정상 인증되는지."""
    company = "테스트 주식회사"
    code = generate_auth_code(SECRET, company)

    messy_code = f"  \n{code}\n\t  "  # 복사 실수로 공백/개행이 섞인 상황 재현
    result = verify_auth_code(SECRET, company, messy_code)
    assert result.is_valid is True


def test_lowercase_and_no_hyphen_code_also_verifies():
    """추가 케이스: 소문자로 입력하거나 하이픈을 뺀 경우도 인증돼야 함."""
    company = "테스트 주식회사"
    code = generate_auth_code(SECRET, company)

    lowercase_no_hyphen = code.replace("-", "").lower()
    result = verify_auth_code(SECRET, company, lowercase_no_hyphen)
    assert result.is_valid is True


def test_wrong_code_fails_verification():
    """당연히 틀린 코드는 실패해야 함 - 항상 성공하는 버그 방지용."""
    company = "테스트 주식회사"
    generate_auth_code(SECRET, company)  # 정상 코드는 생성만 하고 안 씀
    result = verify_auth_code(SECRET, company, "COMPLETELY-WRONG-CODE-000000")
    assert result.is_valid is False
    assert result.reason != ""


def test_wrong_company_name_fails_verification():
    """다른 회사명으로 발급된 코드는 인증 실패해야 함."""
    code = generate_auth_code(SECRET, "성남시")
    result = verify_auth_code(SECRET, "다른회사", code)
    assert result.is_valid is False


def test_debug_mode_exposes_expected_and_actual_values():
    """디버그 모드에서만 정규화된 기대값/입력값이 결과에 채워지는지 확인."""
    company = "테스트 주식회사"
    result = verify_auth_code(SECRET, company, "WRONG-CODE", debug_mode=True)
    assert result.is_valid is False
    assert result.debug_expected != ""
    assert result.debug_actual != ""


def test_non_debug_mode_hides_expected_and_actual_values():
    """일반 모드(배포판 시뮬레이션)에서는 상세 값이 노출되면 안 됨."""
    company = "테스트 주식회사"
    result = verify_auth_code(SECRET, company, "WRONG-CODE", debug_mode=False)
    assert result.is_valid is False
    assert result.debug_expected == ""
    assert result.debug_actual == ""


def test_load_secret_key_raises_when_file_missing():
    with pytest.raises(FileNotFoundError):
        load_secret_key("nonexistent_path/license.key")


def test_load_secret_key_raises_when_file_empty(tmp_path):
    empty_file = tmp_path / "empty.key"
    empty_file.write_text("", encoding="utf-8")
    with pytest.raises(ValueError):
        load_secret_key(str(empty_file))