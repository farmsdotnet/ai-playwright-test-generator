# LinkedIn-alternative Job Alert (via Reed API)

LinkedIn doesn't offer a public API for this, so this uses **Reed.co.uk**'s
free jobseeker API instead — a large UK job board that supports exactly
the filters you wanted (title, location, permanent vs. contract).

## 1. Get a free Reed API key
1. Go to https://www.reed.co.uk/developers/jobseeker
2. Register and copy your API key.

## 2. Set up the config
1. Copy `config.example.json` to `config.json` (same folder as `job_alert.py`).
2. Fill in:
   - `reed_api_key` — from step 1
   - `job_title` — e.g. `"QA Automation Engineer"`
   - `location` — e.g. `"Birmingham"`
   - `distance_miles` — search radius around that location
   - `contract_type` — `"permanent"`, `"contract"`, or `"both"`
   - `employer_names` — optional list of employers to restrict alerts to, e.g.
     `["IQGeo", "Deutsche Bahn"]`. Leave as `[]` to get alerts from any
     employer. Matching is case-insensitive and matches on partial name
     (e.g. `"Google"` will match `"Google UK Ltd"`), since Reed's own API
     only supports filtering by employer ID, not name.
   - `recipient_email` — where alerts get sent (already set to prince7t9@gmail.com)
   - `smtp` — the account the alert will be *sent from*. For Gmail:
     - `sender_email`: a Gmail address you control
     - `sender_password`: a **Gmail App Password** (not your normal password) —
       create one at https://myaccount.google.com/apppasswords (requires
       2-Step Verification to be turned on)

## 3. Install dependencies
```bash
pip install requests
```

## 4. Run it
```bash
python job_alert.py
```
- **First run** just records what's currently out there as a baseline — no
  email (otherwise you'd get blasted with every existing match).
- **Every run after that** emails you only the jobs that are new since last time.

## 5. Schedule it (so it actually runs automatically)
Add a cron job (macOS/Linux) to run it, e.g. every 30 minutes:
```bash
crontab -e
# add this line:
*/30 * * * * cd /path/to/this/folder && /usr/bin/python3 job_alert.py >> job_alert.log 2>&1
```
On Windows, use Task Scheduler with a trigger of "every 30 minutes" running
`python job_alert.py` with the working directory set to this folder.

## Notes
- To change what you're searching for later, just edit `config.json` —
  no code changes needed.
- `seen_jobs.json` is created automatically to track which listings you've
  already been alerted on. Delete it if you ever want to reset the baseline.
- Reed's free tier is generous for this kind of low-frequency polling, but
  don't set the schedule to run every few seconds.