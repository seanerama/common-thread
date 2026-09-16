"""Real-browser operator smoke; record fictional data for a fresh restart read."""

import argparse
import json
import os
import re
from pathlib import Path
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright


def management_off(page, base_url, record):
    for name in ("Edit person", "Add contact"):
        expect(page.get_by_role("link", name=name, exact=True)).to_have_count(0)
    for name in ("Archive person", "Restore person"):
        expect(page.get_by_role("button", name=name, exact=True)).to_have_count(0)
    for suffix in ("edit/", "contact-points/new/"):
        response = page.goto(base_url + record["path"] + suffix)
        assert response.status == 404
    if "contact_edit_path" in record:
        response = page.goto(base_url + record["contact_edit_path"])
        assert response.status == 404
    page.goto(f"{base_url}/people/")
    expect(page.locator('[name="q"]')).to_have_count(0)
    expect(page.locator('[name="archived"]')).to_have_count(0)
    page.goto(base_url + record["path"])


def management_on(page, base_url, record):
    person_url = base_url + record["path"]
    page.get_by_role("link", name="Edit person", exact=True).click()
    stale = page.context.new_page()
    try:
        stale.goto(page.url)
        record["display_name"] += " Updated"
        page.get_by_label("Name", exact=True).fill(record["display_name"])
        page.get_by_label("Client", exact=True).check()
        page.get_by_role("button", name="Save person", exact=True).click()
        expect(page).to_have_url(person_url)
        stale.get_by_label("Name", exact=True).fill("Fictional stale overwrite")
        with stale.expect_navigation() as conflict:
            stale.get_by_role("button", name="Save person", exact=True).click()
        assert conflict.value.status == 409
        expect(stale.get_by_role("alert")).to_contain_text(re.compile("reload", re.I))
        expect(stale.get_by_label("Name", exact=True)).to_have_value(
            "Fictional stale overwrite"
        )
        page.reload()
        expect(
            page.get_by_role("heading", name=record["display_name"], exact=True)
        ).to_be_visible()
        page.get_by_role("link", name="Edit person", exact=True).click()
        expect(page.get_by_label("Client", exact=True)).to_be_checked()
        page.goto(person_url)
        page.get_by_role("link", name="Add contact", exact=True).click()
        page.get_by_label("Kind", exact=True).select_option("email")
        page.get_by_label("Value", exact=True).fill(
            f"fictional-{uuid4().hex}@example.invalid"
        )
        page.get_by_label("Label", exact=True).fill("Smoke contact")
        page.get_by_role("button", name="Save contact", exact=True).click()
        page.get_by_role("link", name="Edit contact", exact=True).click()
        record["contact_edit_path"] = page.url.removeprefix(base_url)
        stale.goto(page.url)
        record["contact_value"] = f"fictional-updated-{uuid4().hex}@example.invalid"
        page.get_by_label("Value", exact=True).fill(record["contact_value"])
        page.get_by_role("button", name="Save contact", exact=True).click()
        stale.get_by_label("Value", exact=True).fill("stale@example.invalid")
        with stale.expect_navigation() as conflict:
            stale.get_by_role("button", name="Save contact", exact=True).click()
        assert conflict.value.status == 409
        expect(stale.get_by_role("alert")).to_contain_text(re.compile("reload", re.I))
        expect(stale.get_by_label("Value", exact=True)).to_have_value(
            "stale@example.invalid"
        )
        page.reload()
        expect(
            page.locator("li").filter(has_text=record["contact_value"])
        ).to_be_visible()
        page.goto(f"{base_url}/people/")
        page.get_by_label("Search", exact=True).fill(record["contact_value"])
        page.get_by_role("button", name="Search", exact=True).click()
        page.get_by_role("link", name=record["display_name"], exact=True).click()
        expect(page).to_have_url(person_url)
        page.get_by_role("button", name="Archive person", exact=True).click()
        page.goto(f"{base_url}/people/?q={record['contact_value']}")
        expect(
            page.get_by_role("link", name=record["display_name"], exact=True)
        ).to_have_count(0)
        page.locator('[name="archived"]').select_option("only")
        page.get_by_role("button", name="Search", exact=True).click()
        page.get_by_role("link", name=record["display_name"], exact=True).click()
        expect(
            page.locator("li").filter(has_text=record["contact_value"])
        ).to_be_visible()
        page.get_by_role("button", name="Restore person", exact=True).click()
        page.goto(f"{base_url}/people/?q={record['contact_value']}")
        page.get_by_role("link", name=record["display_name"], exact=True).click()
        expect(page).to_have_url(person_url)
        # Keep the edited contact for restart proof; archive a separate contact.
        page.get_by_role("link", name="Add contact", exact=True).click()
        discarded_value = f"fictional-archived-{uuid4().hex}@example.invalid"
        page.get_by_label("Kind", exact=True).select_option("email")
        page.get_by_label("Value", exact=True).fill(discarded_value)
        page.get_by_role("button", name="Save contact", exact=True).click()
        page.locator("li").filter(has_text=discarded_value).get_by_role(
            "button", name="Archive contact", exact=True
        ).click()
        expect(page.locator("li").filter(has_text=discarded_value)).to_have_count(0)
        page.goto(f"{base_url}/people/?q={discarded_value}")
        expect(
            page.get_by_role("link", name=record["display_name"], exact=True)
        ).to_have_count(0)
        page.goto(person_url)
    finally:
        stale.close()


def notes_read(page, base_url, record):
    expect(page.get_by_text(record["note_body"], exact=True)).to_be_visible()
    expect(
        page.get_by_text("Source: " + record["note_source"], exact=True)
    ).to_be_visible()
    page.get_by_role("link", name="Note history", exact=True).click()
    expect(page.get_by_text(record["prior_note_body"], exact=True)).to_be_visible()
    expect(
        page.get_by_text("Source: " + record["prior_note_source"], exact=True)
    ).to_be_visible()
    expect(page.get_by_text("Original author:", exact=False)).to_be_visible()
    expect(page.get_by_text("Corrected by", exact=False)).to_be_visible()
    page.goto(base_url + record["path"])


def notes_on(page, base_url, record):
    record["prior_note_body"] = "Fictional context: enjoys painting <watercolors>."
    record["prior_note_source"] = "Fictional conversation at the example picnic"
    record["note_body"] = "Correction: enjoys sketching <landscapes>, not painting."
    record["note_source"] = "Fictional follow-up conversation; author correction"
    page.get_by_role("link", name="Add context note", exact=True).click()
    page.get_by_label("Body", exact=True).fill(record["prior_note_body"])
    page.get_by_label("Source", exact=True).fill(record["prior_note_source"])
    page.get_by_role("button", name="Save note", exact=True).click()
    page.get_by_role("link", name="Correct note", exact=True).click()
    record["note_edit_path"] = page.url.removeprefix(base_url)
    record["note_history_path"] = (
        record["note_edit_path"].removesuffix("edit/") + "history/"
    )
    stale = page.context.new_page()
    try:
        stale.goto(page.url)
        page.get_by_label("Body", exact=True).fill(record["note_body"])
        page.get_by_label("Source", exact=True).fill(record["note_source"])
        page.get_by_role("button", name="Save note", exact=True).click()
        stale.get_by_label("Body", exact=True).fill("Fictional stale context")
        with stale.expect_navigation() as conflict:
            stale.get_by_role("button", name="Save note", exact=True).click()
        assert conflict.value.status == 409
        expect(stale.get_by_label("Body", exact=True)).to_have_value(
            "Fictional stale context"
        )
        expect(stale.get_by_role("alert")).to_contain_text(re.compile("reload", re.I))
    finally:
        stale.close()
    notes_read(page, base_url, record)


def notes_off(page, base_url, record):
    expect(page.get_by_role("heading", name="Context notes", exact=True)).to_have_count(
        0
    )
    expect(page.get_by_role("link", name="Add context note", exact=True)).to_have_count(
        0
    )
    if "note_body" in record:
        expect(page.get_by_text(record["note_body"], exact=True)).to_have_count(0)
    for path in [record["path"] + "notes/new/"] + [
        record[key] for key in ("note_edit_path", "note_history_path") if key in record
    ]:
        response = page.goto(base_url + path)
        assert response.status == 404
    page.goto(base_url + record["path"])


def party_directory_read(page, base_url, record):
    for key in ("organization", "second_organization", "household"):
        if key not in record:
            continue
        party = record[key]
        response = page.goto(base_url + party["path"])
        assert response.status == 200
        expect(
            page.get_by_role("heading", name=party["display_name"], exact=True)
        ).to_be_visible()
        expect(page.get_by_text("Client", exact=False).first).to_be_visible()


def party_directory_on(page, base_url, record, read_only):
    if read_only:
        party_directory_read(page, base_url, record)
        return
    for key, prefix in (("organization", "organizations"), ("household", "households")):
        singular = key
        name = f"Fictional {singular.title()} {uuid4().hex[:10]}"
        page.goto(f"{base_url}/{prefix}/new/")
        page.locator('[name="display_name"]').fill(name)
        page.locator('[name="is_client"]').check()
        page.get_by_role("button", name=f"Save {singular}", exact=True).click()
        expect(page).to_have_url(
            re.compile(re.escape(base_url) + rf"/{prefix}/[0-9a-f-]+/")
        )
        party = {"path": page.url.removeprefix(base_url), "display_name": name}
        record[key] = party
        page.get_by_role("link", name=f"Edit {singular}", exact=True).click()
        stale = page.context.new_page()
        try:
            stale.goto(page.url)
            party["display_name"] += " Updated"
            page.locator('[name="display_name"]').fill(party["display_name"])
            page.get_by_role("button", name=f"Save {singular}", exact=True).click()
            stale.locator('[name="display_name"]').fill("Fictional stale overwrite")
            with stale.expect_navigation() as conflict:
                stale.get_by_role("button", name=f"Save {singular}", exact=True).click()
            assert conflict.value.status == 409
            expect(stale.get_by_role("alert")).to_contain_text(
                re.compile("reload", re.I)
            )
            expect(stale.locator('[name="display_name"]')).to_have_value(
                "Fictional stale overwrite"
            )
        finally:
            stale.close()
        page.goto(f"{base_url}/{prefix}/?q={party['display_name'].replace(' ', '+')}")
        page.get_by_role("link", name=party["display_name"], exact=True).click()
        page.get_by_role("button", name=f"Archive {singular}", exact=True).click()
        page.goto(f"{base_url}/{prefix}/?q={party['display_name'].replace(' ', '+')}")
        expect(
            page.get_by_role("link", name=party["display_name"], exact=True)
        ).to_have_count(0)
        page.locator('[name="archived"]').select_option("only")
        page.get_by_role("button", name="Search", exact=True).click()
        page.get_by_role("link", name=party["display_name"], exact=True).click()
        page.get_by_role("button", name=f"Restore {singular}", exact=True).click()
    party_directory_read(page, base_url, record)


def party_directory_off(page, base_url, record):
    for name in ("Organizations", "Households"):
        expect(page.get_by_role("link", name=name, exact=True)).to_have_count(0)
    paths = ["/organizations/", "/households/"]
    paths.extend(
        record[key]["path"]
        for key in ("organization", "second_organization", "household")
        if key in record
    )
    for path in paths:
        response = page.goto(base_url + path)
        assert response.status == 404
    page.goto(base_url + record["path"])


def _party_id(path):
    return path.rstrip("/").rsplit("/", 1)[-1]


def _create_relationship(page, base_url, from_path, to_path, kind, role, starts_on):
    page.goto(f"{base_url}/relationships/new/")
    page.locator('[name="from_party_id"]').select_option(_party_id(from_path))
    page.locator('[name="to_party_id"]').select_option(_party_id(to_path))
    page.locator('[name="kind"]').fill(kind)
    page.locator('[name="role"]').fill(role)
    page.locator('[name="starts_on"]').fill(starts_on)
    page.get_by_role("button", name="Save relationship", exact=True).click()
    expect(page).to_have_url(
        re.compile(re.escape(base_url) + r"/relationships/[0-9a-f-]+/")
    )
    return page.url.removeprefix(base_url)


def relationships_read(page, base_url, record, party_directory):
    relationships = record["relationships"]
    for relationship in relationships.values():
        response = page.goto(base_url + relationship["path"])
        assert response.status == 200
        expect(
            page.locator("p")
            .filter(has_text=relationship["from_name"])
            .filter(has_text=relationship["to_name"])
        ).to_be_visible()
        expect(page.get_by_text(relationship["role"], exact=False)).to_be_visible()
        if party_directory == "off":
            for endpoint_path in relationship["directory_paths"]:
                expect(page.locator(f'a[href="{endpoint_path}"]')).to_have_count(0)

    # Both the ended employment and its replacement remain visible together.
    page.goto(base_url + record["path"])
    for relationship in relationships.values():
        expect(
            page.get_by_text(relationship["role"], exact=False).first
        ).to_be_visible()
    if party_directory == "on":
        endpoint_roles = (
            ("organization", relationships["ended_employment"]["role"]),
            ("second_organization", relationships["current_employment"]["role"]),
            ("household", relationships["household_membership"]["role"]),
        )
        for key, role in endpoint_roles:
            party = record[key]
            response = page.goto(base_url + party["path"])
            assert response.status == 200
            expect(page.get_by_text(role, exact=False)).to_be_visible()


def relationships_on(page, base_url, record, read_only, party_directory):
    if read_only:
        relationships_read(page, base_url, record, party_directory)
        return

    second_name = f"Fictional Organization {uuid4().hex[:10]}"
    page.goto(f"{base_url}/organizations/new/")
    page.locator('[name="display_name"]').fill(second_name)
    page.get_by_role("button", name="Save organization", exact=True).click()
    expect(page).to_have_url(
        re.compile(re.escape(base_url) + r"/organizations/[0-9a-f-]+/")
    )
    record["second_organization"] = {
        "path": page.url.removeprefix(base_url),
        "display_name": second_name,
    }

    old_role = "Fictional former advisor"
    current_role = "Fictional current advisor"
    household_role = "Fictional household member"
    old_path = _create_relationship(
        page,
        base_url,
        record["path"],
        record["organization"]["path"],
        "employment",
        old_role,
        "2024-01-01",
    )
    page.locator('form[action$="/close/"] [name="ends_on"]').fill("2024-12-31")
    page.get_by_role("button", name="Close relationship", exact=True).click()
    expect(page).to_have_url(base_url + old_path)
    current_path = _create_relationship(
        page,
        base_url,
        record["path"],
        record["second_organization"]["path"],
        "employment",
        current_role,
        "2025-01-01",
    )
    household_path = _create_relationship(
        page,
        base_url,
        record["path"],
        record["household"]["path"],
        "household_member",
        household_role,
        "2024-06-01",
    )
    record["relationships"] = {
        "ended_employment": {
            "path": old_path,
            "from_name": record["display_name"],
            "to_name": record["organization"]["display_name"],
            "role": old_role,
            "directory_paths": [record["organization"]["path"]],
        },
        "current_employment": {
            "path": current_path,
            "from_name": record["display_name"],
            "to_name": second_name,
            "role": current_role,
            "directory_paths": [record["second_organization"]["path"]],
        },
        "household_membership": {
            "path": household_path,
            "from_name": record["display_name"],
            "to_name": record["household"]["display_name"],
            "role": household_role,
            "directory_paths": [record["household"]["path"]],
        },
    }
    relationships_read(page, base_url, record, party_directory)


def relationships_off(page, base_url, record):
    expect(page.get_by_role("heading", name="Relationships", exact=True)).to_have_count(
        0
    )
    expect(page.get_by_role("link", name="Add relationship", exact=True)).to_have_count(
        0
    )
    paths = ["/relationships/new/"]
    if "relationships" in record:
        paths.extend(item["path"] for item in record["relationships"].values())
    for path in paths:
        response = page.goto(base_url + path)
        assert response.status == 404
    page.goto(base_url + record["path"])


def _create_smoke_person(page, base_url, name):
    page.goto(f"{base_url}/people/new/")
    page.get_by_label("Name", exact=True).fill(name)
    page.get_by_role("button", name="Save person", exact=True).click()
    expect(page).to_have_url(re.compile(re.escape(base_url) + r"/people/[0-9a-f-]+/"))
    return {"path": page.url.removeprefix(base_url), "display_name": name}


def interactions_read(page, base_url, record):
    interaction = record["interaction"]
    response = page.goto(base_url + interaction["path"])
    assert response.status == 200
    expect(page.get_by_text(interaction["body"], exact=True)).to_be_visible()
    expect(page.get_by_text(record["display_name"], exact=True)).to_be_visible()
    expect(
        page.get_by_text(record["third_person"]["display_name"], exact=True)
    ).to_be_visible()
    page.get_by_role("link", name="Interaction history", exact=True).click()
    expect(page.get_by_text(interaction["prior_body"], exact=True)).to_be_visible()
    expect(
        page.get_by_text(record["second_person"]["display_name"], exact=True)
    ).to_be_visible()

    # Current membership follows the replacement, while the removed participant is
    # still available through the shared record's correction history.
    page.goto(base_url + record["path"])
    expect(page.get_by_text(interaction["body"], exact=True).first).to_be_visible()
    page.goto(base_url + record["third_person"]["path"])
    expect(page.get_by_text(interaction["body"], exact=True).first).to_be_visible()
    page.goto(base_url + record["second_person"]["path"])
    expect(page.get_by_text(interaction["body"], exact=True)).to_have_count(0)


def interactions_on(page, base_url, record, read_only):
    if read_only:
        interactions_read(page, base_url, record)
        return

    record["second_person"] = _create_smoke_person(
        page, base_url, f"Fictional Interaction Guest {uuid4().hex[:10]}"
    )
    record["third_person"] = _create_smoke_person(
        page, base_url, f"Fictional Replacement Guest {uuid4().hex[:10]}"
    )
    prior_body = f"Fictional shared conversation {uuid4().hex}"
    page.goto(f"{base_url}/interactions/new/")
    page.locator('[name="occurred_at"]').fill("2026-03-04T10:30+00:00")
    page.locator('[name="body"]').fill(prior_body)
    for participant in (record, record["second_person"]):
        page.locator(
            f'[name="participant_ids"][value="{_party_id(participant["path"])}"]'
        ).check()
    page.get_by_role("button", name="Save interaction", exact=True).click()
    expect(page).to_have_url(
        re.compile(re.escape(base_url) + r"/interactions/[0-9a-f-]+/")
    )
    interaction_path = page.url.removeprefix(base_url)
    corrected_body = f"Fictional corrected conversation {uuid4().hex}"
    page.get_by_role("link", name="Edit interaction", exact=True).click()
    stale = page.context.new_page()
    try:
        stale.goto(page.url)
        page.locator('[name="body"]').fill(corrected_body)
        page.locator(
            f'[name="participant_ids"][value="{_party_id(record["second_person"]["path"])}"]'
        ).uncheck()
        page.locator(
            f'[name="participant_ids"][value="{_party_id(record["third_person"]["path"])}"]'
        ).check()
        page.get_by_role("button", name="Save interaction", exact=True).click()
        stale.locator('[name="body"]').fill("Fictional stale correction")
        with stale.expect_navigation() as conflict:
            stale.get_by_role("button", name="Save interaction", exact=True).click()
        assert conflict.value.status == 409
        expect(stale.get_by_role("alert")).to_contain_text(re.compile("reload", re.I))
        expect(stale.locator('[name="body"]')).to_have_value(
            "Fictional stale correction"
        )
    finally:
        stale.close()
    record["interaction"] = {
        "path": interaction_path,
        "body": corrected_body,
        "prior_body": prior_body,
    }
    interactions_read(page, base_url, record)


def interactions_off(page, base_url, record):
    expect(page.get_by_role("heading", name="Interactions", exact=True)).to_have_count(
        0
    )
    expect(page.get_by_role("link", name="Add interaction", exact=True)).to_have_count(
        0
    )
    paths = ["/interactions/new/"]
    if "interaction" in record:
        interaction_path = record["interaction"]["path"]
        paths.extend(
            (
                interaction_path,
                interaction_path + "edit/",
                interaction_path + "history/",
            )
        )
    for path in paths:
        response = page.goto(base_url + path)
        assert response.status == 404
    page.goto(base_url + record["path"])


def commitments_read(page, base_url, record):
    commitment = record["commitment"]
    response = page.goto(base_url + commitment["path"])
    assert response.status == 200
    expect(page.get_by_text(commitment["description"], exact=True)).to_be_visible()
    expect(
        page.get_by_role("link", name=record["display_name"], exact=True)
    ).to_be_visible()
    expect(
        page.get_by_role(
            "link", name=record["third_person"]["display_name"], exact=True
        )
    ).to_be_visible()
    page.goto(base_url + record["path"])
    expect(
        page.get_by_text(commitment["description"], exact=False).first
    ).to_be_visible()
    page.goto(base_url + record["third_person"]["path"])
    expect(
        page.get_by_text(commitment["description"], exact=False).first
    ).to_be_visible()
    page.goto(f"{base_url}/commitments/")
    expect(page.get_by_text(commitment["description"], exact=False)).to_be_visible()


def commitments_on(page, base_url, record, read_only, interactions):
    if read_only:
        commitments_read(page, base_url, record)
        return
    assert "interaction" in record and "third_person" in record
    page.goto(f"{base_url}/commitments/new/")
    first_id = _party_id(record["path"])
    third_id = _party_id(record["third_person"]["path"])
    page.locator('[name="owed_by_party_id"]').select_option(first_id)
    page.locator('[name="owed_to_party_id"]').select_option(third_id)
    page.locator(f'[name="person_ids"][value="{first_id}"]').check()
    page.locator(f'[name="person_ids"][value="{third_id}"]').check()
    if interactions == "on":
        page.locator('[name="source_interaction_id"]').select_option(
            _party_id(record["interaction"]["path"])
        )
    description = f"Fictional promise after shared conversation {uuid4().hex}"
    page.locator('[name="description"]').fill(description)
    page.locator('[name="due_on"]').fill("2026-12-31")
    page.get_by_role("button", name="Save commitment", exact=True).click()
    expect(page).to_have_url(
        re.compile(re.escape(base_url) + r"/commitments/[0-9a-f-]+/")
    )
    path = page.url.removeprefix(base_url)
    page.get_by_role("button", name="Complete commitment", exact=True).click()
    expect(page.get_by_text("Status completed", exact=False)).to_be_visible()
    page.get_by_role("button", name="Reopen commitment", exact=True).click()
    expect(page.get_by_text("Status open", exact=False)).to_be_visible()
    record["commitment"] = {"path": path, "description": description}
    commitments_read(page, base_url, record)


def commitments_off(page, base_url, record):
    expect(page.get_by_role("heading", name="Commitments", exact=True)).to_have_count(0)
    expect(page.get_by_role("link", name="Commitments", exact=True)).to_have_count(0)
    paths = ["/commitments/", "/commitments/new/"]
    if "commitment" in record:
        paths.append(record["commitment"]["path"])
    for path in paths:
        response = page.goto(base_url + path)
        assert response.status == 404
    page.goto(base_url + record["path"])


def _create_scenario_interaction(page, base_url, participants, body):
    page.goto(f"{base_url}/interactions/new/")
    page.locator('[name="occurred_at"]').fill("2026-09-16T14:00+00:00")
    page.locator('[name="body"]').fill(body)
    for participant in participants:
        page.locator(
            f'[name="participant_ids"][value="{_party_id(participant["path"])}"]'
        ).check()
    page.get_by_role("button", name="Save interaction", exact=True).click()
    expect(page).to_have_url(
        re.compile(re.escape(base_url) + r"/interactions/[0-9a-f-]+/")
    )
    return page.url.removeprefix(base_url)


def _create_completed_scenario_commitment(
    page, base_url, person, counterpart, source_path, description
):
    page.goto(f"{base_url}/commitments/new/")
    person_id = _party_id(person["path"])
    counterpart_id = _party_id(counterpart["path"])
    page.locator('[name="owed_by_party_id"]').select_option(person_id)
    page.locator('[name="owed_to_party_id"]').select_option(counterpart_id)
    page.locator(f'[name="person_ids"][value="{person_id}"]').check()
    page.locator('[name="source_interaction_id"]').select_option(_party_id(source_path))
    page.locator('[name="description"]').fill(description)
    page.locator('[name="due_on"]').fill("2026-12-31")
    page.get_by_role("button", name="Save commitment", exact=True).click()
    expect(page).to_have_url(
        re.compile(re.escape(base_url) + r"/commitments/[0-9a-f-]+/")
    )
    commitment_path = page.url.removeprefix(base_url)

    # The open summary and owning record agree before completion.
    page.goto(base_url + person["path"])
    expect(page.get_by_role("heading", name="Conversation preparation")).to_be_visible()
    expect(page.get_by_text(description, exact=True).first).to_be_visible()
    page.goto(base_url + commitment_path)
    page.get_by_role("button", name="Complete commitment", exact=True).click()
    expect(page.get_by_text("Status completed", exact=False)).to_be_visible()

    # Completion remains available in the full paginated section as history.
    page.goto(base_url + person["path"])
    expect(page.get_by_text(description, exact=True)).to_have_count(0)
    page.locator('[name="commitments_status"]').select_option("completed")
    page.get_by_role("button", name="Filter person commitments", exact=True).click()
    expect(page.get_by_text(description, exact=False)).to_be_visible()
    return commitment_path


def person_overview_read(page, base_url, record):
    for scenario in record.get("overview_scenarios", []):
        page.goto(base_url + scenario["person"]["path"])
        expect(
            page.get_by_role("heading", name="Conversation preparation")
        ).to_be_visible()
        expect(
            page.get_by_text(scenario["interaction_body"], exact=True).first
        ).to_be_visible()
        expect(
            page.get_by_text(scenario["relationship_role"], exact=False).first
        ).to_be_visible()
        page.locator('[name="commitments_status"]').select_option("completed")
        page.get_by_role("button", name="Filter person commitments", exact=True).click()
        expect(page.get_by_text(scenario["description"], exact=False)).to_be_visible()
        page.goto(base_url + scenario["commitment_path"])
        expect(page.get_by_text("Status completed", exact=False)).to_be_visible()
        for relationship in scenario["relationships"]:
            page.goto(base_url + relationship["path"])
            expect(
                page.get_by_text(relationship["role"], exact=False).first
            ).to_be_visible()


def person_overview_on(
    page, base_url, record, read_only, relationships, interactions, commitments
):
    page.goto(base_url + record["path"])
    expect(page.get_by_role("heading", name="Conversation preparation")).to_be_visible()
    for enabled, heading in (
        (relationships, "Current relationships"),
        (interactions, "Recent interactions"),
        (commitments, "Open commitments"),
    ):
        expect(page.get_by_role("heading", name=re.compile(heading))).to_have_count(
            1 if enabled == "on" else 0
        )
    if not all(value == "on" for value in (relationships, interactions, commitments)):
        return
    if read_only:
        person_overview_read(page, base_url, record)
        return

    scenario_specs = [
        (
            "Realtor",
            "household_member",
            "Individual household priorities",
            "Shared conversation about each household member's priorities",
            "Send the household options discussed",
            record["household"],
        ),
        (
            "Pre-Sales Engineer",
            "employment",
            "Technical contact after changed employment",
            "Shared technical and business contact discovery",
            "Deliver the promised technical follow-up",
            record["second_organization"],
        ),
        (
            "Attorney",
            "referral",
            "Client update contact",
            "Conversation about the attorney's promised update",
            "Provide the promised matter update",
            record["organization"],
        ),
    ]
    scenarios = []
    for profession, kind, role, body, description, endpoint in scenario_specs:
        person = _create_smoke_person(
            page, base_url, f"Fictional {profession} Contact {uuid4().hex[:8]}"
        )
        counterpart = _create_smoke_person(
            page, base_url, f"Fictional {profession} Colleague {uuid4().hex[:8]}"
        )
        scenario_relationships = []
        if profession == "Pre-Sales Engineer":
            prior_relationship_path = _create_relationship(
                page,
                base_url,
                person["path"],
                record["organization"]["path"],
                "employment",
                "Former technical contact",
                "2025-01-01",
            )
            page.locator('form[action$="/close/"] [name="ends_on"]').fill("2025-12-31")
            page.get_by_role("button", name="Close relationship", exact=True).click()
            scenario_relationships.append(
                {
                    "path": prior_relationship_path,
                    "role": "Former technical contact",
                }
            )
        relationship_path = _create_relationship(
            page,
            base_url,
            person["path"],
            endpoint["path"],
            kind,
            role,
            "2026-01-01",
        )
        scenario_relationships.append({"path": relationship_path, "role": role})
        if profession == "Realtor":
            counterpart_relationship = _create_relationship(
                page,
                base_url,
                counterpart["path"],
                endpoint["path"],
                "household_member",
                "Second individual's distinct priorities",
                "2026-01-01",
            )
            scenario_relationships.append(
                {
                    "path": counterpart_relationship,
                    "role": "Second individual's distinct priorities",
                }
            )
        elif profession == "Pre-Sales Engineer":
            business_relationship = _create_relationship(
                page,
                base_url,
                counterpart["path"],
                endpoint["path"],
                "employment",
                "Business contact",
                "2026-01-01",
            )
            scenario_relationships.append(
                {"path": business_relationship, "role": "Business contact"}
            )
        interaction_path = _create_scenario_interaction(
            page, base_url, (person, counterpart), body
        )
        commitment_path = _create_completed_scenario_commitment(
            page,
            base_url,
            person,
            counterpart,
            interaction_path,
            description,
        )
        scenarios.append(
            {
                "person": person,
                "counterpart": counterpart,
                "relationships": scenario_relationships,
                "relationship_role": role,
                "interaction_path": interaction_path,
                "interaction_body": body,
                "commitment_path": commitment_path,
                "description": description,
            }
        )
    record["overview_scenarios"] = scenarios
    person_overview_read(page, base_url, record)


def person_overview_off(page, base_url, record):
    page.goto(base_url + record["path"])
    expect(page.get_by_role("heading", name="Conversation preparation")).to_have_count(
        0
    )


def smoke(
    base_url,
    username,
    password,
    record_file=None,
    read_file=None,
    people_management="off",
    context_notes="off",
    party_directory="off",
    relationships="off",
    interactions="off",
    commitments="off",
    person_overview="off",
):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            context = browser.new_context()
            page = context.new_page()
            response = page.goto(f"{base_url}/health/ready/")
            assert response.status == 200 and response.json() == {"status": "ready"}
            page.goto(f"{base_url}/login/")
            page.get_by_label("Username", exact=True).fill(username)
            page.get_by_label("Password", exact=True).fill(password)
            page.get_by_role("button", name="Log in", exact=True).click()
            expect(page).to_have_url(f"{base_url}/people/")
            if read_file:
                record = json.loads(Path(read_file).read_text())
                assert record["path"].startswith("/people/")
                response = page.goto(base_url + record["path"])
                assert response.status == 200
            else:
                name = f"Fictional Smoke {uuid4().hex[:12]}"
                page.goto(f"{base_url}/people/new/")
                page.get_by_label("Name", exact=True).fill(name)
                page.get_by_role("button", name="Save person", exact=True).click()
                expect(page).to_have_url(
                    re.compile(re.escape(base_url) + r"/people/[0-9a-f-]+/")
                )
                record = {"path": page.url.removeprefix(base_url), "display_name": name}
            expect(
                page.get_by_role("heading", name=record["display_name"], exact=True)
            ).to_be_visible()
            response = page.reload()
            assert response.status == 200
            expect(
                page.get_by_role("heading", name=record["display_name"], exact=True)
            ).to_be_visible()
            if people_management == "on":
                if read_file:
                    expect(
                        page.get_by_role("link", name="Edit person", exact=True)
                    ).to_be_visible()
                    if "contact_value" in record:
                        expect(
                            page.locator("li").filter(has_text=record["contact_value"])
                        ).to_be_visible()
                else:
                    management_on(page, base_url, record)
            else:
                management_off(page, base_url, record)
            if context_notes == "on":
                if read_file:
                    expect(
                        page.get_by_role("heading", name="Context notes", exact=True)
                    ).to_be_visible()
                    if "note_body" in record:
                        notes_read(page, base_url, record)
                else:
                    notes_on(page, base_url, record)
            else:
                notes_off(page, base_url, record)
            if party_directory == "on":
                party_directory_on(page, base_url, record, bool(read_file))
            else:
                party_directory_off(page, base_url, record)
            if relationships == "on":
                relationships_on(
                    page, base_url, record, bool(read_file), party_directory
                )
            else:
                relationships_off(page, base_url, record)
            if interactions == "on":
                interactions_on(page, base_url, record, bool(read_file))
            else:
                interactions_off(page, base_url, record)
            if commitments == "on":
                commitments_on(page, base_url, record, bool(read_file), interactions)
            else:
                commitments_off(page, base_url, record)
            if person_overview == "on":
                person_overview_on(
                    page,
                    base_url,
                    record,
                    bool(read_file),
                    relationships,
                    interactions,
                    commitments,
                )
            else:
                person_overview_off(page, base_url, record)
            if record_file:
                Path(record_file).write_text(json.dumps(record) + "\n")
            print(
                f"Browser smoke passed: people management {people_management}; "
                f"context notes {context_notes}; party directory {party_directory}; "
                f"relationships {relationships}"
                f"; interactions {interactions}"
                f"; commitments {commitments}"
                f"; person overview {person_overview}"
            )
        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument(
        "--people-management",
        choices=("on", "off"),
        default="off",
        help="Assert flag state; on exercises Stage 1 workflows",
    )
    parser.add_argument("--context-notes", choices=("on", "off"), default="off")
    parser.add_argument("--party-directory", choices=("on", "off"), default="off")
    parser.add_argument("--relationships", choices=("on", "off"), default="off")
    parser.add_argument("--interactions", choices=("on", "off"), default="off")
    parser.add_argument("--commitments", choices=("on", "off"), default="off")
    parser.add_argument("--person-overview", choices=("on", "off"), default="off")
    files = parser.add_mutually_exclusive_group()
    files.add_argument("--record-file")
    files.add_argument("--read-file")
    args = parser.parse_args()
    smoke(
        args.base_url.rstrip("/"),
        os.environ["SMOKE_USERNAME"],
        os.environ["SMOKE_PASSWORD"],
        args.record_file,
        args.read_file,
        args.people_management,
        args.context_notes,
        args.party_directory,
        args.relationships,
        args.interactions,
        args.commitments,
        args.person_overview,
    )


if __name__ == "__main__":
    main()
