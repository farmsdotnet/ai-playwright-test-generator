#!/usr/bin/env python3
"""
job_alert.py — polls the Reed.co.uk job search API for jobs matching a
title/location/contract-type filter, and emails you when a NEW listing
(one not seen on a previous run) shows up.

This script does one pass and exits. Schedule it to run periodically
(e.g. every 30-60 minutes) via cron / Task Scheduler — see README.md.

Config lives in config.json next to this file. seen_jobs.json (created
automatically) tracks which job IDs have already been alerted on, so
you don't get repeat emails for the same posting.
"""

import json
import smtplib
import sys
from email.mime.text import MIMEText
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
SEEN_PATH = BASE_DIR / "seen_jobs.json"

REED_SEARCH_URL = "https://www.reed.co.uk/api/1.0/search"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        sys.exit(f"Missing {CONFIG_PATH}. Copy config.example.json to config.json and fill it in.")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_seen_ids() -> set:
    if not SEEN_PATH.exists():
        return set()
    with open(SEEN_PATH, "r", encoding="utf-8") as f:
        return set(json.load(f))


def save_seen_ids(ids: set) -> None:
    with open(SEEN_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(ids), f, indent=2)


def fetch_jobs(config: dict) -> list:
    params = {
        "keywords": config["job_title"],
        "locationName": config["location"],
        "distanceFromLocation": config.get("distance_miles", 10),
        "resultsToTake": 100,
    }

    contract_type = config.get("contract_type", "both").lower()
    if contract_type == "permanent":
        params["permanent"] = "true"
    elif contract_type == "contract":
        params["contract"] = "true"
    # "both" -> leave both filters unset so the API returns either

    response = requests.get(
        REED_SEARCH_URL,
        params=params,
        auth=(config["reed_api_key"], ""),  # API key as username, blank password
        timeout=30,
    )
    response.raise_for_status()
    return response.json().get("results", [])


def filter_by_employer(jobs: list, employer_names: list) -> list:
    """Reed's search API only supports filtering by employer ID, not name,
    so this filters client-side. Case-insensitive substring match, so
    "Google" in config will match "Google UK Ltd" in the results."""
    if not employer_names:
        return jobs
    wanted = [name.lower() for name in employer_names]
    return [
        job for job in jobs
        if any(name in job.get("employerName", "").lower() for name in wanted)
    ]


def format_job_line(job: dict) -> str:
    title = job.get("jobTitle", "Untitled role")
    employer = job.get("employerName", "Unknown employer")
    location = job.get("locationName", "")
    min_sal = job.get("minimumSalary")
    max_sal = job.get("maximumSalary")
    salary = ""
    if min_sal and max_sal:
        salary = f" | £{min_sal:,.0f}–£{max_sal:,.0f}"
    url = job.get("jobUrl", "")
    return f"- {title} @ {employer} ({location}){salary}\n  {url}"


def send_email(config: dict, new_jobs: list) -> None:
    smtp_cfg = config["smtp"]
    subject = f"{len(new_jobs)} new job posting(s): {config['job_title']} in {config['location']}"
    body = "\n\n".join(format_job_line(job) for job in new_jobs)

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = smtp_cfg["sender_email"]
    msg["To"] = config["recipient_email"]

    with smtplib.SMTP(smtp_cfg["server"], smtp_cfg["port"]) as server:
        server.starttls()
        server.login(smtp_cfg["sender_email"], smtp_cfg["sender_password"])
        server.send_message(msg)


def main():
    config = load_config()
    seen_ids = load_seen_ids()

    jobs = fetch_jobs(config)
    jobs = filter_by_employer(jobs, config.get("employer_names", []))
    current_ids = {job["jobId"] for job in jobs}

    first_run = SEEN_PATH.exists() is False
    new_jobs = [job for job in jobs if job["jobId"] not in seen_ids]

    save_seen_ids(current_ids | seen_ids)

    if first_run:
        # Don't blast an email with every existing match on the very first
        # run — just establish the baseline of what's already out there.
        print(f"First run: recorded {len(current_ids)} existing job(s) as a baseline. No email sent.")
        return

    if new_jobs:
        send_email(config, new_jobs)
        print(f"Sent alert for {len(new_jobs)} new job(s).")
    else:
        print("No new jobs since last run.")


if __name__ == "__main__":
    main()