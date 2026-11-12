

"""Safe daily proposal reconciliation.

Usage:
    python3 daily_run.py          # Dry run, no changes
    python3 daily_run.py --apply  # Save new proposals only

Never modifies CRM accounts or review decisions.
"""

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
PROPOSALS = BASE / "proposals.json"
DB = BASE / "review_decisions.db"
GENERATOR = BASE / "proposal_generator.py"


def load_proposals(path):
    with path.open(encoding="utf-8") as f:
        rows = json.load(f)

    if not isinstance(rows, list):
        raise ValueError(f"{path.name} must contain a JSON array")

    ids = [p["id"] for p in rows]

    if (
        any(not isinstance(i, str) or not i for i in ids)
        or len(ids) != len(set(ids))
    ):
        raise ValueError(
            f"{path.name} contains invalid or duplicate proposal IDs"
        )

    return rows


def reconcile(existing, incoming, decided):
    """Keep existing proposals unchanged; add only new undecided IDs."""

    by_id = {p["id"]: p for p in existing}

    added = 0
    skipped_decided = 0
    already_present = 0

    for proposal in incoming:
        proposal_id = proposal["id"]

        if proposal_id in decided:
            skipped_decided += 1

        elif proposal_id in by_id:
            already_present += 1

        else:
            by_id[proposal_id] = proposal
            added += 1

    return (
        list(by_id.values()),
        added,
        already_present,
        skipped_decided,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Safe daily CRM proposal reconciliation"
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Save new proposals after reconciliation",
    )

    args = parser.parse_args()

    print(
        "Daily run started:",
        datetime.now(timezone.utc).isoformat(),
        flush=True,
    )

    for path in (PROPOSALS, DB, GENERATOR):
        if not path.is_file():
            raise RuntimeError(f"Required file missing: {path.name}")

    if not os.environ.get("CRM_API_TOKEN"):
        raise RuntimeError(
            "CRM_API_TOKEN environment variable is required."
        )

    # Prevent two daily jobs from running simultaneously.
    # fcntl is supported on macOS and Linux.
    import fcntl

    lock_path = BASE / ".daily_run.lock"

    with lock_path.open("a+") as lock:
        fcntl.flock(
            lock,
            fcntl.LOCK_EX | fcntl.LOCK_NB,
        )

        # Generate into a temporary file, never proposals.json.
        with tempfile.TemporaryDirectory(
            prefix="daily_proposals_",
            dir=BASE,
        ) as temp_dir:

            generated = Path(temp_dir) / "generated.json"

            env = os.environ.copy()
            env["PROPOSALS_OUTPUT"] = str(generated)

            subprocess.run(
                [sys.executable, str(GENERATOR)],
                cwd=BASE,
                env=env,
                check=True,
            )

            incoming = load_proposals(generated)

            with sqlite3.connect(DB, timeout=30) as conn:
                conn.execute("BEGIN IMMEDIATE")

                # Never re-propose reviewed items.
                decided = {
                    row[0]
                    for row in conn.execute(
                        """
                        SELECT proposal_id
                        FROM decisions
                        WHERE LOWER(TRIM(decision))
                              IN ('approved', 'rejected')
                        """
                    )
                }

                existing = load_proposals(PROPOSALS)

                (
                    merged,
                    added,
                    already_present,
                    skipped_decided,
                ) = reconcile(
                    existing,
                    incoming,
                    decided,
                )

                print("\nDaily reconciliation summary:")
                print("Existing proposals:", len(existing))
                print("Incoming proposals:", len(incoming))
                print("Merged proposals:", len(merged))
                print("New proposals:", added)
                print("Already present:", already_present)
                print("Skipped reviewed:", skipped_decided)

                if args.apply and added > 0:

                    # Atomic file replacement.
                    fd, temp_name = tempfile.mkstemp(
                        prefix=".proposals_",
                        suffix=".json",
                        dir=BASE,
                    )

                    try:
                        with os.fdopen(
                            fd, "w", encoding="utf-8"
                        ) as out:

                            json.dump(
                                merged,
                                out,
                                indent=2,
                                ensure_ascii=False,
                            )

                            out.write("\n")
                            out.flush()
                            os.fsync(out.fileno())

                        os.replace(temp_name, PROPOSALS)

                    finally:
                        if os.path.exists(temp_name):
                            os.unlink(temp_name)

                conn.commit()

    if args.apply:
        print("\nAPPLIED: New proposals saved.")
        print("No CRM accounts or review decisions changed.")
    else:
        print("\nDRY RUN ONLY")
        print("No proposal, decision, or CRM records changed.")


if __name__ == "__main__":
    main()
