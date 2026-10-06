"""Keep automated tests isolated from a developer's real SMTP account.

Pytest loads this file before importing test modules. That matters because
``app.main`` creates an app at import time, and its lifespan can start an SMTP
health probe. Tests that exercise mail pass explicit settings or fake
transports, and can still override these process-local values with monkeypatch.
"""

from __future__ import annotations

import os


_TEST_SMTP_ENV = {
    "SMTP_HOST": "",
    "SMTP_PORT": "587",
    "SMTP_SECURE": "false",
    "SMTP_USER": "",
    "SMTP_PASS": "",
    "SMTP_FROM": "",
}

for _name, _value in _TEST_SMTP_ENV.items():
    os.environ[_name] = _value
    os.environ[f"BHUDRISHTI_{_name}"] = _value
