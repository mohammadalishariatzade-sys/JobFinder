#!/usr/bin/env python3
"""
24/7 Remote Job Hunter Bot
==========================
Automated remote job hunter that:
1. Loads candidate profile and skills from `resume.json`.
2. Fetches fresh remote job postings from multiple public APIs & RSS feeds (RemoteOK, Jobicy, Arbeitnow, WeWorkRemotely).
3. Evaluates and scores job requirements against candidate skills.
4. Logs jobs scoring above 85% into `jobs_history.csv` to prevent duplicates.
5. Sends instant push alerts directly to your phone via Telegram.
6. Runs continuously 24/7 or as a one-shot scanner.
"""

import os
import sys
import json
import csv
import re
import time
import argparse
from datetime import datetime
from typing import Dict, List, Set, Tuple, Optional, Any
import xml.etree.ElementTree as ET

# Attempt importing requests, fall back to urllib if not installed yet
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    import urllib.request
    import urllib.error
    HAS_REQUESTS = False

# Attempt importing colorama for colored terminal output on Windows/Unix
try:
    from colorama import init as colorama_init, Fore, Style
    colorama_init(autoreset=True)
    HAS_COLORAMA = True
except ImportError:
    HAS_COLORAMA = False

# Telegram configuration supporting environment variables (GitHub Actions) with fallbacks
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "9215545350:AAFLFWAak5YkGnLyi03yFV18KJmvBVlTDtg")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "118524058")

def send_telegram_alert(job: Any, score: float, matched_skills: List[str]) -> None:
    """Sends a formatted push notification to Telegram when a high match is found."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    top_skills = ", ".join(matched_skills[:8])
    message = (
        f"🎯 *HIGH JOB MATCH FOUND ({score:.1f}%)*\n\n"
        f"📌 *Title:* {job.title}\n"
        f"🏢 *Company:* {job.company or 'Confidential'}\n"
        f"🌐 *Source:* {job.source} ({job.location})\n"
        f"🔗 [Apply Here]({job.url})\n"
        f"🛠 *Matched Skills:* {top_skills}"
    )
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }

    if HAS_REQUESTS:
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"Failed to send Telegram alert: {e}")
    else:
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=10)
        except Exception as e:
            print(f"Failed to send Telegram alert via urllib: {e}")


# Console styling helpers
class UI:
    RESET = "\033[0m" if not HAS_COLORAMA else Style.RESET_ALL
    BOLD = "\033[1m" if not HAS_COLORAMA else Style.BRIGHT
    DIM = "\033[2m" if not HAS_COLORAMA else Style.DIM
    GREEN = "\033[32m" if not HAS_COLORAMA else Fore.GREEN
    CYAN = "\033[36m" if not HAS_COLORAMA else Fore.CYAN
    YELLOW = "\033[33m" if not HAS_COLORAMA else Fore.YELLOW
    RED = "\033[31m" if not HAS_COLORAMA else Fore.RED
    MAGENTA = "\033[35m" if not HAS_COLORAMA else Fore.MAGENTA
    BLUE = "\033[34m" if not HAS_COLORAMA else Fore.BLUE

    @classmethod
    def header(cls, text: str) -> None:
        print(f"\n{cls.BOLD}{cls.CYAN}{'=' * 70}{cls.RESET}")
        print(f"{cls.BOLD}{cls.CYAN} {text}{cls.RESET}")
        print(f"{cls.BOLD}{cls.CYAN}{'=' * 70}{cls.RESET}")

    @classmethod
    def success(cls, text: str) -> None:
        print(f"{cls.GREEN}[+] {text}{cls.RESET}")

    @classmethod
    def info(cls, text: str) -> None:
        print(f"{cls.CYAN}[*] {text}{cls.RESET}")

    @classmethod
    def warning(cls, text: str) -> None:
        print(f"{cls.YELLOW}[!] {text}{cls.RESET}")

    @classmethod
    def error(cls, text: str) -> None:
        print(f"{cls.RED}[-] {text}{cls.RESET}")


# Data Model for a Job Posting
class JobPosting:
    def __init__(
        self,
        job_id: str,
        title: str,
        company: str,
        url: str,
        description: str,
        tags: List[str],
        source: str,
        location: str = "Remote",
        published_at: str = ""
    ):
        self.job_id = str(job_id).strip()
        self.title = title.strip()
        self.company = company.strip()
        self.url = url.strip()
        self.description = description.strip()
        self.tags = [t.strip().lower() for t in tags if t.strip()]
        self.source = source
        self.location = location.strip() or "Remote"
        self.published_at = published_at.strip() or datetime.now().strftime("%Y-%m-%d")

    def get_searchable_text(self) -> str:
        """Combine all textual fields for matching."""
        return f"{self.title} {' '.join(self.tags)} {self.description}".lower()


# Candidate Profile Evaluator
class CandidateProfile:
    def __init__(self, resume_path: str = "resume.json"):
        self.resume_path = resume_path
        self.raw_data: Dict[str, Any] = {}
        self.name: str = ""
        self.key_skills: List[str] = []
        self.tools: List[str] = []
        self.roles: List[str] = []
        self.weighted_keywords: Dict[str, float] = {}
        self.role_keywords: Set[str] = set()
        self.load_resume()

    def load_resume(self) -> None:
        """Loads and parses resume.json into categorized, weighted keywords."""
        if not os.path.exists(self.resume_path):
            raise FileNotFoundError(f"Resume file not found at: {self.resume_path}")

        with open(self.resume_path, "r", encoding="utf-8") as f:
            self.raw_data = json.load(f)

        personal = self.raw_data.get("personal_info", {})
        self.name = personal.get("name", "Candidate")
        self.key_skills = self.raw_data.get("key_skills", [])
        self.tools = self.raw_data.get("software_and_tools", [])
        experience = self.raw_data.get("professional_experience", [])
        self.roles = [exp.get("role", "") for exp in experience if "role" in exp]

        self._build_keyword_dictionary()

    def _build_keyword_dictionary(self) -> None:
        """
        Extracts phrases and single words, categorizing by weight:
        - Core Engineering & Automation (Weight 3.5)
        - Specific Platforms & Industrial Networks (Weight 3.0)
        - Software & Programming (Weight 2.5)
        - Secondary & Methodological Tools (Weight 1.5)
        """
        self.role_keywords = {
            "automation", "control", "electrical", "instrumentation", "scada", "plc",
            "commissioning", "systems engineer", "python", "industrial", "robotics",
            "mechatronics", "hardware", "firmware", "iot", "maintenance"
        }

        tier_1 = [
            "industrial automation", "plc", "scada", "tia portal", "simatic manager",
            "wincc", "modbus", "profinet", "profibus", "control systems", "pid",
            "electrical engineer", "instrumentation", "commissioning", "python"
        ]
        for kw in tier_1:
            self.weighted_keywords[kw.lower()] = 3.5

        tier_2 = [
            "siemens", "mitsubishi", "omron", "keyence", "cc-link", "ethernet",
            "hmi", "fuzzy control", "motion control", "servo", "stepper", "drives",
            "pneumatic", "hydraulic", "autocad", "factory i/o", "sensors",
            "power systems", "switchgear", "transformers", "submittal review"
        ]
        for kw in tier_2:
            self.weighted_keywords[kw.lower()] = 2.8

        tier_3 = [
            "gx developer", "gx works", "cx one", "nb designer", "weintek",
            "easy builder", "lenze", "fluidsim", "navis", "excel", "pm", "cm",
            "mttr", "mtbf", "project management", "technical reporting"
        ]
        for kw in tier_3:
            self.weighted_keywords[kw.lower()] = 1.8

        for skill in self.key_skills:
            clean_phrase = re.sub(r"[^\w\s-]", " ", skill.lower())
            for sub in clean_phrase.split():
                if len(sub) > 2 and sub not in self.weighted_keywords:
                    self.weighted_keywords[sub] = 1.5

        for tool in self.tools:
            tool_clean = tool.strip().lower()
            if tool_clean not in self.weighted_keywords:
                self.weighted_keywords[tool_clean] = 2.0

    def evaluate_job(self, job: JobPosting) -> Tuple[float, List[str], Dict[str, Any]]:
        """Evaluates a job posting against candidate's profile."""
        title_lower = job.title.lower()
        search_text = job.get_searchable_text()

        title_score = 0.0
        title_matches = []
        for rkw in self.role_keywords:
            if re.search(r"\b" + re.escape(rkw) + r"\b", title_lower):
                title_matches.append(rkw)
                title_score += 12.0

        title_score = min(title_score, 35.0)

        matched_kws = []
        accumulated_skill_score = 0.0
        max_possible_skill_weight = 40.0

        for kw, weight in self.weighted_keywords.items():
            pattern = r"\b" + re.escape(kw) + r"\b"
            if re.search(pattern, search_text):
                matched_kws.append(kw)
                accumulated_skill_score += weight

        skill_score = min((accumulated_skill_score / max_possible_skill_weight) * 55.0, 55.0)

        domain_score = 0.0
        domain_terms = ["engineering", "automation", "manufacturing", "hardware", "energy", "industrial", "remote"]
        for dt in domain_terms:
            if dt in job.tags or dt in title_lower:
                domain_score += 3.0
        domain_score = min(domain_score, 10.0)

        total_score = title_score + skill_score + domain_score

        conflicting_titles = ["nurse", "sales executive", "marketing lead", "financial accountant", "copywriter", "ui/ux designer"]
        for neg in conflicting_titles:
            if neg in title_lower:
                total_score = max(0.0, total_score - 50.0)

        final_score = round(min(max(total_score, 0.0), 100.0), 1)

        sorted_matched = sorted(
            list(set(matched_kws + title_matches)),
            key=lambda k: self.weighted_keywords.get(k, 1.0),
            reverse=True
        )

        details = {
            "title_score": round(title_score, 1),
            "skill_score": round(skill_score, 1),
            "domain_score": round(domain_score, 1),
            "matched_count": len(sorted_matched),
        }

        return final_score, sorted_matched, details


# Job Fetcher supporting multiple public remote feeds
class JobFetcher:
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 RemoteJobHunter/1.0"

    @classmethod
    def _fetch_url(cls, url: str, timeout: int = 15) -> Optional[str]:
        headers = {"User-Agent": cls.USER_AGENT, "Accept": "application/json, text/xml, */*"}
        if HAS_REQUESTS:
            try:
                resp = requests.get(url, headers=headers, timeout=timeout)
                if resp.status_code == 200:
                    return resp.text
                else:
                    UI.warning(f"Fetch {url} returned HTTP {resp.status_code}")
                    return None
            except Exception as e:
                UI.warning(f"Request failed for {url}: {e}")
                return None
        else:
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    return response.read().decode("utf-8", errors="ignore")
            except Exception as e:
                UI.warning(f"urllib request failed for {url}: {e}")
                return None

    @classmethod
    def fetch_remoteok(cls) -> List[JobPosting]:
        url = "https://remoteok.com/api"
        UI.info("Scanning RemoteOK API...")
        jobs = []
        raw = cls._fetch_url(url)
        if not raw:
            return jobs

        try:
            data = json.loads(raw)
            items = data[1:] if isinstance(data, list) and len(data) > 1 else []
            for item in items:
                if not isinstance(item, dict):
                    continue
                job_id = f"remoteok_{item.get('id', item.get('slug', ''))}"
                title = item.get("position", "")
                company = item.get("company", "")
                url_link = item.get("url") or item.get("apply_url") or f"https://remoteok.com/remote-jobs/{item.get('id')}"
                description = item.get("description", "")
                tags = item.get("tags", [])
                location = item.get("location", "Remote")
                date = item.get("date", "")
                if title:
                    jobs.append(JobPosting(job_id, title, company, url_link, description, tags, "RemoteOK", location, date))
        except Exception as e:
            UI.warning(f"Error parsing RemoteOK response: {e}")

        UI.success(f"Fetched {len(jobs)} jobs from RemoteOK")
        return jobs

    @classmethod
    def fetch_jobicy(cls) -> List[JobPosting]:
        url = "https://jobicy.com/api/v2/remote-jobs"
        UI.info("Scanning Jobicy API...")
        jobs = []
        raw = cls._fetch_url(url)
        if not raw:
            return jobs

        try:
            data = json.loads(raw)
            items = data.get("jobs", [])
            for item in items:
                job_id = f"jobicy_{item.get('id', '')}"
                title = item.get("jobTitle", "")
                company = item.get("companyName", "")
                url_link = item.get("url", "")
                description = item.get("jobDescription", "")
                tags = []
                if "jobIndustry" in item and item["jobIndustry"]:
                    tags.extend(str(item["jobIndustry"]).split(","))
                location = item.get("jobGeo", "Remote")
                date = item.get("pubDate", "")
                if title:
                    jobs.append(JobPosting(job_id, title, company, url_link, description, tags, "Jobicy", location, date))
        except Exception as e:
            UI.warning(f"Error parsing Jobicy response: {e}")

        UI.success(f"Fetched {len(jobs)} jobs from Jobicy")
        return jobs

    @classmethod
    def fetch_arbeitnow(cls) -> List[JobPosting]:
        url = "https://www.arbeitnow.com/api/job-board-api"
        UI.info("Scanning Arbeitnow API...")
        jobs = []
        raw = cls._fetch_url(url)
        if not raw:
            return jobs

        try:
            data = json.loads(raw)
            items = data.get("data", [])
            for item in items:
                job_id = f"arbeitnow_{item.get('slug', item.get('id', ''))}"
                title = item.get("title", "")
                company = item.get("company_name", "")
                url_link = item.get("url", "")
                description = item.get("description", "")
                tags = item.get("tags", [])
                location = item.get("location", "Remote")
                date = item.get("created_at", "")
                if title:
                    jobs.append(JobPosting(job_id, title, company, url_link, description, tags, "Arbeitnow", location, str(date)))
        except Exception as e:
            UI.warning(f"Error parsing Arbeitnow response: {e}")

        UI.success(f"Fetched {len(jobs)} jobs from Arbeitnow")
        return jobs

    @classmethod
    def fetch_weworkremotely(cls) -> List[JobPosting]:
        url = "https://weworkremotely.com/remote-jobs.rss"
        UI.info("Scanning WeWorkRemotely RSS Feed...")
        jobs = []
        raw = cls._fetch_url(url)
        if not raw:
            return jobs

        try:
            root = ET.fromstring(raw)
            for item in root.findall("./channel/item"):
                title_elem = item.find("title")
                link_elem = item.find("link")
                desc_elem = item.find("description")
                guid_elem = item.find("guid")
                pub_date = item.find("pubDate")

                raw_title = title_elem.text if title_elem is not None else ""
                url_link = link_elem.text if link_elem is not None else ""
                description = desc_elem.text if desc_elem is not None else ""
                guid = guid_elem.text if guid_elem is not None else url_link
                date = pub_date.text if pub_date is not None else ""

                company = ""
                title = raw_title
                if ":" in raw_title:
                    parts = raw_title.split(":", 1)
                    company = parts[0].strip()
                    title = parts[1].strip()

                job_id = f"wwr_{guid.split('/')[-1] if guid else abs(hash(url_link))}"
                if title:
                    jobs.append(JobPosting(job_id, title, company, url_link, description, [], "WeWorkRemotely", "Remote", date))
        except Exception as e:
            UI.warning(f"Error parsing WeWorkRemotely RSS: {e}")

        UI.success(f"Fetched {len(jobs)} jobs from WeWorkRemotely")
        return jobs

    @classmethod
    def fetch_all(cls) -> List[JobPosting]:
        all_jobs: List[JobPosting] = []
        all_jobs.extend(cls.fetch_remoteok())
        all_jobs.extend(cls.fetch_jobicy())
        all_jobs.extend(cls.fetch_arbeitnow())
        all_jobs.extend(cls.fetch_weworkremotely())
        return all_jobs


# History Manager for Deduplication and CSV Logging
class HistoryManager:
    CSV_HEADERS = ["job_id", "timestamp", "title", "company", "match_score", "url", "source", "location", "matched_skills"]

    def __init__(self, filename: str = "jobs_history.csv"):
        self.filename = filename
        self.seen_job_ids: Set[str] = set()
        self.seen_urls: Set[str] = set()
        self.init_storage()

    def init_storage(self) -> None:
        if not os.path.exists(self.filename):
            with open(self.filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(self.CSV_HEADERS)
        else:
            try:
                with open(self.filename, "r", newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if "job_id" in row and row["job_id"]:
                            self.seen_job_ids.add(row["job_id"].strip())
                        if "url" in row and row["url"]:
                            self.seen_urls.add(row["url"].strip().lower())
            except Exception as e:
                UI.warning(f"Could not load previous jobs history: {e}")

    def is_duplicate(self, job: JobPosting) -> bool:
        if job.job_id in self.seen_job_ids:
            return True
        if job.url and job.url.lower() in self.seen_urls:
            return True
        return False

    def record_job(self, job: JobPosting, score: float, matched_skills: List[str]) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        skills_str = ", ".join(matched_skills[:12])

        with open(self.filename, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                job.job_id,
                now,
                job.title,
                job.company,
                f"{score:.1f}%",
                job.url,
                job.source,
                job.location,
                skills_str
            ])

        self.seen_job_ids.add(job.job_id)
        if job.url:
            self.seen_urls.add(job.url.lower())


# Notification Display
def display_job_alert(job: JobPosting, score: float, matched_skills: List[str], details: Dict[str, Any]) -> None:
    score_color = UI.GREEN if score >= 90 else UI.CYAN
    print("\n" + f"{UI.BOLD}{score_color}{'─' * 70}{UI.RESET}")
    print(f" {UI.BOLD}{score_color}🎯 HIGH MATCH FOUND: {score:.1f}%{UI.RESET} | {UI.BOLD}{job.title}{UI.RESET}")
    print(f"{UI.BOLD}{score_color}{'─' * 70}{UI.RESET}")
    print(f" {UI.BOLD}Company    :{UI.RESET} {job.company or 'Confidential / Remote'}")
    print(f" {UI.BOLD}Source     :{UI.RESET} {job.source} ({job.location})")
    print(f" {UI.BOLD}Apply Link :{UI.RESET} {UI.CYAN}{job.url}{UI.RESET}")
    print(f" {UI.BOLD}Breakdown  :{UI.RESET} Title: {details['title_score']} pts | Skills: {details['skill_score']} pts | Domain: {details['domain_score']} pts")
    if matched_skills:
        top_skills = ", ".join(matched_skills[:10])
        print(f" {UI.BOLD}Matched    :{UI.RESET} {UI.YELLOW}{top_skills}{UI.RESET}")
    print(f"{score_color}{'─' * 70}{UI.RESET}\n")


# Main Bot Orchestrator
class RemoteJobHunterBot:
    def __init__(self, resume_path: str = "resume.json", min_score: float = 85.0):
        self.profile = CandidateProfile(resume_path)
        self.history = HistoryManager("jobs_history.csv")
        self.min_score = min_score

    def run_cycle(self) -> Dict[str, int]:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        UI.header(f"Job Hunter Cycle Started at {timestamp}")
        UI.info(f"Target Candidate : {self.profile.name}")
        UI.info(f"Match Threshold  : {self.min_score}%")
        UI.info(f"History File     : jobs_history.csv ({len(self.history.seen_job_ids)} jobs previously logged)")

        jobs = JobFetcher.fetch_all()
        stats = {
            "total_fetched": len(jobs),
            "duplicates_skipped": 0,
            "evaluated": 0,
            "high_matches": 0
        }

        unique_batch: Dict[str, JobPosting] = {}
        for j in jobs:
            if j.job_id not in unique_batch:
                unique_batch[j.job_id] = j

        for job in unique_batch.values():
            if self.history.is_duplicate(job):
                stats["duplicates_skipped"] += 1
                continue

            stats["evaluated"] += 1
            score, matched_skills, details = self.profile.evaluate_job(job)

            if score >= self.min_score:
                stats["high_matches"] += 1
                display_job_alert(job, score, matched_skills, details)
                send_telegram_alert(job, score, matched_skills)  # Triggers Telegram push notification
                self.history.record_job(job, score, matched_skills)

        UI.header("Cycle Summary")
        print(f" Total Jobs Fetched   : {stats['total_fetched']}")
        print(f" Duplicates Skipped   : {stats['duplicates_skipped']}")
        print(f" Fresh Evaluated      : {stats['evaluated']}")
        print(f" Matches (>= {self.min_score}%) : {UI.BOLD}{UI.GREEN}{stats['high_matches']}{UI.RESET}")
        print(f"{UI.CYAN}{'=' * 70}{UI.RESET}\n")

        return stats

    def run_daemon(self, interval_minutes: int = 30) -> None:
        UI.header(f"24/7 Remote Job Hunter Daemon Initialized")
        UI.info(f"Monitoring every {interval_minutes} minutes. Press Ctrl+C to terminate.")

        try:
            while True:
                self.run_cycle()
                next_check = datetime.now().timestamp() + (interval_minutes * 60)
                next_time_str = datetime.fromtimestamp(next_check).strftime("%H:%M:%S")
                UI.info(f"Sleeping for {interval_minutes} minutes... Next scan scheduled for {next_time_str}")
                time.sleep(interval_minutes * 60)
        except KeyboardInterrupt:
            print("\n")
            UI.warning("Bot gracefully stopped by user. Goodbye!")


def main():
    parser = argparse.ArgumentParser(
        description="24/7 Automated Remote Job Hunter with Resume Keyword Matching"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single scan cycle and exit immediately"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Interval between scans in minutes for daemon mode"
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=85.0,
        help="Minimum percentage match score to trigger alerts and logging"
    )
    parser.add_argument(
        "--resume",
        type=str,
        default="resume.json",
        help="Path to resume.json file"
    )
    parser.add_argument(
        "--test-resume",
        action="store_true",
        help="Parse resume.json and display recognized skills and weights, then exit"
    )

    args = parser.parse_args()

    if args.test_resume:
        UI.header("Testing Resume Profile Extraction")
        profile = CandidateProfile(args.resume)
        print(f"Candidate Name  : {profile.name}")
        print(f"Key Skills Extracted: {len(profile.key_skills)}")
        print(f"Tools & Software: {len(profile.tools)}")
        print(f"Recognized Weighted Keywords: {len(profile.weighted_keywords)}")
        print("\nTop 25 Weighted Keywords:")
        sorted_kws = sorted(profile.weighted_keywords.items(), key=lambda x: x[1], reverse=True)[:25]
        for kw, w in sorted_kws:
            print(f"  • {kw:<25} (weight: {w})")
        return

    bot = RemoteJobHunterBot(resume_path=args.resume, min_score=args.min_score)

    if args.once:
        bot.run_cycle()
    else:
        bot.run_daemon(interval_minutes=args.interval)


if __name__ == "__main__":
    main()