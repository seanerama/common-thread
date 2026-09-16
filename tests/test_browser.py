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


@pytest.mark.browser
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("old_features", [False, True])
def test_party_directory_browser(live_server, owners, tmp_path, settings, old_features):
    settings.PARTY_DIRECTORY_ENABLED = True
    settings.PEOPLE_MANAGEMENT_ENABLED = old_features
    settings.CONTEXT_NOTES_ENABLED = old_features
    record = tmp_path / "fictional-parties.json"
    common = {
        "people_management": "on" if old_features else "off",
        "context_notes": "on" if old_features else "off",
    }
    smoke(
        live_server.url,
        "fictional_owner",
        "Fictional-passphrase-725!",
        record_file=record,
        party_directory="on",
        **common,
    )
    smoke(
        live_server.url,
        "fictional_owner",
        "Fictional-passphrase-725!",
        read_file=record,
        party_directory="on",
        **common,
    )
    settings.PARTY_DIRECTORY_ENABLED = False
    smoke(
        live_server.url,
        "fictional_owner",
        "Fictional-passphrase-725!",
        read_file=record,
        party_directory="off",
        **common,
    )
    settings.PARTY_DIRECTORY_ENABLED = True
    smoke(
        live_server.url,
        "fictional_owner",
        "Fictional-passphrase-725!",
        read_file=record,
        party_directory="on",
        **common,
    )


@pytest.mark.browser
@pytest.mark.django_db(transaction=True)
def test_relationships_browser_and_independent_flags(
    live_server, owners, tmp_path, settings
):
    settings.PARTY_DIRECTORY_ENABLED = True
    settings.RELATIONSHIPS_ENABLED = True
    record = tmp_path / "fictional-relationships.json"
    smoke(
        live_server.url,
        "fictional_owner",
        "Fictional-passphrase-725!",
        record_file=record,
        party_directory="on",
        relationships="on",
    )
    smoke(
        live_server.url,
        "fictional_owner",
        "Fictional-passphrase-725!",
        read_file=record,
        party_directory="on",
        relationships="on",
    )
    settings.PARTY_DIRECTORY_ENABLED = False
    smoke(
        live_server.url,
        "fictional_owner",
        "Fictional-passphrase-725!",
        read_file=record,
        party_directory="off",
        relationships="on",
    )
    settings.RELATIONSHIPS_ENABLED = False
    smoke(
        live_server.url,
        "fictional_owner",
        "Fictional-passphrase-725!",
        read_file=record,
        party_directory="off",
        relationships="off",
    )


@pytest.mark.browser
@pytest.mark.django_db(transaction=True)
def test_interactions_browser_and_independent_flags(
    live_server, owners, tmp_path, settings
):
    settings.PARTY_DIRECTORY_ENABLED = False
    settings.RELATIONSHIPS_ENABLED = False
    settings.INTERACTIONS_ENABLED = True
    record = tmp_path / "fictional-interactions.json"
    smoke(
        live_server.url,
        "fictional_owner",
        "Fictional-passphrase-725!",
        record_file=record,
        interactions="on",
    )
    smoke(
        live_server.url,
        "fictional_owner",
        "Fictional-passphrase-725!",
        read_file=record,
        interactions="on",
    )
    settings.INTERACTIONS_ENABLED = False
    smoke(
        live_server.url,
        "fictional_owner",
        "Fictional-passphrase-725!",
        read_file=record,
        interactions="off",
    )
    settings.PARTY_DIRECTORY_ENABLED = True
    settings.INTERACTIONS_ENABLED = True
    smoke(
        live_server.url,
        "fictional_owner",
        "Fictional-passphrase-725!",
        read_file=record,
        party_directory="on",
        interactions="on",
    )
