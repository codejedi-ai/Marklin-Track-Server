from ingest import normalize as N


def test_os_canonicalization():
    assert N.normalize_os("macOS Ventura")[0] == "macOS"
    assert N.normalize_os("macos")[0] == "macOS"
    assert N.normalize_os("macOS Sonoma 14.5") == ("macOS", "Sonoma 14.5")
    assert N.normalize_os("Ubuntu 22.04 LTS")[0] == "Ubuntu"
    assert N.normalize_os(None) == (None, None)


def test_status_enum():
    assert N.normalize_status("active") == "active"
    assert N.normalize_status("ACTIVE") == "active"
    assert N.normalize_status("deactivated") == "inactive"
    assert N.normalize_status("inactive") == "inactive"


def test_encryption_to_bool():
    assert N.normalize_encryption("FileVault Enabled") is True
    assert N.normalize_encryption("FileVault 2") is True
    assert N.normalize_encryption("LUKS Full Disk Encryption") is True
    assert N.normalize_encryption(True) is True
    assert N.normalize_encryption("none") is False
    assert N.normalize_encryption(None) is None


def test_name_and_key():
    assert N.normalize_name("  John   D. ") == "John D."
    assert N.norm_key("Slack") == "slack"
    assert N.normalize_email("John.D@Example.com ") == "john.d@example.com"
