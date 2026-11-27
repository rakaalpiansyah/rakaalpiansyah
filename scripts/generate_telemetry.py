"""GitHub GraphQL client and CLI entrypoint for updating assets/telemetry-3d.svg."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.telemetry_metrics import build_telemetry, compute_telemetry_hash
from scripts.telemetry_svg import extract_existing_hash, render_telemetry_svg

GRAPHQL_ENDPOINT = "https://api.github.com/graphql"

INITIAL_QUERY = """
query($cursor: String) {
  viewer {
    createdAt
    repositories(first: 100, after: $cursor, ownerAffiliations: [OWNER], isFork: false) {
      pageInfo {
        hasNextPage
        endCursor
      }
      nodes {
        name
        isPrivate
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges {
            size
            node {
              name
            }
          }
        }
      }
    }
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
            weekday
          }
        }
      }
    }
  }
}
"""

REPOS_PAGE_QUERY = """
query($cursor: String) {
  viewer {
    repositories(first: 100, after: $cursor, ownerAffiliations: [OWNER], isFork: false) {
      pageInfo {
        hasNextPage
        endCursor
      }
      nodes {
        name
        isPrivate
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges {
            size
            node {
              name
            }
          }
        }
      }
    }
  }
}
"""

YEARLY_CONTRIB_QUERY = """
query($from: DateTime!, $to: DateTime!) {
  viewer {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
            weekday
          }
        }
      }
    }
  }
}
"""


def get_now_wib() -> datetime:
    """Return the current timestamp in Asia/Jakarta (UTC+7)."""
    try:
        tz = ZoneInfo("Asia/Jakarta")
    except ZoneInfoNotFoundError:
        tz = timezone(timedelta(hours=7))
    return datetime.now(tz)


def post_graphql(token: str, query: str, variables: dict | None = None) -> dict:
    """Execute a GitHub GraphQL v4 request with Bearer token authentication."""
    payload = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    req = urllib.request.Request(
        GRAPHQL_ENDPOINT,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "rakaalpiansyah-telemetry",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"GitHub GraphQL HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GitHub GraphQL connection error: {exc.reason}") from exc

    if body.get("errors"):
        raise RuntimeError(f"GitHub GraphQL errors: {json.dumps(body['errors'])}")
    return body


def _checked_graphql(graphql_fn, token: str, query: str, variables: dict | None = None) -> dict:
    resp = graphql_fn(token, query, variables or {})
    if resp.get("errors"):
        raise RuntimeError(f"GitHub GraphQL errors: {json.dumps(resp['errors'])}")
    if "data" not in resp or resp["data"] is None:
        raise RuntimeError("GitHub GraphQL response missing 'data'")
    return resp["data"]


def fetch_github_data(
    token: str,
    graphql_fn=None,
    now_year: int | None = None,
) -> tuple[list[dict], list[dict], dict]:
    """Fetch all owned non-fork repositories, yearly calendars, and 52-week calendar."""
    fn = graphql_fn or post_graphql
    initial = _checked_graphql(fn, token, INITIAL_QUERY, {"cursor": None})["viewer"]
    repos = list(initial["repositories"]["nodes"])
    page_info = initial["repositories"]["pageInfo"]
    calendar_52w = initial["contributionsCollection"]["contributionCalendar"]
    created_year = int(initial["createdAt"][:4])
    target_year = now_year if now_year is not None else get_now_wib().year

    while page_info.get("hasNextPage"):
        cursor = page_info.get("endCursor")
        page = _checked_graphql(fn, token, REPOS_PAGE_QUERY, {"cursor": cursor})["viewer"]["repositories"]
        repos.extend(page["nodes"])
        page_info = page["pageInfo"]

    yearly_calendars: list[dict] = []
    for year in range(created_year, target_year + 1):
        variables = {
            "from": f"{year}-01-01T00:00:00Z",
            "to": f"{year}-12-31T23:59:59Z",
        }
        yr_data = _checked_graphql(fn, token, YEARLY_CONTRIB_QUERY, variables)["viewer"]
        yearly_calendars.append(yr_data["contributionsCollection"]["contributionCalendar"])

    return repos, yearly_calendars, calendar_52w


def _atomic_write_utf8(target: Path, content: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".telemetry-", suffix=".tmp", dir=str(target.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(tmp_path, target)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def run_generation(
    output_path: Path,
    token: str,
    force: bool = False,
    now_wib: datetime | None = None,
    fetch_fn=None,
) -> bool:
    """Generate and write telemetry SVG if metrics hash changed or force=True."""
    clean_token = (token or "").strip()
    if not clean_token:
        raise ValueError("METRICS_TOKEN is required and cannot be empty.")

    current_wib = now_wib or get_now_wib()
    fetcher = fetch_fn or fetch_github_data
    repos, yearly_calendars, calendar_52w = fetcher(clean_token, now_year=current_wib.year)
    data = build_telemetry(
        repos=repos,
        yearly_calendars=yearly_calendars,
        calendar_52w=calendar_52w,
        today_wib=current_wib.date().isoformat(),
    )
    new_hash = compute_telemetry_hash(data)

    if not force and output_path.exists():
        existing_hash = extract_existing_hash(output_path.read_text(encoding="utf-8"))
        if existing_hash == new_hash:
            return False

    synced_label = current_wib.strftime("%b %d · %H:%M WIB").upper()
    svg = render_telemetry_svg(data, synced_label_wib=synced_label)
    _atomic_write_utf8(output_path, svg)
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate realtime GitHub telemetry & streak SVG.")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT_DIR / "assets" / "telemetry-3d.svg",
        help="Destination SVG file path",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rewrite output even if the canonical metrics hash matches",
    )
    parser.add_argument(
        "--token-env",
        default="METRICS_TOKEN",
        help="Environment variable name holding the GitHub PAT",
    )
    args = parser.parse_args(argv)

    token = os.environ.get(args.token_env, "").strip()
    if not token:
        print(
            f"Error: environment variable {args.token_env} is missing or empty. "
            "Configure a GitHub PAT with 'repo' and 'read:user' scopes.",
            file=sys.stderr,
        )
        return 1

    try:
        updated = run_generation(output_path=args.output, token=token, force=args.force)
    except Exception as exc:
        print(f"Error generating telemetry SVG: {exc}", file=sys.stderr)
        return 1

    if updated:
        print(f"Updated {args.output}")
    else:
        print(f"Skipped {args.output} (telemetry hash unchanged)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
