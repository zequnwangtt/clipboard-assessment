
import csv
import json
import getpass
import os
import re
from pathlib import Path
from collections import defaultdict

from rapidfuzz import fuzz
from crm_client import get_all_accounts


BELLHAVEN_PARENT_ID = "0015QAPLGS3FVYEEEM"
BASE_DIR = Path(__file__).resolve().parent


def normalize(value):
    value = str(value or "").lower()

    replacements = {
        "northwest": "nw",
        "northeast": "ne",
        "southwest": "sw",
        "southeast": "se",
        "west": "w",
        "east": "e",
        "north": "n",
        "south": "s",
        "street": "st",
        "road": "rd",
        "drive": "dr",
        "lane": "ln",
        "avenue": "ave",
        "boulevard": "blvd",
        "pike": "pk",
    }

    for original, replacement in replacements.items():
        value = re.sub(
            rf"\b{original}\b",
            replacement,
            value,
        )

    return " ".join(
        re.sub(r"[^a-z0-9 ]", " ", value).split()
    )


def address_match(site, crm):
    return (
        normalize(site["street"])
        == normalize(crm.get("billing_street"))
        and normalize(site["city"])
        == normalize(crm.get("billing_city"))
        and normalize(site["state"])
        == normalize(crm.get("billing_state"))
        and normalize(site["zip"])
        == normalize(crm.get("billing_zip"))
    )


def find_candidates(site, accounts):
    candidates = []

    for account in accounts:
        same_city = (
            normalize(site["city"])
            == normalize(account.get("billing_city"))
        )

        same_state = (
            normalize(site["state"])
            == normalize(account.get("billing_state"))
        )

        same_zip = (
            normalize(site["zip"])
            == normalize(account.get("billing_zip"))
        )

        same_street = (
            normalize(site["street"])
            == normalize(account.get("billing_street"))
        )

        name_score = fuzz.ratio(
            normalize(site["name"]),
            normalize(account.get("name")),
        )

        # Exact street, city and state are strong evidence,
        # even when the ZIP code differs.
        if same_street and same_city and same_state:
            score = 100

        elif same_city and same_state and same_zip:
            score = 75 + name_score * 0.2

        elif same_state and same_zip and name_score >= 60:
            score = 65 + name_score * 0.2

        else:
            score = name_score * 0.3

        if score >= 50:
            candidates.append((score, account))

    return sorted(
        candidates,
        key=lambda x: x[0],
        reverse=True,
    )


def build_proposal(site, account, issue, action, evidence):
    account_part = (
        account["account_id"]
        if account
        else normalize(site["name"])
    )

    return {
        "id": (
            f"{issue.lower().replace(' ', '_')}_"
            f"{account_part}"
        ),
        "facility": site["name"],
        "issue": issue,
        "account_id": (
            account["account_id"] if account else ""
        ),
        "evidence": evidence,
        "action": action,
        "source_url": site["source_url"],
    }


def main():
    # Use environment token for scheduled runs.
    # Fall back to interactive input for manual runs.
    token = (
        os.environ.get("CRM_API_TOKEN")
        or getpass.getpass("Enter CRM API Token: ")
    ).strip()

    if not token:
        raise RuntimeError("CRM API Token is required.")

    accounts = get_all_accounts(token)

    locations_file = BASE_DIR / "bellhaven_locations.csv"

    with locations_file.open(
        "r",
        encoding="utf-8-sig",
    ) as f:
        locations = list(csv.DictReader(f))

    proposals = []
    matched_ids = set()

    # Match website facilities against CRM accounts.
    for site in locations:
        candidates = find_candidates(site, accounts)

        if not candidates or candidates[0][0] < 70:
            proposals.append(
                build_proposal(
                    site,
                    None,
                    "Missing CRM Account",
                    (
                        "Create a new account under "
                        "Bellhaven Senior Living."
                    ),
                    (
                        "No reliable match. Website address: "
                        f"{site['street']}, {site['city']}, "
                        f"{site['state']} {site['zip']}"
                    ),
                )
            )
            continue

        score, account = candidates[0]
        matched_ids.add(account["account_id"])

        evidence = (
            f"Match score: {score:.1f}. "
            f"Website address: {site['street']}, "
            f"{site['city']}, {site['state']} "
            f"{site['zip']}. "
            f"CRM address: "
            f"{account.get('billing_street')}, "
            f"{account.get('billing_city')}, "
            f"{account.get('billing_state')} "
            f"{account.get('billing_zip')}."
        )

        wrong_parent = (
            account.get("parent_id")
            != BELLHAVEN_PARENT_ID
        )

        revenue = float(
            account.get("lifetime_revenue") or 0
        )

        ar = float(
            account.get("outstanding_ar") or 0
        )

        # Follow the required CHOW SOP.
        if wrong_parent:
            if revenue > 0 and ar > 0:
                issue = "CHOW Required"

                action = (
                    "Preserve original account and parent. "
                    "Create new account under Bellhaven. "
                    "Link original using chow_current_account."
                )

            else:
                issue = "Wrong Parent"

                action = (
                    "Update parent_id to "
                    "Bellhaven Senior Living."
                )

            proposals.append(
                build_proposal(
                    site,
                    account,
                    issue,
                    action,
                    (
                        evidence
                        + f" Revenue: {revenue}; AR: {ar}."
                    ),
                )
            )

        # Detect outdated facility names.
        if (
            normalize(site["name"])
            != normalize(account["name"])
        ):
            proposals.append(
                build_proposal(
                    site,
                    account,
                    "Outdated Name",
                    f"Update name to {site['name']}.",
                    evidence,
                )
            )

        # Detect address discrepancies.
        if (
            normalize(site["street"])
            != normalize(account.get("billing_street"))
            or normalize(site["zip"])
            != normalize(account.get("billing_zip"))
        ):
            proposals.append(
                build_proposal(
                    site,
                    account,
                    "Address Mismatch",
                    "Review and update CRM address fields.",
                    evidence,
                )
            )

    # Identify possible duplicate accounts by address.
    address_groups = defaultdict(list)

    for account in accounts:
        key = (
            normalize(account.get("billing_street")),
            normalize(account.get("billing_city")),
            normalize(account.get("billing_state")),
            normalize(account.get("billing_zip")),
        )

        if all(key):
            address_groups[key].append(account)

    for group in address_groups.values():
        if len(group) < 2:
            continue

        for account in group[1:]:
            proposals.append(
                {
                    "id": (
                        f"duplicate_{account['account_id']}"
                    ),
                    "facility": account["name"],
                    "issue": "Possible Duplicate",
                    "account_id": account["account_id"],
                    "evidence": (
                        "Multiple CRM accounts share "
                        "the same normalized address."
                    ),
                    "action": (
                        "Review survivor account. "
                        "Mark losing account Inactive "
                        "and set duplicate_of_account."
                    ),
                    "source_url": "",
                }
            )

    # Detect active Bellhaven CRM accounts
    # missing from the website matching results.
    for account in accounts:
        if (
            account.get("parent_id")
            == BELLHAVEN_PARENT_ID
            and account["account_id"] not in matched_ids
            and account.get("status") == "Active"
        ):
            proposals.append(
                {
                    "id": (
                        f"stale_{account['account_id']}"
                    ),
                    "facility": account["name"],
                    "issue": "Missing from Website",
                    "account_id": account["account_id"],
                    "evidence": (
                        "Active CRM account under "
                        "Bellhaven parent was not matched "
                        "to a website location."
                    ),
                    "action": (
                        "Review whether account should "
                        "be marked Inactive or Needs Review."
                    ),
                    "source_url": "",
                }
            )

    # Daily Run sets PROPOSALS_OUTPUT to a temporary
    # file so reviewed proposals are never overwritten.
    output_path = Path(
        os.environ.get(
            "PROPOSALS_OUTPUT",
            str(BASE_DIR / "proposals.json"),
        )
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            proposals,
            f,
            indent=2,
            ensure_ascii=False,
        )
        f.write("\n")

    print("\nGenerated proposals:", len(proposals))

    counts = defaultdict(int)

    for proposal in proposals:
        counts[proposal["issue"]] += 1

    for issue, count in sorted(counts.items()):
        print(f"{issue}: {count}")

    print(f"\nSaved to: {output_path}")
    print("No CRM records were modified.")


if __name__ == "__main__":
    main()
