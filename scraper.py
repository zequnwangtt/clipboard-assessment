
import csv
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

BASE_URL = "https://analyst-assessment-production.up.railway.app"
START_URL = f"{BASE_URL}/communities"

session = requests.Session()


def get_soup(url):
    response = session.get(url, timeout=20)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def get_community_links():
    links = {}
    visited_pages = set()
    next_url = START_URL

    while next_url and next_url not in visited_pages:
        visited_pages.add(next_url)
        print(f"Reading directory: {next_url}")

        soup = get_soup(next_url)

        for link in soup.find_all("a", href=True):
            full_url = urljoin(next_url, link["href"])
            path = urlparse(full_url).path

            if path.startswith("/communities/"):
                name = link.get_text(" ", strip=True)
                if name:
                    links[full_url] = name

        next_url = None

        for link in soup.find_all("a", href=True):
            label = link.get_text(" ", strip=True).lower()
            if label.startswith("next"):
                next_url = urljoin(
                    START_URL, link["href"]
                )
                break

    return links


def get_field(lines, label):
    for index, line in enumerate(lines):
        if line.lower() == label.lower():
            if index + 1 < len(lines):
                return lines[index + 1]
    return ""


def parse_location(url):
    soup = get_soup(url)

    heading = soup.find("h1")
    name = heading.get_text(" ", strip=True) if heading else ""

    lines = list(soup.stripped_strings)

    street = get_field(lines, "Address")
    city_state_zip = ""

    if street in lines:
        index = lines.index(street)
        if index + 1 < len(lines):
            city_state_zip = lines[index + 1]

    match = re.match(
        r"(.+?),\s*([A-Z]{2})\s+(\d{5})(?:-\d{4})?$",
        city_state_zip
    )

    city = match.group(1) if match else ""
    state = match.group(2) if match else ""
    zip_code = match.group(3) if match else ""

    care = get_field(lines, "Care Offerings")
    administrator = get_field(lines, "Administrator")
    phone = get_field(lines, "Phone")

    return {
        "name": name,
        "street": street,
        "city": city,
        "state": state,
        "zip": zip_code,
        "care_offerings": care,
        "administrator": administrator,
        "phone": phone,
        "source_url": url,
    }


def main():
    links = get_community_links()

    print(f"\nFound {len(links)} community links.\n")

    locations = []

    for index, url in enumerate(links, start=1):
        print(f"[{index}/{len(links)}] Reading {links[url]}")
        location = parse_location(url)
        locations.append(location)

    fields = [
        "name",
        "street",
        "city",
        "state",
        "zip",
        "care_offerings",
        "administrator",
        "phone",
        "source_url",
    ]

    with open(
        "bellhaven_locations.csv",
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(locations)

    print("\nScraping complete!")
    print(f"Total locations: {len(locations)}")
    print("Saved to bellhaven_locations.csv")

    missing = [
        loc["name"]
        for loc in locations
        if not all(
            loc[field]
            for field in (
                "name", "street", "city",
                "state", "zip", "care_offerings"
            )
        )
    ]

    if missing:
        print("\nWARNING: Incomplete records:")
        for name in missing:
            print("-", name)
    else:
        print("All required fields populated.")


if __name__ == "__main__":
    main()


