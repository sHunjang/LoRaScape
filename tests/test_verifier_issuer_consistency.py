"""verifier.py와 issuer_core.py가 같은 generate_auth_code를 참조하는지 확인함 (중복 제거 검증)."""
from lorascape.license import verifier, issuer_core


def test_verifier_reexports_same_function_as_issuer_core():
    assert verifier.generate_auth_code is issuer_core.generate_auth_code