import pytest

from scripts.browser_smoke import smoke


@pytest.mark.browser
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("enabled", [False, True])
def test_real_browser_login_create_reload(
    live_server, owners, tmp_path, settings, enabled
):
    settings.PEOPLE_MANAGEMENT_ENABLED = enabled
    record = tmp_path / "fictional-person.json"
    smoke(
        live_server.url,
        "fictional_owner",
        "Fictional-passphrase-725!",
        record_file=record,
        people_management="on" if enabled else "off",
    )
    # New browser session and HTTP navigation, independent of creation-page state.
    smoke(
        live_server.url,
        "fictional_owner",
        "Fictional-passphrase-725!",
        read_file=record,
        people_management="on" if enabled else "off",
    )

    if enabled:
        settings.PEOPLE_MANAGEMENT_ENABLED = False
        smoke(
            live_server.url,
            "fictional_owner",
            "Fictional-passphrase-725!",
            read_file=record,
        )
        settings.PEOPLE_MANAGEMENT_ENABLED = True
        smoke(
            live_server.url,
            "fictional_owner",
            "Fictional-passphrase-725!",
            read_file=record,
            people_management="on",
        )
