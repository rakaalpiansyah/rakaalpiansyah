"""Pure SVG renderer for the Midnight Slate & Sky-Blue 3D telemetry dashboard."""
from __future__ import annotations

from datetime import date
from pathlib import Path
import re
import sys
from xml.sax.saxutils import escape

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.telemetry_metrics import TelemetryData, compute_telemetry_hash

HASH_PATTERN = re.compile(r"<!--\s*telemetry-hash:\s*([0-9a-fA-F]{64})\s*-->")
MONO_FONT = "'JetBrains Mono', 'Fira Code', 'Consolas', monospace"
SANS_FONT = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"


def extract_existing_hash(svg_text: str) -> str | None:
    """Return the embedded SHA-256 telemetry hash from an SVG string, if present."""
    match = HASH_PATTERN.search(svg_text)
    return match.group(1).lower() if match else None


def _plural(count: int, singular: str, plural: str) -> str:
    return f"{count:,} {singular if count == 1 else plural}"


def _format_short_range(start_iso: str, end_iso: str) -> str:
    if not start_iso or not end_iso:
        return "NO ACTIVE STREAK"
    s = date.fromisoformat(start_iso)
    e = date.fromisoformat(end_iso)
    s_lbl = s.strftime("%b %d").upper().replace(" 0", " ")
    e_lbl = e.strftime("%b %d").upper().replace(" 0", " ")
    if s == e:
        return s_lbl
    if s.year != e.year:
        return f"{s_lbl} '{s.strftime('%y')} - {e_lbl} '{e.strftime('%y')}"
    return f"{s_lbl} - {e_lbl}"


def _resolve_grid_cells(days_52w: list[dict]) -> list[tuple[int, int, int]]:
    """Return sorted (week_idx, day_idx, count) tuples ordered back-to-front."""
    cells: list[tuple[int, int, int]] = []
    inferred_week = 0
    prev_weekday: int | None = None
    for d in days_52w:
        count = int(d.get("contributionCount", 0))
        weekday = int(d.get("weekday", 0))
        if "week_idx" in d:
            week_idx = int(d["week_idx"])
        else:
            if prev_weekday is not None and weekday <= prev_weekday:
                inferred_week += 1
            week_idx = inferred_week
            prev_weekday = weekday
        cells.append((week_idx, weekday, count))
    cells.sort(key=lambda c: (c[0], c[1]))
    return cells


def _bar_colors(count: int, max_count: int) -> tuple[str, str, str]:
    if count <= 0 or max_count <= 0:
        return ("#162032", "#111827", "#0d131f")
    ratio = count / max_count
    if ratio <= 0.25:
        return ("#0284c7", "#0369a1", "#075985")
    if ratio <= 0.65:
        return ("#0ea5e9", "#0284c7", "#0369a1")
    return ("#38bdf8", "#0ea5e9", "#0284c7")


def _render_terrain(days_52w: list[dict]) -> str:
    cells = _resolve_grid_cells(days_52w)
    max_count = max((c[2] for c in cells), default=0)
    parts: list[str] = []
    for week_idx, day_idx, count in cells:
        bx = round(140.0 + 20.0 * week_idx - 20.0 * day_idx, 2)
        by = round(154.18 + 11.547 * week_idx + 11.547 * day_idx, 2)
        top_c, left_c, right_c = _bar_colors(count, max_count)
        if count <= 0:
            parts.append(
                f'<g transform="translate({bx:g} {by:g})">'
                f'<rect stroke="none" x="0" y="0" width="18" height="18" transform="skewY(-30) skewX(40.89) scale(1 1.15)" fill="{top_c}"/>'
                f'<rect stroke="none" x="0" y="0" width="18" height="2.6" transform="skewY(30) scale(1 1.15)" fill="{left_c}"/>'
                f'<rect stroke="none" x="0" y="0" width="18" height="2.6" transform="translate(18 10.39) skewY(-30) scale(1 1.15)" fill="{right_c}"/>'
                f'</g>'
            )
        else:
            h = round(min(88.12, 5.24 + ((count - 1) / max(1, max_count - 1)) * 82.88), 2)
            ty = round(by - (h - 2.6) * 1.1547, 2)
            parts.append(
                f'<g transform="translate({bx:g} {ty:g})">'
                f'<animateTransform attributeName="transform" type="translate" values="{bx:g} {by:g};{bx:g} {ty:g}" dur="3s" repeatCount="1"/>'
                f'<rect stroke="none" x="0" y="0" width="18" height="18" transform="skewY(-30) skewX(40.89) scale(1 1.15)" fill="{top_c}"/>'
                f'<rect stroke="none" x="0" y="0" width="18" height="{h:g}" transform="skewY(30) scale(1 1.15)" fill="{left_c}">'
                f'<animate attributeName="height" values="2.6;{h:g}" dur="3s" repeatCount="1"/></rect>'
                f'<rect stroke="none" x="0" y="0" width="18" height="{h:g}" transform="translate(18 10.39) skewY(-30) scale(1 1.15)" fill="{right_c}">'
                f'<animate attributeName="height" values="2.6;{h:g}" dur="3s" repeatCount="1"/></rect>'
                f'</g>'
            )
    return "".join(parts)


def _render_languages(data: TelemetryData) -> str:
    if not data.languages:
        return (
            '<text x="22" y="72" fill="#64748b" '
            f'font-family="{SANS_FONT}" font-size="12">No repository language telemetry available.</text>'
        )
    items = data.languages[:6]
    top_pct = max((cat.percentage for cat in items), default=1)
    rows: list[str] = []
    for idx, cat in enumerate(items):
        y = 56 + idx * 48
        bar_w = max(6, round((cat.percentage / max(1, top_pct)) * 354)) if cat.percentage > 0 else 0
        repo_lbl = "1 Repo" if cat.repo_count == 1 else f"{cat.repo_count} Repos"
        rows.append(
            f'''    <g transform="translate(22, {y})">
      <circle cx="6" cy="8" r="4" fill="{cat.color}"/>
      <text x="18" y="12" fill="#f1f5f9" font-family="{SANS_FONT}" font-size="12.5" font-weight="700">{escape(cat.name)}</text>
      <text x="225" y="12" fill="#64748b" font-family="{MONO_FONT}" font-size="9.5" font-weight="500">{escape(repo_lbl)}</text>
      <text x="416" y="12" text-anchor="end" fill="{cat.color}" font-family="{MONO_FONT}" font-size="11.5" font-weight="700">{cat.percentage}%</text>
      <rect x="0" y="20" width="416" height="7" rx="3.5" fill="#0b0f17" stroke="#1e293b" stroke-width="0.8"/>
      <rect x="0" y="20" width="{bar_w}" height="7" rx="3.5" fill="{cat.color}"/>
      <text x="0" y="39" fill="#64748b" font-family="{SANS_FONT}" font-size="10.5">{escape(cat.subtitle)}</text>
    </g>'''
        )
    return "\n".join(rows)


def _render_card(
    x: int,
    width: int,
    label: str,
    value: str,
    badge: str,
    badge_color: str,
    value_size: int = 18,
) -> str:
    badge_x = width - 20
    return f'''    <g transform="translate({x}, 0)">
      <rect x="0" y="0" width="{width}" height="66" rx="12" fill="#111827" stroke="#1e293b" stroke-width="1"/>
      <text x="20" y="25" fill="#64748b" font-family="{MONO_FONT}" font-size="9.5" font-weight="600">{escape(label)}</text>
      <text x="20" y="49" fill="#f8fafc" font-family="{SANS_FONT}" font-size="{value_size}" font-weight="800">{escape(value)}</text>
      <text x="{badge_x}" y="48" text-anchor="end" fill="{badge_color}" font-family="{MONO_FONT}" font-size="10.5" font-weight="700">{escape(badge)}</text>
    </g>'''


def render_telemetry_svg(data: TelemetryData, synced_label_wib: str) -> str:
    """Render the complete 1200x540 Midnight Slate & Sky-Blue telemetry SVG."""
    data_hash = compute_telemetry_hash(data)
    terrain_markup = _render_terrain(data.days_52w)
    langs_markup = _render_languages(data)

    cur_streak_val = _plural(data.streak.current_days, "Day", "Days")
    cur_streak_badge = _format_short_range(data.streak.current_start, data.streak.current_end)
    longest_val = _plural(data.streak.longest_days, "Day", "Days")
    longest_badge = f"{data.streak.active_days_52w:,} ACTIVE DAYS"
    repos_val = _plural(data.total_repos, "Project", "Projects")
    repos_badge = f"{data.public_repos} PUB · {data.private_repos} PRIV"

    cards_markup = "\n".join([
        _render_card(0, 268, "TOTAL CONTRIBUTIONS", f"{data.total_contributions_all_time:,} Total", "ALL-TIME", "#38bdf8"),
        _render_card(286, 268, "TOTAL REPOSITORIES", repos_val, repos_badge, "#60a5fa"),
        _render_card(572, 268, "CURRENT STREAK", cur_streak_val, cur_streak_badge, "#38bdf8"),
        _render_card(858, 270, "LONGEST STREAK", longest_val, longest_badge, "#60a5fa"),
    ])

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 540" width="100%" height="100%">
  <!-- telemetry-hash: {data_hash} -->
  <defs>
    <linearGradient id="telBg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0b0f17"/>
      <stop offset="100%" stop-color="#0f172a"/>
    </linearGradient>
    <pattern id="telGrid" width="32" height="32" patternUnits="userSpaceOnUse">
      <path d="M 32 0 L 0 0 0 32" fill="none" stroke="#94a3b8" stroke-width="0.5" stroke-opacity="0.035"/>
    </pattern>
    <clipPath id="terrainClip">
      <rect x="36" y="84" width="648" height="348" rx="14"/>
    </clipPath>
  </defs>

  <rect x="1.5" y="1.5" width="1197" height="537" rx="16" fill="url(#telBg)" stroke="#1e293b" stroke-width="1.5"/>
  <rect x="1.5" y="1.5" width="1197" height="537" rx="16" fill="url(#telGrid)"/>

  <!-- Header -->
  <text x="36" y="38" fill="#38bdf8" font-family="{MONO_FONT}" font-size="10.5" font-weight="700" letter-spacing="1">ENGINEERING TELEMETRY  ·  PUBLIC &amp; PRIVATE REPOSITORIES</text>
  <text x="1164" y="38" text-anchor="end" fill="#64748b" font-family="{MONO_FONT}" font-size="9.5" font-weight="600">SYNCED {escape(synced_label_wib)}</text>
  <text x="36" y="64" fill="#f8fafc" font-family="{SANS_FONT}" font-size="22" font-weight="800">3D Contribution Terrain &amp; True Language Distribution</text>

  <!-- Left Panel: 3D Contribution Terrain Well -->
  <rect x="36" y="84" width="648" height="348" rx="14" fill="#090d16" stroke="#1e293b" stroke-width="1"/>
  <text x="56" y="112" fill="#94a3b8" font-family="{MONO_FONT}" font-size="10" font-weight="600" letter-spacing="0.6">3D ISOMETRIC COMMIT TOPOGRAPHY (52-WEEK ACTIVITY)</text>
  <g clip-path="url(#terrainClip)">
    <g transform="translate(85, 86) scale(0.46, 0.37)">
      <g>{terrain_markup}</g>
    </g>
  </g>
  <g transform="translate(56, 404)">
    <text x="0" y="10" fill="#64748b" font-family="{MONO_FONT}" font-size="9.5">ACTIVITY LEVEL:</text>
    <rect x="98" y="1" width="10" height="10" rx="2" fill="#162032" stroke="#1e293b" stroke-width="0.8"/>
    <rect x="114" y="1" width="10" height="10" rx="2" fill="#0284c7"/>
    <rect x="130" y="1" width="10" height="10" rx="2" fill="#0ea5e9"/>
    <rect x="146" y="1" width="10" height="10" rx="2" fill="#38bdf8"/>
    <text x="608" y="10" text-anchor="end" fill="#38bdf8" font-family="{MONO_FONT}" font-size="10" font-weight="700">{data.total_contributions_52w:,} CONTRIBUTIONS (52W)</text>
  </g>

  <!-- Right Panel: True Language Distribution (Public + Private) -->
  <g transform="translate(704, 84)">
    <rect x="0" y="0" width="460" height="348" rx="14" fill="#111827" stroke="#1e293b" stroke-width="1"/>
    <line x1="22" y1="0" x2="160" y2="0" stroke="#38bdf8" stroke-width="2"/>
    <text x="22" y="28" fill="#38bdf8" font-family="{MONO_FONT}" font-size="10" font-weight="700" letter-spacing="0.6">TOP LANGUAGES (PUBLIC + PRIVATE REPOS)</text>
{langs_markup}
  </g>

  <!-- Bottom Telemetry Strip (4 Equal Cards) -->
  <g transform="translate(36, 448)">
{cards_markup}
  </g>
</svg>
'''
