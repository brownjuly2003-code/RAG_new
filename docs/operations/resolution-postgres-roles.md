# Resolution PostgreSQL role operations

Last updated: 2026-08-22

## Scope

This runbook owns the PostgreSQL boundary for Resolution persistence on the
authorized Mac target. It does not switch the legacy application
`DATABASE_URL`, enable Resolution API routing, deploy the web runtime, or touch
the pre-existing PostgreSQL server on port `5432`.

The dedicated target uses PostgreSQL 16, loopback port `55432`, database
`ragnew_prod`, and a separate data directory. All commands below fail closed
when the observed port, listen address, data directory, database owner, roles,
or grants differ from the declared contract.

## Installed Mac target

| Item | Path/value |
|------|------------|
| PostgreSQL | Homebrew `postgresql@16` (`/usr/local/opt/postgresql@16/bin`) |
| data | `~/.local/share/rag-new/postgresql-16` |
| socket | `~/.local/share/rag-new/postgresql-socket` |
| secrets | `~/.config/rag-new/postgres-secrets.env` (`0600`) |
| service | `~/Library/LaunchAgents/com.rag-new.postgresql.plist` (`0644`) |
| logs | `~/Library/Logs/RAG_new` |

The LaunchAgent must keep `LC_ALL=C` and `LANG=C`: without them PostgreSQL 16
on this macOS host exits during startup with the postmaster multithreading
locale guard. Manage this dedicated cluster through `launchctl`; do not start
the unused Homebrew default cluster with `brew services`, because port `5432`
belongs to the pre-existing PostgreSQL service.

```bash
launchctl print "gui/$(id -u)/com.rag-new.postgresql"
/usr/local/opt/postgresql@16/bin/pg_isready -h 127.0.0.1 -p 55432
launchctl kickstart -k "gui/$(id -u)/com.rag-new.postgresql"
```

## Ownership topology

| Role | Login | Purpose |
|------|-------|---------|
| `ragnew_bootstrap` | yes | Cluster-local bootstrap and rollback owner; never used by the application. |
| `ragnew_schema_owner` | no | Owns `ragnew_prod`, schema `public`, extensions, and Alembic objects. |
| `ragnew_migrator` | yes, `NOINHERIT` | Member only of `ragnew_schema_owner`; migrations run with `SET ROLE`. |
| `ragnew_resolution_runtime` | yes, `NOINHERIT` | Direct runtime login; owns no objects and belongs to no roles. |

Every role is `NOSUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`, `NOREPLICATION`,
and `NOBYPASSRLS` except the dedicated cluster bootstrap role. The bootstrap
credential remains outside Git and application configuration.

## Minimum runtime grants

| Object | Grant |
|--------|-------|
| database `ragnew_prod` | `CONNECT` |
| schema `public` | `USAGE` |
| `support_cases` | `SELECT`, `INSERT`, `UPDATE(status, version, updated_at)` |
| `case_events` | `SELECT`, `INSERT` |
| `evidence_snapshots` | `SELECT`, `INSERT` |
| `case_evidence_links` | `SELECT`, `INSERT` |
| `pgp_sym_encrypt(text,text,text)` | `EXECUTE` |
| `pgp_sym_decrypt(bytea,text)` | `EXECUTE` |

Runtime receives no database/schema `CREATE`, `TEMP`, sequence privileges,
table-level `UPDATE`, `DELETE`, `TRUNCATE`, `REFERENCES`, or `TRIGGER`.
`PUBLIC` receives no access to the target database, schema, tables, sequences,
or functions. New objects remain closed until this explicit matrix is updated.

## Secrets

Provide these values through the Mac secret file or the process environment:

- `RAG_NEW_BOOTSTRAP_PASSWORD`
- `RAG_NEW_MIGRATOR_PASSWORD`
- `RAG_NEW_RUNTIME_PASSWORD`
- `DB_ENCRYPTION_KEY`
- `RESOLUTION_ADMIN_DATABASE_URL`
- `RESOLUTION_MIGRATOR_DATABASE_URL`
- `RESOLUTION_RUNTIME_DATABASE_URL`
- `RAG_NEW_POSTGRES_DATA_DIR`
- `RAG_NEW_POSTGRES_PORT`

The secret file must be outside the checkout with mode `0600`. Never place a
DSN, password, encryption key, or `.pgpass` content in Git, shell history,
command arguments, logs, evidence documents, or database backups.

## Apply

First inventory the exact target without mutation:

```bash
. "$HOME/.config/rag-new/postgres-secrets.env"
python scripts/resolution_role_ops.py inventory
```

Create or reconcile the database and roles:

```bash
python scripts/resolution_role_ops.py bootstrap \
  --confirm-target ragnew_prod@55432
```

Run Alembic as the migrator while assuming the non-login schema owner:

```bash
export PGOPTIONS='-c role=ragnew_schema_owner'
DATABASE_URL="$RESOLUTION_MIGRATOR_DATABASE_URL" alembic upgrade head
unset PGOPTIONS
```

Then apply and verify the exact runtime ACL:

```bash
python scripts/resolution_role_ops.py grant \
  --confirm-target ragnew_prod@55432
python scripts/resolution_role_ops.py verify
python scripts/resolution_role_ops.py smoke \
  --confirm-target ragnew_prod@55432
```

The smoke connects directly as `ragnew_resolution_runtime`; it proves
default-deny with populated rows, own-tenant access, cross-tenant invisibility
and `42501`, CAS-only column update, append-table ACL denial, owner-level append
guard `55000`, pgcrypto execution, and full transaction rollback. It leaves no
case or evidence rows. The tenant GUC is an application trust boundary, not a
defense against a fully compromised process holding the runtime credential.

## Kill switch and rollback

The non-destructive rollback owner is `ragnew_bootstrap`:

```bash
python scripts/resolution_role_ops.py revoke-runtime \
  --confirm-target ragnew_prod@55432
```

This changes runtime to `NOLOGIN`, revokes `CONNECT`, terminates only its
sessions in `ragnew_prod`, and removes its schema/table/sequence/function
privileges. It preserves the database, schema, data, migrations, owner, and
migrator. Restore access only after the incident is resolved:

```bash
python scripts/resolution_role_ops.py grant \
  --confirm-target ragnew_prod@55432
python scripts/resolution_role_ops.py verify
```

Do not run Alembic downgrade as operational rollback. Full database, role,
cluster, secret, or checkout removal is a separate destructive teardown and
requires a fresh backup plus explicit authorization.

## Acceptance checks

- `session_user = current_user = ragnew_resolution_runtime` for runtime smoke;
- runtime is non-owner, `NOSUPERUSER`, `NOINHERIT`, and `NOBYPASSRLS`;
- all four Resolution tables have enabled and forced RLS;
- all four tables have exactly one permissive `ALL TO PUBLIC` tenant policy
  with the migration-owned `USING` and `WITH CHECK` expressions;
- direct table, column, function, sequence, schema, database, `PUBLIC`, and
  schema-owner default ACLs equal the matrix above;
- migrator membership has `ADMIN=false`, `INHERIT=false`, `SET=true`, and
  managed role/database settings are empty;
- migrations are at the single Alembic head;
- kill-switch revoke and grant restoration both verify;
- PostgreSQL `5432` remains accepting connections and unchanged;
- no credentials appear in Git diff, process arguments, or logs.
