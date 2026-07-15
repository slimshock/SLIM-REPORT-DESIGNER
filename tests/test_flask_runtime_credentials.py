from __future__ import annotations

import threading
import time

from slim_report_flask import InMemoryRuntimeCredentialStore


def test_runtime_credential_store_isolated_clearable_and_redacted() -> None:
    store = InMemoryRuntimeCredentialStore(ttl_seconds=10)
    store.set_password("report-a", "source-a", "secret-a")
    store.set_password("report-b", "source-a", "secret-b")

    assert store.get_password("report-a", "source-a") == "secret-a"
    assert store.get_password("report-b", "source-a") == "secret-b"
    assert "secret" not in repr(store)
    assert not hasattr(store, "items")

    store.clear_password("report-a", "source-a")
    assert store.get_password("report-a", "source-a") is None
    store.clear_report("report-b")
    assert store.get_password("report-b", "source-a") is None


def test_runtime_credential_store_expires_and_handles_concurrent_access() -> None:
    store = InMemoryRuntimeCredentialStore(ttl_seconds=0.2)

    threads = [
        threading.Thread(target=store.set_password, args=("report", f"source-{index}", "x"))
        for index in range(8)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert all(store.get_password("report", f"source-{index}") == "x" for index in range(8))

    time.sleep(0.25)
    assert store.get_password("report", "source-0") is None
