
import requests

BASE_URL = (
    "https://analyst-assessment-production.up.railway.app"
    "/api/v1"
)


def headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def get_account(token, account_id):
    response = requests.get(
        f"{BASE_URL}/accounts/{account_id}",
        headers=headers(token),
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def create_account(token, payload, approved=False):
    if not approved:
        raise PermissionError(
            "Account creation requires reviewer approval."
        )

    response = requests.post(
        f"{BASE_URL}/accounts",
        headers=headers(token),
        json=payload,
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def update_account(
    token, account_id, payload, approved=False
):
    if not approved:
        raise PermissionError(
            "Account update requires reviewer approval."
        )

    response = requests.patch(
        f"{BASE_URL}/accounts/{account_id}",
        headers=headers(token),
        json=payload,
        timeout=20,
    )
    response.raise_for_status()
    return response.json()
