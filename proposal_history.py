
import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "review_decisions.db"


def get_decided_proposal_ids(db_path=DB_FILE):
    db_path = Path(db_path)

    if not db_path.exists():
        raise FileNotFoundError(
            f"Review database not found: {db_path}"
        )

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT proposal_id
            FROM decisions
            WHERE decision IN ('Approved', 'Rejected')
            """
        ).fetchall()

    return {row[0] for row in rows}


def filter_decided_proposals(
    proposals,
    decided_ids,
):
    return [
        proposal
        for proposal in proposals
        if proposal["id"] not in decided_ids
    ]


if __name__ == "__main__":
    import json

    proposals_file = BASE_DIR / "proposals.json"

    with proposals_file.open(
        "r", encoding="utf-8"
    ) as file:
        proposals = json.load(file)

    decided_ids = get_decided_proposal_ids()

    pending = filter_decided_proposals(
        proposals,
        decided_ids,
    )

    print("Total proposals:", len(proposals))
    print("Previously decided IDs:", len(decided_ids))
    print("Remaining proposals:", len(pending))
    print("No CRM changes were made.")
