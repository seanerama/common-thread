"""Assert exact health contract, including deliberately unhealthy runtime tests."""

import argparse
import json
import urllib.error
import urllib.request

parser = argparse.ArgumentParser()
parser.add_argument("url")
parser.add_argument("--ready", type=int, default=200)
args = parser.parse_args()
for endpoint, expected, status in (
    ("live", 200, "ok"),
    ("ready", args.ready, "ready" if args.ready == 200 else "not_ready"),
):
    try:
        response = urllib.request.urlopen(f"{args.url}/health/{endpoint}/", timeout=5)
    except urllib.error.HTTPError as error:
        response = error
    assert response.code == expected, (endpoint, response.code, expected)
    assert json.load(response) == {"status": status}
    assert response.headers["Cache-Control"] == "no-store"
