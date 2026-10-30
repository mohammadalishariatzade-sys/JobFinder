# 24/7 Remote Job Hunter Bot

Automated Python bot that parses `resume.json`, fetches remote jobs from public APIs & RSS feeds, evaluates job descriptions against your engineering skills, prints console alerts, and logs jobs with a **match score >= 85%** into `jobs_history.csv` while preventing duplicates.

---

## 🚀 Features

- **Automated Resume Matching**: Dynamically extracts key skills, software/tools, and domain keywords from `resume.json` (Industrial Automation, PLC, SCADA, Control Systems, Python, Industrial Networks, etc.).
- **Multiple Remote Job Sources**:
  - **RemoteOK API** (`https://remoteok.com/api`)
  - **Jobicy API** (`https://jobicy.com/api/v2/remote-jobs`)
  - **Arbeitnow API** (`https://www.arbeitnow.com/api/job-board-api`)
  - **WeWorkRemotely RSS** (`https://weworkremotely.com/remote-jobs.rss`)
- **Intelligent Evaluation Engine**:
  - Role & title relevance analysis (Max 35 pts)
  - Technical skills & software keyword matching with tiered weighting (Max 55 pts)
  - Engineering domain & remote alignment bonus (Max 10 pts)
  - Negative keyword filtering (prevents non-engineering roles)
- **Duplicate Prevention & Logging**:
  - Automatically maintains `jobs_history.csv` with job IDs, timestamps, company, score, and application links.
  - Skips already evaluated or logged jobs across runs.
- **24/7 Daemon Mode**: Runs in the background with customizable intervals (default: 30 minutes) and graceful shutdown (`Ctrl+C`).
- **Zero-Dependency Fallback**: Works with standard Python libraries (`urllib`) even if external libraries are not yet installed, though `requests` and `colorama` provide enhanced features and styling.

---

## 📦 Quick Installation

Install recommended dependencies:

```bash
pip install -r requirements.txt
```

---

## 💻 How to Run

### 1. Run 24/7 Continuous Monitoring (Default)
Runs scans automatically every 30 minutes:
```bash
python main.py
```

To set a custom interval (e.g. check every 15 minutes):
```bash
python main.py --interval 15
```

### 2. Run a Single Scan Cycle (`--once`)
Runs one scan across all remote sources, prints matching jobs, logs them to `jobs_history.csv`, and exits:
```bash
python main.py --once
```

### 3. Customize Minimum Match Score
Default threshold is 85%. You can adjust it via `--min-score`:
```bash
python main.py --once --min-score 80
```

### 4. Verify Resume Parsing
Inspect the extracted skills and weights directly from your `resume.json`:
```bash
python main.py --test-resume
```

---

## 📊 Output Files

- `jobs_history.csv`: Contains all jobs scoring above the threshold with columns:
  - `job_id`: Unique identifier across job boards
  - `timestamp`: Date and time when the match was discovered
  - `title`: Job title
  - `company`: Employer / Company name
  - `match_score`: Percentage score (e.g., `88.5%`)
  - `url`: Direct application link
  - `source`: Job provider (RemoteOK, Jobicy, Arbeitnow, etc.)
  - `location`: Remote eligibility / Region
  - `matched_skills`: List of matched keywords that contributed to the score
