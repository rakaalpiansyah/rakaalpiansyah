"""Pure metrics computation for GitHub telemetry, streaks, and language distribution."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
import hashlib
import json

MARKUP_AND_CONFIG_LANGUAGES = frozenset({
    "HTML",
    "CSS",
    "SCSS",
    "Sass",
    "Less",
    "Makefile",
    "Dockerfile",
    "Batchfile",
    "PowerShell",
    "ShaderLab",
    "CMake",
    "Nix",
})

LANGUAGE_BUCKETS = (
    ("Python & AI Pipelines", "FastAPI · AI/ML · Pipelines", "#38bdf8", ("Python", "Jupyter Notebook")),
    ("Java & Kotlin Systems", "Android · OOP · JVM", "#60a5fa", ("Java", "Kotlin")),
    ("JavaScript & TypeScript", "React · Next.js · Web", "#38bdf8", ("JavaScript", "TypeScript", "Vue", "Svelte")),
    ("PHP & Laravel Backend", "Laravel · REST API · Blade", "#818cf8", ("PHP", "Blade")),
    ("Dart & Flutter Mobile", "Flutter · Google Play · Clean Arch", "#2dd4bf", ("Dart",)),
    ("C++, Go & Systems", "Systems · Blockchain · CLI", "#94a3b8", ("C++", "C", "Go", "Shell", "C#", "Rust", "Wolfram Language")),
)

DEFAULT_BUCKET_NAME = "C++, Go & Systems"
LANGUAGE_TO_BUCKET = {
    lang: bucket_name
    for bucket_name, _, _, langs in LANGUAGE_BUCKETS
    for lang in langs
}
BUCKET_META = {
    bucket_name: (subtitle, color)
    for bucket_name, subtitle, color, _ in LANGUAGE_BUCKETS
}


@dataclass(frozen=True)
class LanguageCategory:
    name: str
    subtitle: str
    color: str
    repo_count: int
    percentage: int
    weight: float


@dataclass(frozen=True)
class StreakStats:
    current_days: int
    current_start: str
    current_end: str
    longest_days: int
    longest_start: str
    longest_end: str
    active_days_52w: int
    total_days_52w: int


@dataclass(frozen=True)
class TelemetryData:
    days_52w: list[dict]
    total_contributions_52w: int
    total_contributions_all_time: int
    total_repos: int
    public_repos: int
    private_repos: int
    languages: list[LanguageCategory]
    streak: StreakStats


def compute_streaks(
    daily_counts: dict[str, int],
    today_wib: str,
    days_52w: list[dict],
) -> StreakStats:
    """Compute current (with today grace period) and all-time longest contribution streaks."""
    today_dt = date.fromisoformat(today_wib)
    active_dates = sorted(
        dt
        for ds, count in daily_counts.items()
        if count > 0 and (dt := date.fromisoformat(ds)) <= today_dt
    )
    active_set = set(active_dates)

    # Allow grace period for the current WIB day before any commit lands today.
    anchor = today_dt if today_dt in active_set else (today_dt - timedelta(days=1))
    current_days = 0
    current_start = ""
    current_end = ""
    if anchor in active_set:
        current_end = anchor.isoformat()
        cursor = anchor
        while cursor in active_set:
            current_start = cursor.isoformat()
            current_days += 1
            cursor -= timedelta(days=1)

    longest_days = 0
    longest_start = ""
    longest_end = ""
    run_len = 0
    run_start: date | None = None
    prev_dt: date | None = None
    for dt in active_dates:
        if prev_dt is not None and (dt - prev_dt).days == 1:
            run_len += 1
        else:
            run_len = 1
            run_start = dt
        if run_len > longest_days:
            longest_days = run_len
            longest_start = run_start.isoformat()
            longest_end = dt.isoformat()
        prev_dt = dt

    active_days_52w = sum(1 for d in days_52w if int(d.get("contributionCount", 0)) > 0)
    return StreakStats(
        current_days=current_days,
        current_start=current_start,
        current_end=current_end,
        longest_days=longest_days,
        longest_start=longest_start,
        longest_end=longest_end,
        active_days_52w=active_days_52w,
        total_days_52w=len(days_52w),
    )


def _allocate_percentages(weights: list[float]) -> list[int]:
    """Allocate integer percentages summing to 100 via largest-remainder rounding."""
    total = sum(weights)
    if total <= 0:
        return [0] * len(weights)
    exact = [(w / total) * 100.0 for w in weights]
    floors = [int(v) for v in exact]
    remainder = 100 - sum(floors)
    order = sorted(range(len(exact)), key=lambda i: -(exact[i] - floors[i]))
    for idx in order[:remainder]:
        floors[idx] += 1
    return floors


def compute_languages(repos: list[dict]) -> list[LanguageCategory]:
    """Aggregate per-repo normalized weights across public and private repositories."""
    bucket_weights: dict[str, float] = {}
    bucket_repos: dict[str, set[str]] = {}

    for idx, repo in enumerate(repos):
        repo_id = str(repo.get("name") or f"repo-{idx}")
        edges = (repo.get("languages") or {}).get("edges") or []
        code_edges = [
            (edge["node"]["name"], int(edge.get("size", 0)))
            for edge in edges
            if edge.get("node", {}).get("name") not in MARKUP_AND_CONFIG_LANGUAGES
            and int(edge.get("size", 0)) > 0
        ]
        repo_code_bytes = sum(size for _, size in code_edges)
        if repo_code_bytes <= 0:
            continue
        for lang_name, size in code_edges:
            bucket = LANGUAGE_TO_BUCKET.get(lang_name, DEFAULT_BUCKET_NAME)
            bucket_weights[bucket] = bucket_weights.get(bucket, 0.0) + (size / repo_code_bytes)
            bucket_repos.setdefault(bucket, set()).add(repo_id)

    ordered = sorted(bucket_weights.items(), key=lambda item: -item[1])
    if not ordered:
        return []

    percentages = _allocate_percentages([w for _, w in ordered])
    result: list[LanguageCategory] = []
    for (bucket_name, weight), pct in zip(ordered, percentages):
        subtitle, color = BUCKET_META[bucket_name]
        result.append(
            LanguageCategory(
                name=bucket_name,
                subtitle=subtitle,
                color=color,
                repo_count=len(bucket_repos[bucket_name]),
                percentage=pct,
                weight=round(weight, 6),
            )
        )
    return result


def _flatten_calendar(calendar: dict) -> list[dict]:
    """Flatten GraphQL contributionCalendar weeks into ordered day entries with week_idx."""
    days: list[dict] = []
    for week_idx, week in enumerate(calendar.get("weeks") or []):
        for day in week.get("contributionDays") or []:
            ds = day["date"]
            weekday = day.get("weekday")
            if weekday is None:
                weekday = (date.fromisoformat(ds).weekday() + 1) % 7
            days.append({
                "date": ds,
                "contributionCount": int(day.get("contributionCount", 0)),
                "weekday": int(weekday),
                "week_idx": week_idx,
            })
    return days


def build_telemetry(
    repos: list[dict],
    yearly_calendars: list[dict],
    calendar_52w: dict,
    today_wib: str,
) -> TelemetryData:
    """Build complete TelemetryData from GraphQL repositories and contribution calendars."""
    days_52w = _flatten_calendar(calendar_52w)
    daily_counts: dict[str, int] = {}

    for cal in [*yearly_calendars, calendar_52w]:
        for week in cal.get("weeks") or []:
            for day in week.get("contributionDays") or []:
                ds = day["date"]
                cnt = int(day.get("contributionCount", 0))
                if cnt > daily_counts.get(ds, -1):
                    daily_counts[ds] = cnt

    total_all_time = sum(int(cal.get("totalContributions", 0)) for cal in yearly_calendars)
    total_52w = int(calendar_52w.get("totalContributions", sum(d["contributionCount"] for d in days_52w)))
    private_repos = sum(1 for r in repos if bool(r.get("isPrivate")))
    total_repos = len(repos)
    public_repos = total_repos - private_repos

    return TelemetryData(
        days_52w=days_52w,
        total_contributions_52w=total_52w,
        total_contributions_all_time=total_all_time,
        total_repos=total_repos,
        public_repos=public_repos,
        private_repos=private_repos,
        languages=compute_languages(repos),
        streak=compute_streaks(daily_counts, today_wib=today_wib, days_52w=days_52w),
    )


def compute_telemetry_hash(data: TelemetryData) -> str:
    """Compute a deterministic SHA-256 digest of canonical telemetry metrics."""
    payload = json.dumps(asdict(data), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
