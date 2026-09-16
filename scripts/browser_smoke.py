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
    for key in ("organization", "household"):
        party = record[key]
        response = page.goto(base_url + party["path"])
        assert response.status == 200
        expect(
            page.get_by_role("heading", name=party["display_name"], exact=True)
        ).to_be_visible()
        expect(page.get_by_text("Client", exact=False)).to_be_visible()


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
        record[key]["path"] for key in ("organization", "household") if key in record
    )
    for path in paths:
        response = page.goto(base_url + path)
        assert response.status == 404
    page.goto(base_url + record["path"])


def smoke(
    base_url,
    username,
    password,
    record_file=None,
    read_file=None,
    people_management="off",
    context_notes="off",
    party_directory="off",
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
            if record_file:
                Path(record_file).write_text(json.dumps(record) + "\n")
            print(
                f"Browser smoke passed: people management {people_management}; "
                f"context notes {context_notes}; party directory {party_directory}"
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
    )


if __name__ == "__main__":
    main()
