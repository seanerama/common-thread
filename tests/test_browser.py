import pytest

from scripts.browser_smoke import smoke


@pytest.mark.browser
@pytest.mark.django_db(transaction=True)
def test_real_browser_login_create_reload(live_server, owners, tmp_path):
    record = tmp_path / "fictional-person.json"
    smoke(
        live_server.url,
        "fictional_owner",
        "Fictional-passphrase-725!",
        record_file=record,
    )
    # New browser session and HTTP navigation, independent of creation-page state.
    smoke(
        live_server.url,
        "fictional_owner",
        "Fictional-passphrase-725!",
        read_file=record,
    )
