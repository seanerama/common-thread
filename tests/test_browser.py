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


@pytest.mark.browser
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("management", [False, True])
def test_context_notes_browser(live_server, owners, tmp_path, settings, management):
    settings.PEOPLE_MANAGEMENT_ENABLED = management
    settings.CONTEXT_NOTES_ENABLED = True
    record = tmp_path / "fictional-notes.json"
    common = dict(people_management="on" if management else "off")
    smoke(
        live_server.url,
        "fictional_owner",
        "Fictional-passphrase-725!",
        record_file=record,
        context_notes="on",
        **common,
    )
    smoke(
        live_server.url,
        "fictional_owner",
        "Fictional-passphrase-725!",
        read_file=record,
        context_notes="on",
        **common,
    )
    settings.CONTEXT_NOTES_ENABLED = False
    smoke(
        live_server.url,
        "fictional_owner",
        "Fictional-passphrase-725!",
        read_file=record,
        context_notes="off",
        **common,
    )
    settings.CONTEXT_NOTES_ENABLED = True
    smoke(
        live_server.url,
        "fictional_owner",
        "Fictional-passphrase-725!",
        read_file=record,
        context_notes="on",
        **common,
    )
