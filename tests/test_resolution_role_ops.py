from __future__ import annotations

from dataclasses import replace

import pytest

from scripts import resolution_role_ops


def test_default_role_contract_is_least_privilege() -> None:
    names = resolution_role_ops.RoleNames()

    assert names.database == "ragnew_prod"
    assert names.schema_owner == "ragnew_schema_owner"
    assert names.migrator == "ragnew_migrator"
    assert names.runtime == "ragnew_resolution_runtime"
    assert resolution_role_ops.RUNTIME_TABLE_GRANTS == {
        "support_cases": frozenset({"SELECT", "INSERT"}),
        "case_events": frozenset({"SELECT", "INSERT"}),
        "evidence_snapshots": frozenset({"SELECT", "INSERT"}),
        "case_evidence_links": frozenset({"SELECT", "INSERT"}),
    }
    assert resolution_role_ops.RUNTIME_COLUMN_GRANTS == {
        "support_cases": frozenset({"status", "version", "updated_at"})
    }
    assert resolution_role_ops.RUNTIME_FUNCTION_GRANTS == frozenset(
        {
            "pgp_sym_encrypt(text,text,text)",
            "pgp_sym_decrypt(bytea,text)",
        }
    )

    resolution_role_ops.validate_role_names(names)


@pytest.mark.parametrize(
    "names",
    [
        resolution_role_ops.RoleNames(runtime="ragnew-runtime"),
        resolution_role_ops.RoleNames(migrator="RAGNEW_MIGRATOR"),
        resolution_role_ops.RoleNames(schema_owner="9schema_owner"),
        resolution_role_ops.RoleNames(database="ragnew_prod;drop_database"),
        resolution_role_ops.RoleNames(runtime="ragnew_migrator"),
    ],
)
def test_role_contract_rejects_unsafe_or_duplicate_identifiers(
    names: resolution_role_ops.RoleNames,
) -> None:
    with pytest.raises(ValueError, match="identifier|distinct"):
        resolution_role_ops.validate_role_names(names)


@pytest.mark.parametrize("password", ["", "short", "x" * 23, "valid-password-with-newline\n"])
def test_role_password_requires_24_single_line_characters(password: str) -> None:
    with pytest.raises(ValueError, match="24|single-line"):
        resolution_role_ops.validate_password(password, label="runtime")


def test_role_password_accepts_urlsafe_generated_shape() -> None:
    resolution_role_ops.validate_password("N8h4xY2mQ7pL5vC9kR6sT3wZ")


def test_bootstrap_requires_both_passwords_before_database_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RAG_NEW_MIGRATOR_PASSWORD", raising=False)
    monkeypatch.delenv("RAG_NEW_RUNTIME_PASSWORD", raising=False)

    with pytest.raises(SystemExit) as exc_info:
        resolution_role_ops.main(
            ["bootstrap", "--admin-url", "postgresql://unused.invalid/postgres"]
        )

    assert exc_info.value.code == 2


def test_membership_contract_disallows_admin_and_inherit_options() -> None:
    names = resolution_role_ops.RoleNames()

    assert resolution_role_ops._expected_memberships(names) == {
        (names.migrator, names.schema_owner, False, False, True)
    }


@pytest.mark.parametrize(
    ("field_name", "unexpected_entry"),
    [
        ("database", ("PUBLIC", "CONNECT")),
        ("schema", ("PUBLIC", "USAGE")),
        ("relations", ("ragnew_resolution_runtime", "sequence", "legacy_seq", "USAGE")),
        (
            "columns",
            ("ragnew_resolution_runtime", "support_cases", "contract_id", "SELECT"),
        ),
        (
            "functions",
            ("ragnew_resolution_runtime", "unsafe_helper(text)", "EXECUTE"),
        ),
        ("defaults", ("global", "f", "PUBLIC", "EXECUTE")),
    ],
)
def test_acl_contract_rejects_public_or_extra_runtime_privileges(
    field_name: str,
    unexpected_entry: tuple[str, ...],
) -> None:
    names = resolution_role_ops.RoleNames()
    expected = resolution_role_ops._expected_acl_snapshot(names)
    drifted_values = getattr(expected, field_name) | {unexpected_entry}
    drifted = replace(expected, **{field_name: drifted_values})

    assert resolution_role_ops._acl_contract_violations(expected, names) == []
    assert resolution_role_ops._acl_contract_violations(drifted, names)


@pytest.mark.parametrize(
    "field_index, replacement",
    [
        (2, "RESTRICTIVE"),
        (3, ("ragnew_resolution_runtime",)),
        (4, "SELECT"),
        (5, "true"),
        (6, "true"),
    ],
)
def test_rls_policy_contract_rejects_semantic_drift(
    field_index: int,
    replacement: object,
) -> None:
    expected = resolution_role_ops._expected_tenant_policy_rows()
    row = list(next(iter(expected)))
    row[field_index] = replacement
    drifted = (expected - {next(iter(expected))}) | {tuple(row)}

    assert resolution_role_ops._policy_contract_violations(expected) == []
    assert resolution_role_ops._policy_contract_violations(drifted)


def test_smoke_requires_admin_and_runtime_urls_to_share_one_endpoint() -> None:
    names = resolution_role_ops.RoleNames()
    admin_url = "postgresql://admin:secret@127.0.0.1:55432/postgres?sslmode=disable"
    runtime_url = (
        "postgresql://ragnew_resolution_runtime:secret@127.0.0.1:55432/ragnew_prod?sslmode=disable"
    )

    resolution_role_ops._validate_runtime_endpoint(admin_url, runtime_url, names)

    with pytest.raises(resolution_role_ops.RoleContractError, match="endpoint"):
        resolution_role_ops._validate_runtime_endpoint(
            admin_url,
            runtime_url.replace("127.0.0.1", "localhost"),
            names,
        )
    with pytest.raises(resolution_role_ops.RoleContractError, match="routing"):
        resolution_role_ops._validate_runtime_endpoint(
            admin_url,
            runtime_url + "&host=elsewhere.invalid",
            names,
        )
