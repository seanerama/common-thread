"""Real-browser operator smoke; record fictional data for a fresh restart read."""

import argparse
import json
import os
import re
from pathlib import Path
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright


def smoke(base_url, username, password, record_file=None, read_file=None):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
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
            if record_file:
                Path(record_file).write_text(json.dumps(record) + "\n")
            print("Browser smoke passed: authenticated persistent person read")
        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
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
    )


if __name__ == "__main__":
    main()
