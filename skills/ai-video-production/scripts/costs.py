"""Pre-call reservation with POSIX locking; never invokes a paid provider."""
from contextlib import contextmanager
import fcntl
from pathlib import Path
import time
from core import number, read_json, write_json


@contextmanager
def locked(path):
    # Persistent lock file is harmless; kernel releases lock even after process crash.
    with Path(str(path) + ".lock").open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("Another writer owns the cost ledger") from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def reserve(root, project, action_id, provider, input_fingerprint, maximum, pricing_basis):
    budget = project.get("budget", {})
    cap = number(budget.get("cap", 0), "budget.cap")
    maximum = number(maximum, "reservation.maximum", .000001)
    if not budget.get("authorization") or not budget.get("currency") or not pricing_basis:
        raise ValueError("Missing budget authorization, currency or live pricing evidence")
    path = Path(root) / "costs.json"
    with locked(path):
        ledger = read_json(path) if path.exists() else {"currency": budget["currency"], "entries": []}
        if ledger["currency"] != budget["currency"]:
            raise ValueError("Cannot change currency of an existing ledger")
        entries = ledger["entries"]
        if any(e.get("reservation_exceeded") for e in entries):
            raise ValueError("An actual charge exceeded its reservation; resolve budget scope before new calls")
        if any(e["id"] == action_id for e in entries):
            raise ValueError("Action ID already recorded; check original result instead of resubmitting")
        if any(e["status"] == "reserved" and e["input_fingerprint"] == input_fingerprint for e in entries):
            raise ValueError("Same input has an unresolved chargeable call")
        committed = sum(e["amount"] if e["status"] == "settled" else e["maximum"] for e in entries)
        if committed + maximum > cap + 1e-9:
            raise ValueError(f"Budget exceeded: committed {committed} + reservation {maximum} > {cap}")
        entry = {"id": action_id, "provider": provider, "input_fingerprint": input_fingerprint,
                 "maximum": maximum, "status": "reserved", "pricing_basis": pricing_basis,
                 "reserved_at_unix": time.time(), "invoice_verified": False}
        entries.append(entry)
        ledger["authorization"] = budget["authorization"]
        ledger["cap"] = cap
        write_json(path, ledger)
        return entry


def settle(root, action_id, amount, response_id, invoice_verified=False):
    number(amount, "amount")
    path = Path(root) / "costs.json"
    with locked(path):
        ledger = read_json(path)
        entries = [e for e in ledger["entries"] if e["id"] == action_id]
        if len(entries) != 1 or entries[0]["status"] != "reserved":
            raise ValueError("Only one existing reserved call can be settled")
        entry = entries[0]
        entry.update(status="settled", amount=amount, response_id=response_id,
                     invoice_verified=invoice_verified, settled_at_unix=time.time())
        entry["reservation_exceeded"] = amount > entry["maximum"]
        write_json(path, ledger)
        return entry
