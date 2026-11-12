
import csv
import getpass
from rapidfuzz import fuzz
from crm_client import get_all_accounts


def load_locations():
    with open(
        "bellhaven_locations.csv",
        encoding="utf-8-sig"
    ) as file:
        return list(csv.DictReader(file))


def normalize(value):
    return " ".join(
        str(value or "").lower().strip().split()
    )


def compare_location(location, account):
    name_score = fuzz.ratio(
        normalize(location["name"]),
        normalize(account.get("name"))
    )

    street_score = fuzz.ratio(
        normalize(location["street"]),
        normalize(account.get("billing_street"))
    )

    city_match = (
        normalize(location["city"])
        == normalize(account.get("billing_city"))
    )

    state_match = (
        normalize(location["state"])
        == normalize(account.get("billing_state"))
    )

    zip_match = (
        normalize(location["zip"])
        == normalize(account.get("billing_zip"))
    )

    score = (
        name_score * 0.30
        + street_score * 0.40
        + (15 if zip_match else 0)
        + (10 if city_match else 0)
        + (5 if state_match else 0)
    )

    return round(score, 1)


def main():
    token = getpass.getpass("Enter CRM API Token: ").strip()

    accounts = get_all_accounts(token)
    locations = load_locations()

    print("\nMATCHING RESULTS\n")

    for location in locations:
        candidates = sorted(
            accounts,
            key=lambda account: compare_location(
                location, account
            ),
            reverse=True
        )

        best = candidates[0]
        score = compare_location(location, best)

        print(f"Website: {location['name']}")
        print(f"CRM: {best['name']}")
        print(f"Score: {score}")
        print(f"CRM Account ID: {best['account_id']}")
        print(f"Parent: {best.get('parent_name', '')}")
        print("-" * 55)


if __name__ == "__main__":
    main()
