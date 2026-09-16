"""Fresh-process checks exercise startup validation without cached Django settings."""

import json
import os
import subprocess
import sys

import pytest


@pytest.fixture
def production_env():
    return {
        **os.environ,
        "APP_ENV": "production",
        "DJANGO_SETTINGS_MODULE": "common_thread.settings",
        "DATABASE_URL": "postgresql://unused:unused@localhost/unused",
        "DJANGO_SECRET_KEY": "fictional-test-configuration-only",
        "ALLOWED_HOSTS": "crm.example.test",
        "CSRF_TRUSTED_ORIGINS": "https://crm.example.test",
        "TRUST_PROXY_HTTPS": "false",
    }


def run_python(env, source):
    return subprocess.run(
        [sys.executable, "-c", source],
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )


def test_production_secure_cookies_and_untrusted_proxy(production_env):
    result = run_python(
        production_env,
        """
import json
import django
django.setup()
from django.conf import settings
from django.test import RequestFactory
request = RequestFactory().get("/", HTTP_X_FORWARDED_PROTO="https")
print(json.dumps({
    "secure_session": settings.SESSION_COOKIE_SECURE,
    "secure_csrf": settings.CSRF_COOKIE_SECURE,
    "debug": settings.DEBUG,
    "spoofed_https": request.is_secure(),
    "timeout": settings.DATABASES["default"]["OPTIONS"]["connect_timeout"],
}))
""",
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "secure_session": True,
        "secure_csrf": True,
        "debug": False,
        "spoofed_https": False,
        "timeout": 2,
    }


@pytest.mark.parametrize(
    "missing",
    [
        "DATABASE_URL",
        "DJANGO_SECRET_KEY",
        "ALLOWED_HOSTS",
        "CSRF_TRUSTED_ORIGINS",
    ],
)
def test_missing_production_configuration_fails_startup(production_env, missing):
    production_env.pop(missing)
    result = run_python(production_env, "import django; django.setup()")
    assert result.returncode != 0
    assert f"Missing {missing}" in result.stderr


def test_non_https_csrf_origin_rejected(production_env):
    production_env["CSRF_TRUSTED_ORIGINS"] = "http://crm.example.test"
    result = run_python(production_env, "import django; django.setup()")
    assert result.returncode != 0
    assert "Production origins must use HTTPS" in result.stderr


def test_clickjacking_header(client):
    assert client.get("/login/").headers["X-Frame-Options"] == "DENY"
