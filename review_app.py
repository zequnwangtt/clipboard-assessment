import csv
import sqlite3
import streamlit as st
from crm_writer import get_account, update_account, create_account
from crm_client import get_all_accounts

DB_FILE = "review_decisions.db"


import json

with open("proposals.json", "r", encoding="utf-8") as f:
    PROPOSALS = json.load(f)



def connect_db():
    return sqlite3.connect(DB_FILE)



def init_db():
    with connect_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS decisions (
                proposal_id TEXT PRIMARY KEY,
                decision TEXT NOT NULL,
                decided_at TEXT DEFAULT CURRENT_TIMESTAMP,
                execution_status TEXT,
                executed_at TEXT,
                execution_error TEXT,
                current_values TEXT,
                proposed_values TEXT,
                evidence_json TEXT,
                survivor_account_id TEXT
            )
        """)

        required_columns = {
            "execution_status": "TEXT",
            "executed_at": "TEXT",
            "execution_error": "TEXT",
            "current_values": "TEXT",
            "proposed_values": "TEXT",
            "evidence_json": "TEXT",
            "survivor_account_id": "TEXT",
        }

        existing_columns = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(decisions)"
            ).fetchall()
        }

        for column, data_type in required_columns.items():
            if column not in existing_columns:
                conn.execute(
                    f"ALTER TABLE decisions "
                    f"ADD COLUMN {column} {data_type}"
                )



def get_saved_evidence(proposal_id):
    with connect_db() as conn:
        row = conn.execute(
            """
            SELECT current_values,
                   proposed_values,
                   evidence_json
            FROM decisions
            WHERE proposal_id = ?
            """,
            (proposal_id,),
        ).fetchone()

    if not row:
        return None

    if not any(value is not None for value in row):
        return None

    return {
        "current": json.loads(row[0]) if row[0] else {},
        "proposed": json.loads(row[1]) if row[1] else {},
        "evidence": json.loads(row[2]) if row[2] else {},
    }


def show_saved_evidence(proposal):
    saved = get_saved_evidence(proposal["id"])

    if saved is None:
        st.info(
            "Historical evidence was not captured "
            "for this proposal."
        )
        return

    st.markdown("### Before / After")

    current = saved["current"]
    proposed = saved["proposed"]
    evidence = saved["evidence"]

    fields = sorted(set(current) | set(proposed))

    if fields:
        rows = [
            {
                "Field": field,
                "Before (CRM snapshot)": current.get(field),
                "Proposed": proposed.get(field),
            }
            for field in fields
            if field in proposed
        ]

        if rows:
            st.dataframe(
                rows,
                use_container_width=True,
                hide_index=True,
            )

    st.caption(
        "CRM values are from a local snapshot. "
        "They may differ from the current live CRM."
    )

    if evidence.get("source_url"):
        st.write(
            "**Website Source:**",
            evidence["source_url"],
        )

    if evidence.get("matching_evidence"):
        st.write(
            "**Matching Evidence:**",
            evidence["matching_evidence"],
        )


def get_saved_evidence(proposal_id):
    with connect_db() as conn:
        row = conn.execute(
            """
            SELECT current_values,
                   proposed_values,
                   evidence_json
            FROM decisions
            WHERE proposal_id = ?
            """,
            (proposal_id,),
        ).fetchone()

    if not row:
        return None

    if not any(value is not None for value in row):
        return None

    return {
        "current": json.loads(row[0]) if row[0] else {},
        "proposed": json.loads(row[1]) if row[1] else {},
        "evidence": json.loads(row[2]) if row[2] else {},
    }


def show_saved_evidence(proposal):
    saved = get_saved_evidence(proposal["id"])

    if saved is None:
        st.info("Historical evidence was not captured for this proposal.")
        return

    st.markdown("### Before / After")

    current = saved["current"]
    proposed = saved["proposed"]
    evidence = saved["evidence"]

    if proposal.get("issue") == "CHOW Required":
        rows = [
            {
                "Field": "Old Account ID",
                "Before (CRM snapshot)": current.get("account_id"),
                "Proposed": "UNCHANGED",
            },
            {
                "Field": "Old Account Parent",
                "Before (CRM snapshot)": (
                    str(current.get("parent_name") or "")
                    + " (" + str(current.get("parent_id") or "") + ")"
                ),
                "Proposed": "UNCHANGED",
            },
            {
                "Field": "Old Account chow_current_account",
                "Before (CRM snapshot)": current.get(
                    "chow_current_account", "Not captured"
                ),
                "Proposed": "NEW_ACCOUNT_ID_AFTER_CREATION",
            },
            {
                "Field": "New Account",
                "Before (CRM snapshot)": "Not yet created (verify live CRM)",
                "Proposed": "Create " + proposal.get("facility", ""),
            },
            {
                "Field": "New Account Parent",
                "Before (CRM snapshot)": "N/A",
                "Proposed": proposed.get(
                    "new_account.parent_id", "Not specified"
                ),
            },
        ]
    else:
        fields = sorted(set(current) | set(proposed))
        rows = [
            {
                "Field": field,
                "Before (CRM snapshot)": current.get(field),
                "Proposed": proposed.get(field),
            }
            for field in fields
            if field in proposed
        ]

    if rows:
        st.dataframe(
            rows,
            use_container_width=True,
            hide_index=True,
        )

    st.caption(
        "CRM values are from a local snapshot. "
        "They may differ from the current live CRM."
    )

    if evidence.get("source_url"):
        st.write(
            "**Website Source:**",
            evidence["source_url"],
        )

    if evidence.get("matching_evidence"):
        st.write(
            "**Matching Evidence:**",
            evidence["matching_evidence"],
        )


def write_audit_event(
    conn, proposal_id, event_type,
    event_status, details=None
):
    conn.execute(
        """
        INSERT INTO audit_events (
            proposal_id,
            event_type,
            event_status,
            event_details
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            proposal_id,
            event_type,
            event_status,
            json.dumps(details or {}, ensure_ascii=False),
        ),
    )


def get_audit_events(proposal_id):
    with connect_db() as conn:
        rows = conn.execute(
            """
            SELECT event_type, event_status,
                   event_details, created_at
            FROM audit_events
            WHERE proposal_id = ?
            ORDER BY event_id DESC
            """,
            (proposal_id,),
        ).fetchall()

    return [
        {
            "Event": row[0],
            "Status": row[1],
            "Details": row[2],
            "Time (UTC)": row[3],
        }
        for row in rows
    ]


def get_decisions():
    with connect_db() as conn:
        rows = conn.execute(
            """
            SELECT
                proposal_id,
                decision,
                execution_status,
                survivor_account_id
            FROM decisions
            """
        ).fetchall()

    return {
        row[0]: {
            "decision": row[1],
            "execution_status": row[2],
            "survivor_account_id": row[3],
        }
        for row in rows
    }



def save_decision(proposal_id, decision, survivor_account_id=None):
    if decision not in {"Approved", "Rejected"}:
        raise ValueError("Invalid review decision.")

    if survivor_account_id is not None:
        survivor_account_id = survivor_account_id.strip()
        if not survivor_account_id:
            raise ValueError("Survivor Account ID cannot be empty.")
        if decision != "Approved":
            raise ValueError(
                "Survivor Account ID requires approval."
            )

    with connect_db() as conn:
        cursor = conn.execute(
            """
            UPDATE decisions
            SET decision = ?,
                survivor_account_id = ?,
                decided_at = CURRENT_TIMESTAMP
            WHERE proposal_id = ?
              AND decision = 'Pending'
            """,
            (decision, survivor_account_id, proposal_id),
        )

        if cursor.rowcount != 1:
            raise ValueError(
                "Proposal already reviewed or missing."
            )

        write_audit_event(
            conn,
            proposal_id,
            "Review Decision",
            decision,
            {
                "decision": decision,
                "survivor_account_id": survivor_account_id,
            },
        )




def mark_execution(proposal_id, status, error=None):
    if status not in {"Verified", "Failed"}:
        raise ValueError("Invalid execution status.")

    with connect_db() as conn:
        cursor = conn.execute(
            """
            UPDATE decisions
            SET execution_status = ?,
                execution_error = ?,
                executed_at = CURRENT_TIMESTAMP
            WHERE proposal_id = ?
              AND decision = 'Approved'
              AND COALESCE(
                  execution_status, 'Not Applied'
              ) != 'Verified'
            """,
            (status, error, proposal_id),
        )

        if cursor.rowcount != 1:
            raise ValueError(
                "Proposal is not eligible for execution."
            )

        write_audit_event(
            conn,
            proposal_id,
            "CRM Execution",
            status,
            {"error": error} if error else {},
        )



    
BELLHAVEN_PARENT_ID = "0015QAPLGS3FVYEEEM"

# Three Union Square proposals share an account with a material address mismatch.
# Execution is opt-in per approved proposal, with extra identity confirmation.
UNION_SQUARE_ACCOUNT_ID = "001GNU41AVXZRLLJ9P"
UNION_SQUARE_FACILITY = "Bellhaven at Union Square"
UNION_SQUARE_ISSUES = {"Outdated Name", "Wrong Parent", "Address Mismatch"}
UNION_SQUARE_OLD_ADDRESS = ("240 Market St", "New Albany", "OH", "43054")
UNION_SQUARE_NEW_ADDRESS = ("118 Union Square Dr", "New Albany", "OH", "43054")


def is_union_square_proposal(proposal):
    return (
        proposal.get("account_id") == UNION_SQUARE_ACCOUNT_ID
        and proposal.get("facility") == UNION_SQUARE_FACILITY
        and proposal.get("issue") in UNION_SQUARE_ISSUES
    )


def crm_address(account):
    return tuple(str(account.get(k) or "").strip() for k in (
        "billing_street", "billing_city", "billing_state", "billing_zip"
    ))


def normalize_address_tuple(values):
    return tuple(re.sub(r"[^a-z0-9]", "", str(v).lower()) for v in values)


def validate_union_square(proposal, current, payload):
    if not is_union_square_proposal(proposal):
        raise ValueError("Not an authorized Union Square proposal.")
    saved = get_saved_evidence(proposal["id"])
    if not saved or not saved.get("current"):
        raise ValueError("Original CRM snapshot missing; manual review required.")
    old = saved["current"]
    if old.get("account_id") not in (None, "", UNION_SQUARE_ACCOUNT_ID):
        raise ValueError("Saved CRM identity differs from proposal.")
    # The same account has three separate proposals, so allow either the original
    # or proposed address while the reviewer executes them individually.
    actual = normalize_address_tuple(crm_address(current))
    allowed = {normalize_address_tuple(UNION_SQUARE_OLD_ADDRESS),
               normalize_address_tuple(UNION_SQUARE_NEW_ADDRESS)}
    if actual not in allowed:
        raise ValueError("Live CRM address changed unexpectedly; stop and review.")
    if current.get("chow_current_account"):
        raise ValueError("CHOW link exists; manual review required.")
    issue = proposal["issue"]
    if issue == "Outdated Name":
        original_name = old.get("name")
        if not original_name or current.get("name") not in (original_name, UNION_SQUARE_FACILITY):
            raise ValueError("CRM name no longer matches original review evidence.")
        if payload != {"name": UNION_SQUARE_FACILITY}:
            raise ValueError("Unexpected name change payload.")
    elif issue == "Wrong Parent":
        original_parent = old.get("parent_id")
        if not original_parent or current.get("parent_id") not in (original_parent, BELLHAVEN_PARENT_ID):
            raise ValueError("CRM parent no longer matches original review evidence.")
        if payload != {"parent_id": BELLHAVEN_PARENT_ID}:
            raise ValueError("Unexpected parent change payload.")
    else:
        expected = dict(zip(("billing_street", "billing_city", "billing_state", "billing_zip"),
                            UNION_SQUARE_NEW_ADDRESS))
        if payload != expected:
            raise ValueError("Unexpected address change payload.")
    return True




SAFE_PARENT_CHANGES = {
    "Bellhaven Crossings of Lima",
    "Bellhaven of Zanesville",
}


SAFE_NAME_CHANGES = {
    "Bellhaven Rehabilitation & Nursing of Grove City":
        "001TZCSTBZFM6K5BGN",

    "Bellhaven at Sycamore Ridge":
        "00191H7JR16471SZ34",

    "The Arbors at Bellhaven - Dayton":
        "0010KJFP601YNTZVDA",

    "Bellhaven Healthcare Centre of Ashland":
        "001RJ0D7Z5MAZN5HX5",

    "Bellhaven of Zanesville":
        "001H1JMVZWP46D5VUF",

    "Bellhaven of Chagrin Falls":
        "001RJU1X4NBWC1Q0G7",

    "Bellhaven Willow Creek":
        "0017MN2JYAJBDS8WQZ",

    "Bellhaven of Chesterton":
        "0013NUZQHQUEZ8DXEG",

    "Bellhaven of Kettering":
        "001WR41PYNWXCAE2X4",
}



def get_patch_payload(proposal):
    """
    Return a PATCH payload only for specifically
    reviewed, evidence-backed proposals.
    """
    issue = proposal["issue"]
    facility = proposal["facility"]

    if is_union_square_proposal(proposal):
        if issue == "Outdated Name":
            return {"name": UNION_SQUARE_FACILITY}
        if issue == "Wrong Parent":
            return {"parent_id": BELLHAVEN_PARENT_ID}
        return dict(zip(
            ("billing_street", "billing_city", "billing_state", "billing_zip"),
            UNION_SQUARE_NEW_ADDRESS,
        ))

    if (
        issue == "Address Mismatch"
        and facility == "Bellhaven of Portsmouth"
        and proposal["account_id"] == "001CF3LDWVRGL09P4F"
    ):
        return {"billing_zip": "45662"}

    if (
        issue == "Wrong Parent"
        and facility in SAFE_PARENT_CHANGES
    ):
        return {"parent_id": BELLHAVEN_PARENT_ID}

    if (
    issue == "Outdated Name"
    and SAFE_NAME_CHANGES.get(facility)
        == proposal["account_id"]
    ):
        return {"name": facility}

    return None


BELLHAVEN_PARENT_NAME = "Bellhaven Senior Living"

def load_website_locations():
    with open(
        "bellhaven_locations.csv",
        newline="",
        encoding="utf-8-sig",
    ) as f:
        return list(csv.DictReader(f))


@st.cache_data
def load_crm_snapshot():
    with open(
        "crm_snapshot.json",
        encoding="utf-8",
    ) as f:
        return json.load(f)["accounts"]


def show_issue_evidence(proposal, crm_account=None):
    issue = proposal["issue"]
    facility = proposal["facility"]

    st.markdown("### Evidence")

    if issue == "Wrong Parent":
        st.write("**Current CRM Parent:**")
        st.write(
            crm_account.get("parent_name", "Not loaded")
            if crm_account else "Not loaded"
        )

        st.write("**Proposed Parent:**")
        st.write(BELLHAVEN_PARENT_NAME)

        st.caption(
            "The proposed parent is based on the "
            "Bellhaven website affiliation. "
            "Address matching supports account identity."
        )

    elif issue == "Outdated Name":
        st.write("**Current CRM Name:**")
        st.write(
            crm_account.get("name", "Not loaded")
            if crm_account else "Not loaded"
        )

        st.write("**Proposed Website Name:**")
        st.write(facility)

    elif issue == "Address Mismatch":
        st.write("**Current CRM Address:**")
        if crm_account:
            st.write(
                ", ".join(
                    str(crm_account.get(field) or "")
                    for field in [
                        "billing_street",
                        "billing_city",
                        "billing_state",
                        "billing_zip",
                    ]
                )
            )
        else:
            st.write("Not loaded")

        st.write("**Website Address:**")
        locations = load_website_locations()
        match = next(
            (x for x in locations if x["name"] == facility),
            None,
        )

        if match:
            st.write(
                f"{match['street']}, {match['city']}, "
                f"{match['state']} {match['zip']}"
            )
        else:
            st.warning("Website record not found.")

    else:
        st.write(proposal.get("evidence", ""))

    st.caption(
        "Original matching evidence: "
        + proposal.get("evidence", "")
    )



from decimal import Decimal, InvalidOperation


import re


VERIFIED_PARENT_TARGETS = {
    "001LGFPBJY4N9MB6KL": {
        "facility": "Bellhaven Crossings of Lima",
        "street": "3115 N Cole St",
        "city": "Lima",
        "state": "OH",
        "zip": "45801",
        "old_parent": "001FJZYHR7MLFMNPLL",
    },
    "001H1JMVZWP46D5VUF": {
        "facility": "Bellhaven of Zanesville",
        "street": "2680 Maple Ave",
        "city": "Zanesville",
        "state": "OH",
        "zip": "43701",
        "old_parent": "001FWSQ30SFW6S7604",
    },
}


def normalize_street(value):
    value = (value or "").lower().strip()
    value = re.sub(r"[^\w\s]", " ", value)
    value = re.sub(r"\bavenue\b", "ave", value)
    value = re.sub(r"\bstreet\b", "st", value)
    value = re.sub(r"\s+", " ", value)
    return value


def validate_parent_target(proposal, current, payload):
    if "parent_id" not in payload:
        return True

    account_id = proposal["account_id"]
    expected = VERIFIED_PARENT_TARGETS.get(account_id)

    if expected is None:
        if is_union_square_proposal(proposal):
            return True  # validated separately by validate_union_square
        raise ValueError(
            "Parent change is not authorized for this account."
        )

    if proposal["facility"] != expected["facility"]:
        raise ValueError("Facility name mismatch.")

    if payload["parent_id"] != BELLHAVEN_PARENT_ID:
        raise ValueError("Unexpected target parent.")

    actual_address = (
        normalize_street(current.get("billing_street")),
        str(current.get("billing_city") or "").strip().lower(),
        str(current.get("billing_state") or "").strip().upper(),
        str(current.get("billing_zip") or "").strip(),
    )

    expected_address = (
        normalize_street(expected["street"]),
        expected["city"].lower(),
        expected["state"],
        expected["zip"],
    )

    if actual_address != expected_address:
        raise ValueError(
            "CRM address changed or does not match website."
        )

    if current.get("parent_id") not in {
        expected["old_parent"],
        BELLHAVEN_PARENT_ID,
    }:
        raise ValueError(
            "CRM parent changed unexpectedly."
        )

    return True



def validate_before_patch(proposal, current, payload):
    """
    Validate account identity and business rules
    before making a CRM PATCH request.
    """
    account_id = proposal["account_id"]
    facility = proposal["facility"]
    issue = proposal["issue"]

    if current.get("account_id") != account_id:
        raise ValueError("CRM account ID mismatch.")

    if current.get("duplicate_of_account"):
        raise ValueError(
            "This account is marked as a duplicate."
        )

    if current.get("status") != "Active":
        raise ValueError(
            "Only Active accounts can be updated."
        )

    if "parent_id" in payload:
        try:
            revenue = Decimal(
                str(current.get("lifetime_revenue", 0))
            )
            ar = Decimal(
                str(current.get("outstanding_ar", 0))
            )
        except (InvalidOperation, TypeError):
            raise ValueError(
                "Invalid revenue or AR value."
            )

        if revenue > 0 and ar > 0:
            raise ValueError(
                "CHOW required: revenue and AR "
                "are both positive."
            )

   
    if issue == "Outdated Name":
        if payload.get("name") != facility:
            raise ValueError(
                "Proposed name does not match facility."
            )

        if (
            SAFE_NAME_CHANGES.get(facility)
            != account_id
            and not is_union_square_proposal(proposal)
        ):
            raise ValueError(
                "Account ID is not authorized "
                "for this name change."
            )

        original = get_saved_evidence(
            proposal["id"]
        )

        if original is None:
            raise ValueError(
                "Original CRM evidence is missing."
            )

        expected_name = original["current"].get("name")

        if not expected_name:
            raise ValueError(
                "Original CRM name is missing."
            )

        actual_name = current.get("name")

        if actual_name not in {
            expected_name,
            facility,
        }:
            raise ValueError(
                "CRM name changed since review. "
                "Manual revalidation required."
            )


    return True


def validate_duplicate_accounts(loser, survivor):
    """Validate live CRM accounts before duplicate resolution."""

    loser_id = loser.get("account_id")
    survivor_id = survivor.get("account_id")

    if not loser_id or not survivor_id:
        raise ValueError("Missing CRM account ID.")

    if loser_id == survivor_id:
        raise ValueError(
            "Survivor and duplicate cannot be the same account."
        )

    for account, label in [
        (loser, "Duplicate"),
        (survivor, "Survivor"),
    ]:
        if account.get("status") != "Active":
            raise ValueError(
                f"{label} account must be Active."
            )

        if account.get("duplicate_of_account"):
            raise ValueError(
                f"{label} is already marked as a duplicate."
            )

    address_fields = [
        "billing_street",
        "billing_city",
        "billing_state",
        "billing_zip",
    ]

    for field in address_fields:
        loser_value = str(loser.get(field) or "").strip().lower()
        survivor_value = str(survivor.get(field) or "").strip().lower()

        if not loser_value or loser_value != survivor_value:
            raise ValueError(
                f"Account address mismatch: {field}"
            )

    return True




def duplicate_comparison_rows(accounts, proposal):
    """Find candidate accounts by exact normalized address, read-only."""
    target_id = str(proposal.get("account_id") or "")
    by_id = {str(a.get("account_id") or ""): a for a in accounts}
    target = by_id.get(target_id)
    if target is None:
        return None, []

    address_fields = ("billing_street", "billing_city", "billing_state", "billing_zip")
    def norm(value):
        return re.sub(r"[^a-z0-9]", "", str(value or "").lower())

    target_address = tuple(norm(target.get(field)) for field in address_fields)
    if not all(target_address):
        return target, [target]

    candidates = [a for a in accounts if all(
        norm(a.get(field)) == target_address[i]
        for i, field in enumerate(address_fields)
    )]
    candidates.sort(key=lambda a: (str(a.get("account_id")) != target_id,
                                   str(a.get("name") or "")))
    return target, candidates


def show_duplicate_comparison(proposal):
    """Fetch live CRM data for human review. Never writes to CRM."""
    st.markdown("#### Live CRM Duplicate Comparison (read-only)")
    st.caption("Use the CRM token to load current accounts. This does not approve, reject, or modify any CRM record.")
    pid = proposal["id"]
    token = st.text_input("CRM API Token for comparison", type="password",
                          key=f"compare_token_{pid}")
    if st.button("Load Live CRM Candidates", key=f"compare_load_{pid}", disabled=not token):
        try:
            accounts = get_all_accounts(token)
            if not isinstance(accounts, list):
                raise ValueError("CRM did not return a list of accounts.")
            target, candidates = duplicate_comparison_rows(accounts, proposal)
            if target is None:
                st.session_state.pop(f"compare_result_{pid}", None)
                st.error("The proposal account was not found in the live CRM.")
            else:
                st.session_state[f"compare_result_{pid}"] = (target, candidates)
        except Exception as exc:
            st.session_state.pop(f"compare_result_{pid}", None)
            st.error(f"Could not load CRM accounts: {exc}")

    result = st.session_state.get(f"compare_result_{pid}")
    if not result:
        return
    target, candidates = result
    st.write(f"**Proposal account:** {target.get('name') or 'Unknown'} ({target.get('account_id')})")
    if len(candidates) < 2:
        st.warning("No second account with an identical normalized billing address was found. Do not assume duplication.")
    else:
        st.info(f"Found {len(candidates)} accounts at the same normalized billing address. Address alone does not prove duplication or identify a survivor.")
    fields = (
        ("Account ID", "account_id"), ("Name", "name"),
        ("Street", "billing_street"), ("City", "billing_city"),
        ("State", "billing_state"), ("ZIP", "billing_zip"),
        ("Parent ID", "parent_id"), ("Parent Name", "parent_name"),
        ("Status", "status"), ("Duplicate Of", "duplicate_of_account"),
        ("Lifetime Revenue", "lifetime_revenue"),
        ("Outstanding AR", "outstanding_ar"),
        ("CHOW Current Account", "chow_current_account"),
    )
    rows = []
    for label, field in fields:
        row = {"Field": label}
        for i, account in enumerate(candidates, start=1):
            row[f"Account {i}"] = str(account.get(field) if account.get(field) is not None else "Not provided")
        rows.append(row)
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.warning("Before approving: verify ownership history, CHOW links, and which account is the survivor. No automatic CRM update is performed here.")


def execute_approved_patch(token, proposal, union_confirmed=False):
    proposal_id = proposal["id"]
    account_id = proposal["account_id"]
    if is_union_square_proposal(proposal) and not union_confirmed:
        raise PermissionError("Explicit Union Square identity confirmation required.")
    if proposal["issue"] == "Possible Duplicate":
        raise ValueError(
            "Duplicate execution is temporarily blocked. "
            "Business confirmation and survivor validation "
            "are required before CRM changes."
        )

    record = get_decisions().get(proposal_id, {})

    if record.get("decision") != "Approved":
        raise PermissionError("Proposal is not approved.")

    if record.get("execution_status") == "Verified":
        return "Already verified. No action needed."

    payload = get_patch_payload(proposal)

    if payload is None:
        raise ValueError("No authorized PATCH payload.")

    def matches(account):
        return all(
            str(account.get(field)) == str(value)
            for field, value in payload.items()
        )

    current = get_account(token, account_id)

    validate_before_patch(proposal, current, payload)
    validate_parent_target(proposal, current, payload)
    if is_union_square_proposal(proposal):
        validate_union_square(proposal, current, payload)

    if matches(current):
        mark_execution(proposal_id, "Verified")
        return "CRM already contains expected values."

    try:
        update_account(
            token,
            account_id,
            payload,
            approved=True,
        )
    except Exception as patch_error:
        # The PATCH might have succeeded before
        # the network connection failed.
        try:
            updated = get_account(token, account_id)

            if matches(updated):
                mark_execution(proposal_id, "Verified")
                return (
                    "CRM update was applied and verified "
                    "after a network error."
                )
        except Exception:
            pass

        mark_execution(
            proposal_id,
            "Failed",
            str(patch_error),
        )
        raise

    try:
        updated = get_account(token, account_id)

        if matches(updated):
            mark_execution(proposal_id, "Verified")
            return "CRM updated and verified successfully."

        mark_execution(
            proposal_id,
            "Failed",
            "CRM values did not match expected values.",
        )
        raise ValueError("CRM verification failed.")

    except Exception as e:
        mark_execution(proposal_id, "Failed", str(e))
        raise



# New-account proposals require explicit approval, exact evidence and
# a single, deliberate execution action. Never auto-create on rerun.
ALLOWED_NEW_FACILITIES = {
    "Bellhaven of Batavia": ("2000 Hospital Dr", "Batavia", "OH", "45103"),
    "Bellhaven of Carlisle": ("640 Walnut Bottom Rd", "Carlisle", "PA", "17015"),
    "Amberly Manor": ("4390 Darrow Rd", "Hudson", "OH", "44236"),
}


def new_account_payload(proposal):
    if proposal.get("issue") != "Missing CRM Account":
        return None
    facility = proposal.get("facility")
    expected = ALLOWED_NEW_FACILITIES.get(facility)
    if not expected or proposal.get("account_id") not in (None, "", "New"):
        return None
    saved = get_saved_evidence(proposal["id"])
    if not saved:
        raise ValueError("Missing approved evidence snapshot; creation blocked.")
    proposed = saved["proposed"]
    payload = {
        "name": facility,
        "billing_street": expected[0],
        "billing_city": expected[1],
        "billing_state": expected[2],
        "billing_zip": expected[3],
        "parent_id": BELLHAVEN_PARENT_ID,
    }
    for field, value in payload.items():
        if str(proposed.get(field) or "").strip() != value:
            raise ValueError(f"Evidence mismatch for {field}; creation blocked.")
    return payload


def matching_accounts(accounts, payload):
    # An address match is a possible existing facility, even if renamed.
    keys = ("billing_street", "billing_city", "billing_state", "billing_zip")
    def norm(value):
        return re.sub(r"[^a-z0-9]", "", str(value or "").lower())
    return [a for a in accounts if all(
        norm(a.get(k)) == norm(payload[k]) for k in keys
    )]


def creation_receipt(proposal_id):
    with connect_db() as conn:
        rows = conn.execute(
            """SELECT event_details FROM audit_events
               WHERE proposal_id=? AND event_type='CRM Account Created'
               AND event_status='Success' ORDER BY event_id DESC""",
            (proposal_id,),
        ).fetchall()
    for (details,) in rows:
        try:
            account_id = json.loads(details).get("account_id")
            if account_id:
                return account_id
        except (ValueError, TypeError):
            pass
    return None


def execute_approved_create(token, proposal):
    pid = proposal["id"]
    record = get_decisions().get(pid, {})
    if record.get("decision") != "Approved":
        raise PermissionError("Proposal is not approved.")
    if record.get("execution_status") in ("Verified", "Applied"):
        return "Already executed; no additional account created."
    payload = new_account_payload(proposal)
    if payload is None:
        raise ValueError("New account creation is not authorized.")

    with connect_db() as conn:
        uncertain = conn.execute(
            """SELECT COUNT(*) FROM audit_events
               WHERE proposal_id=? AND event_type='CRM Creation Attempt'
               AND event_status='Uncertain'""", (pid,)
        ).fetchone()[0]
    if uncertain:
        raise ValueError("Earlier creation outcome uncertain. Manual reconciliation required; retry blocked.")

    prior_id = creation_receipt(pid)
    if prior_id:
        current = get_account(token, prior_id)
        if current.get("account_id") != prior_id:
            raise ValueError("Prior creation receipt could not be verified.")
        mark_execution(pid, "Verified")
        return f"Previously created account verified: {prior_id}"

    before = get_all_accounts(token)
    existing = matching_accounts(before, payload)
    if existing:
        ids = ", ".join(str(a.get("account_id")) for a in existing)
        raise ValueError(
            "An account already uses this facility address (" + ids + "). "
            "Creation blocked; review for duplicate or prior creation."
        )

    # If POST raises (including a timeout), do not automatically retry:
    # a server may have committed the creation before losing the response.
    try:
        created = create_account(token, payload, approved=True)
    except Exception as exc:
        with connect_db() as conn:
            write_audit_event(conn, pid, "CRM Creation Attempt", "Uncertain", {
                "reason": str(exc), "action": "Do not retry until reconciled"
            })
        raise RuntimeError(
            "Creation outcome uncertain. Do NOT click Execute again. "
            "Reconcile live CRM and audit history first."
        ) from exc

    # Record a receipt immediately after a successful response, before verification.
    result = created.get("data", created) if isinstance(created, dict) else {}
    if not isinstance(result, dict):
        result = {}
    new_id = result.get("account_id") or result.get("id")
    if not new_id:
        with connect_db() as conn:
            write_audit_event(conn, pid, "CRM Creation Attempt", "Uncertain", {
                "reason": "POST succeeded but no account ID in response",
                "response": str(created)[:500],
            })
        raise RuntimeError("CRM returned no account ID. Do NOT retry; reconcile first.")

    with connect_db() as conn:
        write_audit_event(conn, pid, "CRM Account Created", "Success", {
            "account_id": str(new_id), "facility": payload["name"]
        })

    current = get_account(token, str(new_id))
    for field, value in payload.items():
        if str(current.get(field) or "").strip() != value:
            raise ValueError(
                f"Created account {new_id}, but {field} verification failed. "
                "Do NOT retry; account creation is recorded in Audit History."
            )
    mark_execution(pid, "Verified")
    return f"CRM account created and verified: {new_id}"




init_db()
decisions = get_decisions()

st.set_page_config(
    page_title="Bellhaven CRM Review",
    page_icon="🏥",
    layout="wide",
)

st.title("Bellhaven CRM Data Quality Review")
st.caption("Clipboard Sales Operations Analyst Assessment")


total = len(PROPOSALS)

approved = sum(
    decisions.get(p["id"], {}).get("decision") == "Approved"
    for p in PROPOSALS
)

rejected = sum(
    decisions.get(p["id"], {}).get("decision") == "Rejected"
    for p in PROPOSALS
)

verified = sum(
    decisions.get(p["id"], {}).get("execution_status") == "Verified"
    for p in PROPOSALS
)

pending = total - approved - rejected


col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Proposals", total)
col2.metric("Pending", pending)
col3.metric("Approved", approved)
col4.metric("Rejected", rejected)

st.divider()

filter_option = st.selectbox(
    "Filter proposals",
    ["All", "Pending", "Approved", "Rejected"],
)

for proposal in PROPOSALS:
    record = decisions.get(proposal["id"], {})
    status = record.get("decision", "Pending")
    execution_status = record.get(
        "execution_status", "Not Applied"
    )


    if filter_option != "All" and status != filter_option:
        continue

    with st.expander(
        f"{proposal['facility']} | {proposal['issue']} | {status}",
        expanded=(status == "Pending"),
    ):
        st.write("**CRM Account ID:**", proposal["account_id"] or "New")
        st.write("**Issue:**", proposal["issue"])
        show_saved_evidence(proposal)
        st.write("**Proposed Action:**", proposal["action"])
        st.write("**Execution Status:**", execution_status)

        with st.expander("Audit History"):
            events = get_audit_events(proposal["id"])

            if events:
                st.dataframe(
                    events,
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.caption(
                    "No audit events recorded yet. "
                    "Earlier decisions predate audit logging."
                )


        

        if status == "Pending":
            survivor_id = None

            if proposal["issue"] == "Possible Duplicate":
                show_duplicate_comparison(proposal)
                st.warning(
                    "Same address does not prove duplication. "
                    "Confirm this is a true duplicate, not a "
                    "historical CHOW account, before approval."
                )
                survivor_id = st.text_input(
                    "Survivor Account ID",
                    key=f"survivor_{proposal['id']}",
                    placeholder="Enter the account ID to keep",
                ).strip()
                if survivor_id == proposal["account_id"]:
                    st.error("Survivor and duplicate cannot be the same account.")

            left, right = st.columns(2)
            with left:
                if st.button(
                    "Approve",
                    key=f"approve_{proposal['id']}",
                    type="primary",
                    disabled=(
                        proposal["issue"] == "Possible Duplicate"
                        and (
                            not survivor_id
                            or survivor_id == proposal["account_id"]
                        )
                    ),
                ):
                    save_decision(
                        proposal["id"],
                        "Approved",
                        survivor_account_id=survivor_id,
                    )
                    st.rerun()
            with right:
                if st.button(
                    "Reject",
                    key=f"reject_{proposal['id']}",
                ):
                    save_decision(proposal["id"], "Rejected")
                    st.rerun()

        else:
            st.info("This proposal has already been reviewed.")
            if status == "Approved":
                if execution_status == "Verified":
                    st.success(
                        "CRM change already verified. "
                        "No further action required."
                    )
                elif (get_patch_payload(proposal) is not None
                      or proposal["issue"] == "Missing CRM Account"):
                    token = st.text_input(
                        "CRM API Token",
                        type="password",
                        key=f"token_{proposal['id']}",
                    )
                    union_confirmed = True
                    if is_union_square_proposal(proposal):
                        st.warning(
                            "Union Square: website address (118 Union Square Dr) differs "
                            "materially from CRM (240 Market St). Matching score is "
                            "84.4. Confirm this is the SAME legal facility before any "
                            "CRM update. Approval alone does not establish identity."
                        )
                        st.write("**Exact proposed PATCH:**", get_patch_payload(proposal))
                        union_confirmed = st.checkbox(
                            "I independently verified this CRM account represents "
                            "the website facility, and authorize this specific change.",
                            key=f"confirm_union_{proposal['id']}",
                        )
                    if st.button(
                        "Execute Approved CRM Update" if proposal["issue"] != "Missing CRM Account"
                        else "Create Approved CRM Account",
                        key=f"execute_{proposal['id']}",
                        disabled=not token or not union_confirmed,
                    ):
                        try:
                            result = (execute_approved_create(token, proposal)
                                       if proposal["issue"] == "Missing CRM Account"
                                       else execute_approved_patch(token, proposal, union_confirmed=union_confirmed))
                            st.success(result)
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
                else:
                    st.warning(
                        "This proposal requires additional "
                        "review or an execution plan."
                    )


st.divider()
st.info(
    "Review decisions and evidence are stored locally. "
    "CRM changes are executed only after approval "
    "and an explicit execution action."
)
