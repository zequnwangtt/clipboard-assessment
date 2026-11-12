
import json
from pathlib import Path

from proposal_history import (
    get_decided_proposal_ids,
)

BASE_DIR = Path(__file__).resolve().parent


def merge_proposals(
    existing_proposals,
    new_proposals,
    decided_ids,
):
    # Preserve existing proposals and their evidence.
    merged = {
        proposal["id"]: proposal
        for proposal in existing_proposals
    }

    new_count = 0
    updated_count = 0
    skipped_count = 0

    for proposal in new_proposals:
        proposal_id = proposal["id"]

        if proposal_id in decided_ids:
            skipped_count += 1
            continue

        if proposal_id in merged:
            updated_count += 1
        else:
            new_count += 1

        merged[proposal_id] = proposal

    return (
        list(merged.values()),
        new_count,
        updated_count,
        skipped_count,
    )


def main():
    proposals_path = BASE_DIR / "proposals.json"

    with proposals_path.open(
        "r", encoding="utf-8"
    ) as file:
        existing = json.load(file)

    # Dry run: use existing data as the incoming batch.
    incoming = list(existing)

    decided_ids = get_decided_proposal_ids()

    merged, new_count, updated_count, skipped = (
        merge_proposals(
            existing,
            incoming,
            decided_ids,
        )
    )

    print("Existing proposals:", len(existing))
    print("Merged proposals:", len(merged))
    print("New proposals:", new_count)
    print("Updated proposals:", updated_count)
    print("Skipped reviewed proposals:", skipped)
    print("Dry run only: no files were modified.")


if __name__ == "__main__":
    main()
