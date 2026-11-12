
# Bellhaven Senior Living — CRM Data Hygiene

Clipboard Sales Operations Analyst Take-Home Assessment

## Project Overview

This project implements a CRM data hygiene workflow for Bellhaven Senior Living, a fictional long-term care facility operator.

The system compares facility locations from the operator's website against CRM accounts, identifies potential data quality issues, and provides a human review interface for approving or rejecting proposed changes.

Approved changes can be written back to the CRM through its API.

## Key Features

- Scrape facility information from the Bellhaven website
- Match website locations to CRM accounts
- Detect incorrect parent relationships
- Identify outdated facility names and address discrepancies
- Identify missing CRM accounts and possible duplicates
- Apply billing-aware change-of-ownership (CHOW) rules
- Review proposed changes through a Streamlit application
- Execute approved CRM updates
- Preserve review decisions across daily runs
- Prevent duplicate proposals during repeated pipeline execution

## Technology Stack

- Python 3
- Streamlit
- Requests
- Beautiful Soup
- RapidFuzz
- SQLite
- CRM REST API

## Project Structure

Core files:

- `scraper.py` — Website location scraper
- `bellhaven_locations.csv` — Scraped facility dataset
- `crm_client.py` — CRM API client
- `crm_writer.py` — CRM update and creation helpers
- `matcher.py` — Matching utilities
- `proposal_generator.py` — Proposal generation and classification
- `review_app.py` — Human review interface
- `daily_run.py` — Safe daily proposal reconciliation
- `proposal_history.py` — Review history helpers
- `proposal_merge.py` — Proposal reconciliation helpers
- `proposal_storage.py` — Safe proposal storage
- `proposal_sync.py` — Pending proposal synchronization

## Installation

Clone the repository:

    git clone <REPOSITORY_URL>
    cd clipboard-assessment

Create a Python virtual environment:

    python3 -m venv .venv
    source .venv/bin/activate

Install dependencies:

    python3 -m pip install -r requirements.txt

## CRM Authentication

The pipeline requires a CRM API token.

Set the token using an environment variable:

    export CRM_API_TOKEN="YOUR_CRM_API_TOKEN"

Do not commit API tokens or credential files to GitHub.

## Scraping

Run the scraper:

    python3 scraper.py

The scraped location dataset is stored in:

    bellhaven_locations.csv

## Matching and Proposal Generation

The matching workflow compares website facility records with CRM accounts using normalized names and addresses.

Potential discrepancies include:

- Wrong Parent
- Outdated Name
- Address Mismatch
- Missing CRM Account
- Missing from Website
- Possible Duplicate
- CHOW Required

Proposals include supporting evidence and recommended actions for reviewer evaluation.

## Billing-Aware CHOW Logic

When an existing CRM account needs to move to a different parent, the pipeline checks:

- `lifetime_revenue`
- `outstanding_ar`

If both values are greater than zero, the original account must be preserved.

The proposed workflow is:

1. Leave the existing account and parent unchanged.
2. Create a new account under the correct parent.
3. Set `chow_current_account` on the old account to the new account ID.

If the account has no revenue history or no outstanding AR, the existing account can be re-parented directly.

Possible duplicates are reviewed separately from CHOW cases.

## Human Review Application

Start the Streamlit application:

    python3 -m streamlit run review_app.py

Open the local URL displayed in the terminal, typically:

    http://localhost:8501

The reviewer can inspect proposals, review supporting evidence, and approve or reject proposed changes.

CRM write-back is a separate action and is intended to occur only after approval.

## Daily Pipeline

Run a safe dry run:

    python3 daily_run.py

Apply new proposals:

    python3 daily_run.py --apply

The pipeline:

1. Fetches current CRM account data.
2. Generates proposals into a temporary file.
3. Reads previously recorded review decisions.
4. Skips proposals already approved or rejected.
5. Preserves existing proposals.
6. Adds only new, undecided proposal IDs.
7. Saves updates atomically when `--apply` is supplied.

Daily execution does not automatically modify CRM accounts.

A sample cron configuration is provided in:

    daily_run_cron.example

## Idempotency Verification

The daily pipeline was tested with consecutive applied runs.

First applied run:

- Existing proposals: 34
- Incoming proposals: 16
- New proposals: 2
- Merged proposals: 36
- Previously reviewed proposals skipped: 12

Second applied run:

- Existing proposals: 36
- Incoming proposals: 16
- New proposals: 0
- Merged proposals: 36
- Previously reviewed proposals skipped: 12

The second applied run produced no duplicate proposals and did not modify CRM accounts or review decisions.

## Data Safety

- CRM credentials are excluded from version control.
- Local review databases and backups are excluded.
- Proposal generation does not automatically write to CRM.
- Previously reviewed proposals are preserved.
- Potential duplicates require human review.
- CHOW actions preserve historical accounts when required by billing rules.

## Future Improvements

- Improve entity resolution using historical ownership information
- Expand automated tests for CHOW and duplicate scenarios
- Add monitoring and alerting for scheduled runs
- Improve audit logging and error recovery
- Expand CRM write-back coverage
