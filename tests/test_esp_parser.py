from helpers import build_esp_bytes

from mod_manager.diagnostics import esp_parser


def test_parses_masters_in_order(tmp_path):
    path = tmp_path / "Test.esp"
    path.write_bytes(build_esp_bytes(["Fallout4.esm", "DLCRobot.esm"]))
    header = esp_parser.parse_header(path)
    assert header.error is None
    assert header.is_master_style is True
    assert header.masters == ["Fallout4.esm", "DLCRobot.esm"]
    assert header.author == "test"
    assert header.is_light is False


def test_parses_esl_flag(tmp_path):
    path = tmp_path / "Light.esp"
    path.write_bytes(build_esp_bytes(["Fallout4.esm"], is_light=True))
    header = esp_parser.parse_header(path)
    assert header.is_light is True


def test_no_masters_is_valid(tmp_path):
    path = tmp_path / "NoMasters.esp"
    path.write_bytes(build_esp_bytes([]))
    header = esp_parser.parse_header(path)
    assert header.masters == []
    assert header.error is None


def test_truncated_file_reports_error_not_exception(tmp_path):
    path = tmp_path / "Truncated.esp"
    full = build_esp_bytes(["Fallout4.esm"])
    path.write_bytes(full[:20])  # cut off mid record-header
    header = esp_parser.parse_header(path)
    assert header.error is not None
    assert header.masters == []


def test_truncated_record_data_reports_error(tmp_path):
    path = tmp_path / "TruncatedData.esp"
    full = build_esp_bytes(["Fallout4.esm", "DLCRobot.esm"])
    path.write_bytes(full[:30])  # header ok, data cut short
    header = esp_parser.parse_header(path)
    assert header.is_master_style is True
    assert header.error is not None


def test_non_esp_file_is_not_master_style(tmp_path):
    path = tmp_path / "NotAPlugin.esp"
    path.write_bytes(b"this is not a valid plugin file at all, just text padding")
    header = esp_parser.parse_header(path)
    assert header.is_master_style is False
    assert header.error is not None


def test_missing_file_reports_error(tmp_path):
    header = esp_parser.parse_header(tmp_path / "does_not_exist.esp")
    assert header.error is not None
