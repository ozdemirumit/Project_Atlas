from __future__ import annotations

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


@pytest.mark.asyncio
async def test_live_postgres_schema_is_append_only_and_source_digests_are_required() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")

    engine = create_async_engine(database_url)
    tables = (
        "workflow_event_runtime_process_scheduling_consumption_claims",
        "workflow_event_runtime_process_scheduling_attempts",
        "workflow_event_runtime_process_scheduling_results",
    )
    source_digest_columns = (
        "scheduling_authorization_lease_digest",
        "scheduling_authorization_claim_digest",
        "process_state_attestation_digest",
        "scheduling_profile_digest",
        "process_creation_result_digest",
        "process_creation_receipt_digest",
    )
    try:
        async with engine.connect() as connection:
            columns = (
                (
                    await connection.execute(
                        text(
                            """
                        SELECT table_name, column_name, is_nullable
                        FROM information_schema.columns
                        WHERE table_schema = current_schema()
                          AND table_name = ANY(:tables)
                          AND (column_name = ANY(:digests)
                               OR column_name = 'process_creation_failure_class')
                        """
                        ),
                        {"tables": list(tables), "digests": list(source_digest_columns)},
                    )
                )
                .mappings()
                .all()
            )
            triggers = int(
                (
                    await connection.execute(
                        text(
                            """
                            SELECT count(*)
                            FROM pg_trigger t
                            JOIN pg_class c ON c.oid = t.tgrelid
                            WHERE NOT t.tgisinternal
                              AND c.relname = ANY(:tables)
                              AND t.tgname LIKE 'trg_wf_rtpsched_cons_%'
                            """
                        ),
                        {"tables": list(tables)},
                    )
                ).scalar_one()
            )
        by_table = {
            table: {
                row["column_name"]: row["is_nullable"]
                for row in columns
                if row["table_name"] == table
            }
            for table in tables
        }
        for table in tables:
            assert by_table[table]["process_creation_failure_class"] == "YES"
            assert all(by_table[table][name] == "NO" for name in source_digest_columns)
        assert triggers == 6
    finally:
        await engine.dispose()
