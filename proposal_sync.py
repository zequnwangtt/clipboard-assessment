
import json
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "review_decisions.db"


def sync_pending_proposals(proposals, db_path=DB_FILE):
    db_path = Path(db_path)

    if not db_path.exists():
        raise FileNotFoundError(
            f"Review database not found: {db_path}"
        )

    inserted = 0
    preserved = 0

    with sqlite3.connect(db_path) as conn:
        for proposal in proposals:
            proposal_id = proposal["id"]

            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO decisions (
                    proposal_id,
                    decision,
                    current_values,
                    proposed_values,
                    evidence_json
                )
                VALUES (?, 'Pending', ?, ?, ?)
                """,
                (
                    proposal_id,
                    json.dumps(
                        {},
                        ensure_ascii=False
                    ),
                    json.dumps(
                        {},
                        ensure_ascii=False
                    ),
                    json.dumps(
                        {
                            "matching_evidence":
                                proposal.get("evidence", ""),
                            "source_url":
                                proposal.get("source_url", ""),
                        },
                        ensure_ascii=False,
                    ),
                ),
            )

            if cursor.rowcount == 1:
                inserted += 1
            else:
                preserved += 1

    return inserted, preserved


if __name__ == "__main__":
    import sys

    if "--dry-run" not in sys.argv:
        raise SystemExit(
            "Use --dry-run for a read-only check."
        )

    with (BASE_DIR / "proposals.json").open(
        "r", encoding="utf-8"
    ) as file:
        proposals = json.load(file)

    with sqlite3.connect(DB_FILE) as conn:
        existing_ids = {
            row[0]
            for row in conn.execute(
                "SELECT proposal_id FROM decisions"
            )
        }

    new_count = sum(
        p["id"] not in existing_ids
        for p in proposals
    )

    print("Proposals:", len(proposals))
    print("New Pending records needed:", new_count)
    print(
        "Existing records preserved:",
        len(proposals) - new_count,
    )
    print("DRY RUN: Database not modified.")
