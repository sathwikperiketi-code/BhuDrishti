"""Mailbox validation must preserve the exact intended account recipient."""

import pytest

from app.contracts.auth import CreateUserRequest, EmailRequest, Role, SignUpRequest
from app.email_address import normalize_email_address


@pytest.mark.parametrize("value", [
    "foo<bar@example.test>", "Name <bar@example.test>", "(alias)bar@example.test",
    "bar@example.test,", "bar@example.test,other@example.test", "bar@example.test(comment)",
    "bar@example.test\r\nBcc:other@example.test", "bar\t@example.test", '"bar"@example.test',
    "foo..bar@example.test", ".bar@example.test", "bar.@example.test", "bar@-example.test",
    "bar@example-.test", "bar@example..test", "bar@example", "bar@", "@example.test",
    f"{'a' * 65}@example.test", f"bar@{'a' * 64}.test", "straße@example.test",
])
def test_all_account_email_contracts_reject_header_and_invalid_mailboxes(value) -> None:
    for contract, fields in (
        (EmailRequest, {}),
        (CreateUserRequest, {"name": "Test User", "password": "ValidPassword12!", "role": Role.AUDITOR}),
        (SignUpRequest, {
            "full_name": "Test User", "username": "test.user", "password": "ValidPassword12!",
            "confirm_password": "ValidPassword12!", "requested_role": Role.AUDITOR,
        }),
    ):
        with pytest.raises(ValueError, match="Enter a valid email address"):
            contract(email=value, **fields)


@pytest.mark.parametrize("value, expected", [
    (" Person+QA@Gmail.COM ", "person+qa@gmail.com"),
    ("first.last@example.test", "first.last@example.test"),
    ("a!#$%&'*+/=?^_`{|}~-b@example.test", "a!#$%&'*+/=?^_`{|}~-b@example.test"),
    ("person@xn--bcher-kva.example", "person@xn--bcher-kva.example"),
])
def test_bare_mailbox_normalization_preserves_supported_aliases(value, expected) -> None:
    assert normalize_email_address(value) == expected
    assert EmailRequest(email=value).email == expected
