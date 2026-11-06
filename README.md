# 24/7 Remote Job Hunter Bot

Automated Python bot that parses `resume.json`, fetches remote jobs from public APIs & RSS feeds, evaluates job descriptions against your engineering skills, prints console alerts, and logs jobs with a **match score >= 50%** into `jobs_history.csv` while preventing duplicates and sending instant push notifications to Telegram.

---

## 🚀 Features

- **Automated Resume Matching**: Dynamically extracts key skills, software/tools, and domain keywords from `resume.json` (Industrial Automation, PLC, SCADA, Control Systems, Python, Industrial Networks, etc.).
- **Multiple Remote Job Sources**:
  - RemoteOK API (`https://remoteok.com/api`)
  - Jobicy API (`https://jobicy.com/api/v2/remote-jobs`)
  - Arbeitnow API (`https://www.arbeitnow.com/api/job-board-api`)
  - WeWorkRemotely RSS (`https://weworkremotely.com/remote-jobs.rss`)
- **Intelligent Evaluation Engine**:
  - Role & title relevance analysis with primary engineering title weighting (Max 35 pts)
  - Core Technical Anchors (PLC, SCADA, Electrical, Control Systems, Instrumentation, Hardware, Embedded, Python, etc.)
  - Negative keyword filtering (strictly excludes accounting, sales, marketing, HR, etc.)
- **Telegram Push Notifications**:
  - Instant HTML formatted alerts delivered to your Telegram app.
  - Test command (`python main.py --test-telegram`) to verify connection anytime.
- **Duplicate Prevention & Logging**:
  - Automatically maintains `jobs_history.csv` with job IDs, timestamps, company, score, and application links.
  - Skips already evaluated or logged jobs across runs.
- **24/7 Daemon Mode**: Runs in the background with customizable intervals (default: 30 minutes) and graceful shutdown (`Ctrl+C`).

---

## 💻 How to Run

1. **Test Telegram Connectivity**:
```bash
python main.py --test-telegram
```

2. **Run a Single Scan**:
```bash
python main.py --once
```

3. **Start 24/7 Monitoring (Double-click `run.bat` or run)**:
```bash
python main.py
```
