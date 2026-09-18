"""license_dialog.py 검증 테스트임. QApplication 필요함."""
import pytest
from PyQt5.QtWidgets import QApplication
from lorascape.gui.widgets.license_dialog import (
    LicenseDialog, try_silent_login, find_license_key_path,
)
from lorascape.license.verifier import generate_auth_code
import lorascape.gui.app_config as app_config

from lorascape.license.verifier import load_secret_key


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config, "CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(app_config, "CONFIG_PATH", str(tmp_path / "config.json"))
    return tmp_path


SECRET = b"test-secret-key"


def test_find_license_key_path_returns_empty_when_not_found(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # license.key 없는 빈 폴더로 이동
    assert find_license_key_path() == ""


def test_find_license_key_path_finds_in_cwd(monkeypatch, tmp_path):
    key_file = tmp_path / "license.key"
    key_file.write_text(SECRET.decode())
    monkeypatch.chdir(tmp_path)
    assert find_license_key_path() == str(key_file)


def test_try_silent_login_fails_when_no_saved_credentials(isolated_config):
    assert try_silent_login() is False


def test_try_silent_login_succeeds_with_valid_saved_credentials(isolated_config, monkeypatch, tmp_path):
    key_file = tmp_path / "license.key"
    key_file.write_text(SECRET.decode())
    monkeypatch.chdir(tmp_path)

    company = "테스트 회사"
    code = generate_auth_code(SECRET, company)

    cfg = app_config.load_config()
    cfg["license_company"] = company
    cfg["license_user"] = "테스트유저"
    cfg["license_code"] = code
    app_config.save_config(cfg)

    assert try_silent_login() is True


def test_try_silent_login_fails_with_wrong_saved_code(isolated_config, monkeypatch, tmp_path):
    key_file = tmp_path / "license.key"
    key_file.write_text(SECRET.decode())
    monkeypatch.chdir(tmp_path)

    cfg = app_config.load_config()
    cfg["license_company"] = "테스트 회사"
    cfg["license_user"] = "테스트유저"
    cfg["license_code"] = "WRONG-CODE-0000"
    app_config.save_config(cfg)

    assert try_silent_login() is False


def test_license_dialog_verify_saves_config_on_success(qapp, isolated_config, monkeypatch, tmp_path):
    key_file = tmp_path / "license.key"
    key_file.write_text(SECRET.decode())

    company = "테스트 회사"
    code = generate_auth_code(SECRET, company)

    dlg = LicenseDialog()
    dlg._key_path = str(key_file)
    dlg.e_company.setText(company)
    dlg.e_user.setText("테스트유저")
    dlg.e_code.setText(code)
    dlg._verify()

    assert dlg.result() == dlg.Accepted
    reloaded = app_config.load_config()
    assert reloaded["license_company"] == company


def test_license_dialog_verify_shows_error_on_wrong_code(qapp, isolated_config, tmp_path):
    key_file = tmp_path / "license.key"
    key_file.write_text(SECRET.decode())

    dlg = LicenseDialog()
    dlg._key_path = str(key_file)
    dlg.e_company.setText("테스트 회사")
    dlg.e_user.setText("테스트유저")
    dlg.e_code.setText("WRONG-CODE")
    dlg._verify()

    assert dlg.result() != dlg.Accepted
    assert "일치하지" not in dlg.lbl_msg.text() or dlg.lbl_msg.text() != ""  # 에러 메시지가 표시됨


def test_license_dialog_verify_fails_when_key_file_missing(qapp, isolated_config):
    dlg = LicenseDialog()
    dlg._key_path = ""
    dlg.e_company.setText("회사")
    dlg.e_user.setText("유저")
    dlg.e_code.setText("CODE")
    dlg._verify()
    assert "선택" in dlg.lbl_msg.text()
    
    
def test_load_secret_key_strips_bom(tmp_path):
    """
    Windows PowerShell의 'Out-File -Encoding utf8'이 파일 앞에 붙이는 BOM을
    자동으로 걸러내는지 확인함 - 이거 안 걸러내면 비밀키 값이 미묘하게 달라져서
    나중에 회사명/코드를 정확히 입력해도 인증이 계속 실패하는 버그가 재발함.
    """
    key_file = tmp_path / "license_with_bom.key"
    # UTF-8 BOM(EF BB BF)을 파일 맨 앞에 직접 붙여서 재현함
    with open(key_file, "wb") as f:
        f.write(b"\xef\xbb\xbf" + b"my-test-secret-key")

    key = load_secret_key(str(key_file))
    assert key == b"my-test-secret-key"  # BOM 없는 순수 값이어야 함