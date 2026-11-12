
import getpass
import requests

BASE_URL = "https://analyst-assessment-production.up.railway.app/api/v1"


def get_all_accounts(token):
    accounts = []
    page = 1
    page_size = 50

    while True:
        response = requests.get(
            f"{BASE_URL}/accounts",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "page": page,
                "page_size": page_size,
            },
            timeout=20,
        )

        response.raise_for_status()
        result = response.json()

        batch = result.get("data", [])
        accounts.extend(batch)

        total = result.get("total")

        print(f"Page {page}: {len(batch)} accounts")

        if not batch:
            break

        if total is not None and len(accounts) >= total:
            break

        if len(batch) < page_size:
            break

        page += 1

    return accounts


if __name__ == "__main__":
    token = getpass.getpass("Enter CRM API Token: ").strip()

    accounts = get_all_accounts(token)

    print("\nTotal accounts retrieved:", len(accounts))

    bellhaven_accounts = [
        account for account in accounts
        if "bellhaven" in account.get("name", "").lower()
    ]

    print("Accounts with Bellhaven in name:", len(bellhaven_accounts))

