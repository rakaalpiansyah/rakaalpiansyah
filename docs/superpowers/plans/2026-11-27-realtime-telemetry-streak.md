# Realtime GitHub Telemetry & Streak Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mengganti `assets/telemetry-3d.svg` yang statis dengan generator Python stdlib-only dan GitHub Actions terjadwal 3 jam sekali yang merender terrain 3D 52 minggu, distribusi bahasa public dan private ter-normalisasi, serta Current dan Longest Streak.

**Architecture:** Logika dipisah ke tiga modul kecil berbatas jelas: `scripts/telemetry_metrics.py` (perhitungan murni streak, normalisasi bahasa, dan SHA-256 hash), `scripts/telemetry_svg.py` (rendering murni SVG Midnight Slate & Sky-Blue `1200x540`), dan `scripts/generate_telemetry.py` (client GraphQL berpaginasi dan CLI). GitHub Actions di `.github/workflows/update-telemetry.yml` menjalankan generator memakai secret `METRICS_TOKEN` dan hanya melakukan commit jika hash data berubah.

**Tech Stack:** Python 3 standard library (`urllib.request`, `json`, `datetime`, `zoneinfo`, `hashlib`, `dataclasses`, `xml.sax.saxutils`, `unittest`), GitHub GraphQL API v4, GitHub Actions.

**Spec:** [2026-11-27-realtime-telemetry-streak-design.md](docs/superpowers/specs/2026-11-27-realtime-telemetry-streak-design.md)

## Global Constraints

- Python 3 standard library saja (tanpa `pip install` atau dependensi pihak ketiga).
- Dimensi SVG tetap `viewBox="0 0 1200 540"` dengan palet Midnight Slate dan Sky-Blue (`#0b0f17`, `#0f172a`, `#162032`, `#0284c7`, `#0ea5e9`, `#38bdf8`).
- Zona waktu `Asia/Jakarta` (UTC+7) untuk batas hari streak dan label `SYNCED <MON DD> · <HH:MM> WIB`.
- Wajib gagal dengan exit code non-zero jika `METRICS_TOKEN` kosong (dilarang fallback diam-diam ke `GITHUB_TOKEN` publik).
- Lewati penulisan file bila `<!-- telemetry-hash: <sha256> -->` sama dengan hash baru (kecuali `--force`).
- Author commit bot wajib `github-actions[bot]` (`github-actions[bot]@users.noreply.github.com`).

## Review Focus

- **Pergantian tahun dengan grace period hari berjalan:** Hari ini `0` kontribusi sedangkan kemarin `1 Jan` dan `31 Des` aktif harus menjaga `current_streak` tetap nyambung lintas tahun (diuji di Task 1).
- **Kalender nol kontribusi:** Semua hari bernilai `0` tidak boleh memicu pembagian nol saat menghitung skala tinggi balok 3D maupun rasio persentase, serta memformat `0 Days` secara bersih (diuji di Task 1 dan Task 2).
- **Outlier 1,5 GB C++ dan repo markup-only:** Satu repo dengan ukuran C++ raksasa tidak boleh mendominasi persentase bahasa global, dan repo berisi HTML/CSS saja tidak boleh menyebabkan pembagian nol (diuji di Task 1).
- **Karakter spesial XML dan kestabilan hash:** Karakter `&`, `<`, `>` pada label harus ter-escape agar SVG valid di `xml.etree.ElementTree`, dan perbedaan timestamp sinkronisasi pada data identik harus menghasilkan hash yang sama (diuji di Task 2 dan Task 3).
- **Token kosong, error GraphQL, dan pagination >100 repo:** `METRICS_TOKEN` kosong atau response dengan key `errors` harus gagal cepat tanpa menimpa `assets/telemetry-3d.svg`, dan `pageInfo.hasNextPage` harus diikuti sampai halaman terakhir (diuji di Task 3).

## File Structure

- Create: `scripts/telemetry_metrics.py` (dataclass dan fungsi murni statistik kontribusi, streak, bahasa, dan hash kanonis)
- Create: `scripts/telemetry_svg.py` (fungsi murni rendering SVG dan ekstraksi hash eksisting)
- Create: `scripts/generate_telemetry.py` (client GraphQL berpaginasi, orkestrasi baca/tulis atomik, dan CLI)
- Create: `tests/test_telemetry.py` (unit test `unittest` untuk metrics, renderer, dan CLI/client)
- Create: `.github/workflows/update-telemetry.yml` (workflow Actions cron 3 jam sekali)
- Delete: `.github/workflows/generate-animation.yml`, `profile-3d-contrib/`
- Modify (generated): `assets/telemetry-3d.svg`

---

### Task 1: Metrics Engine (`scripts/telemetry_metrics.py`)

**Files:**
- Create: `scripts/telemetry_metrics.py`
- Create: `tests/test_telemetry.py`

**Interfaces:**
- Consumes: list repo GraphQL (`name`, `isPrivate`, `languages.edges`), list kalender tahunan (`totalContributions`, `weeks`), dan kalender 52 minggu (`totalContributions`, `weeks`), plus `today_wib: str` (`YYYY-MM-DD`).
- Produces:
  - `@dataclass(frozen=True) class LanguageCategory(name: str, subtitle: str, color: str, repo_count: int, percentage: int, weight: float)`
  - `@dataclass(frozen=True) class StreakStats(current_days: int, current_start: str, current_end: str, longest_days: int, longest_start: str, longest_end: str, active_days_52w: int, total_days_52w: int)`
  - `@dataclass(frozen=True) class TelemetryData(days_52w: list[dict], total_contributions_52w: int, total_contributions_all_time: int, total_repos: int, public_repos: int, private_repos: int, languages: list[LanguageCategory], streak: StreakStats)`
  - `compute_streaks(daily_counts: dict[str, int], today_wib: str, days_52w: list[dict]) -> StreakStats`
  - `compute_languages(repos: list[dict]) -> list[LanguageCategory]`
  - `build_telemetry(repos: list[dict], yearly_calendars: list[dict], calendar_52w: dict, today_wib: str) -> TelemetryData`
  - `compute_telemetry_hash(data: TelemetryData) -> str`

**Spec-Pinned Mapping:**
- 6 kategori bahasa kode:
  1. `Python & AI Pipelines` (`#38bdf8`, `FastAPI · AI/ML · Pipelines`): `Python`, `Jupyter Notebook`
  2. `Java & Kotlin Systems` (`#60a5fa`, `Android · OOP · JVM`): `Java`, `Kotlin`
  3. `JavaScript & TypeScript` (`#38bdf8`, `React · Next.js · Web`): `JavaScript`, `TypeScript`, `Vue`, `Svelte`
  4. `PHP & Laravel Backend` (`#818cf8`, `Laravel · REST API · Blade`): `PHP`, `Blade`
  5. `Dart & Flutter Mobile` (`#2dd4bf`, `Flutter · Google Play · Clean Arch`): `Dart`
  6. `C++, Go & Systems` (`#94a3b8`, `Systems · Blockchain · CLI`): `C++`, `C`, `Go`, `Shell`, `C#`, `Rust`, `Wolfram Language`
- Bahasa markup/konfigurasi yang diabaikan dari pembagian bobot: `HTML`, `CSS`, `SCSS`, `Sass`, `Less`, `Makefile`, `Dockerfile`, `Batchfile`, `PowerShell`, `ShaderLab`, `CMake`, `Nix`.
- Setiap repo berbobot total `1.0` dibagi proporsional ke byte bahasa kode non-markup; kategori diurutkan turun berdasarkan `weight`; persentase bulat dihitung dengan largest-remainder method agar jumlahnya `100` (ketika total bobot > 0).

- [ ] **Step 1: Write failing tests in `tests/test_telemetry.py`**

```python
import unittest
from scripts.telemetry_metrics import (
    build_telemetry,
    compute_languages,
    compute_streaks,
    compute_telemetry_hash,
)


class TestTelemetryMetrics(unittest.TestCase):
    def test_streak_grace_period_and_year_boundary(self):
        daily = {
            "2025-12-30": 1,
            "2025-12-31": 3,
            "2026-01-01": 2,
            "2026-01-02": 0,
        }
        days_52w = [{"date": k, "contributionCount": v} for k, v in daily.items()]
        s = compute_streaks(daily, today_wib="2026-01-02", days_52w=days_52w)
        self.assertEqual(s.current_days, 3)
        self.assertEqual((s.current_start, s.current_end), ("2025-12-30", "2026-01-01"))
        self.assertEqual(s.longest_days, 3)
        self.assertEqual(s.active_days_52w, 3)

    def test_streak_all_zero(self):
        daily = {"2026-11-26": 0, "2026-11-27": 0}
        days_52w = [{"date": k, "contributionCount": v} for k, v in daily.items()]
        s = compute_streaks(daily, today_wib="2026-11-27", days_52w=days_52w)
        self.assertEqual(s.current_days, 0)
        self.assertEqual(s.longest_days, 0)
        self.assertEqual((s.current_start, s.current_end), ("", ""))

    def test_languages_normalized_outlier_and_markup_only(self):
        repos = [
            {
                "name": "huge-cpp",
                "isPrivate": False,
                "languages": {"edges": [{"size": 1_500_000_000, "node": {"name": "C++"}}]},
            },
            {
                "name": "py-1",
                "isPrivate": True,
                "languages": {
                    "edges": [
                        {"size": 5000, "node": {"name": "Python"}},
                        {"size": 5000, "node": {"name": "HTML"}},
                    ]
                },
            },
            {
                "name": "py-2",
                "isPrivate": False,
                "languages": {"edges": [{"size": 2000, "node": {"name": "Python"}}]},
            },
            {
                "name": "static-site",
                "isPrivate": False,
                "languages": {"edges": [{"size": 8000, "node": {"name": "HTML"}}]},
            },
        ]
        cats = compute_languages(repos)
        self.assertEqual(cats[0].name, "Python & AI Pipelines")
        self.assertEqual(cats[0].repo_count, 2)
        self.assertEqual(cats[0].percentage, 67)
        cpp = next(c for c in cats if c.name == "C++, Go & Systems")
        self.assertEqual(cpp.percentage, 33)
        self.assertEqual(sum(c.percentage for c in cats), 100)

    def test_build_telemetry_and_hash_determinism(self):
        repos = [
            {
                "name": "app",
                "isPrivate": True,
                "languages": {"edges": [{"size": 1000, "node": {"name": "Dart"}}]},
            }
        ]
        yearly = [
            {"totalContributions": 10, "weeks": [{"contributionDays": [{"date": "2025-12-31", "contributionCount": 2}]}]},
            {"totalContributions": 5, "weeks": [{"contributionDays": [{"date": "2026-01-01", "contributionCount": 5}]}]},
        ]
        cal52 = {
            "totalContributions": 7,
            "weeks": [{"contributionDays": [{"date": "2025-12-31", "contributionCount": 2}, {"date": "2026-01-01", "contributionCount": 5}]}],
        }
        t1 = build_telemetry(repos, yearly, cal52, today_wib="2026-01-01")
        t2 = build_telemetry(repos, yearly, cal52, today_wib="2026-01-01")
        self.assertEqual(t1.total_contributions_all_time, 15)
        self.assertEqual((t1.total_repos, t1.public_repos, t1.private_repos), (1, 0, 1))
        self.assertEqual(compute_telemetry_hash(t1), compute_telemetry_hash(t2))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_telemetry -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.telemetry_metrics'`.

- [ ] **Step 3: Implement `scripts/telemetry_metrics.py`**

Implement `LanguageCategory`, `StreakStats`, `TelemetryData`, `compute_streaks`, `compute_languages`, `build_telemetry`, and `compute_telemetry_hash` in `scripts/telemetry_metrics.py` using only the Python standard library. Keep `compute_telemetry_hash` purely derived from canonicalized metrics JSON (sorted keys, no sync timestamp).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_telemetry -v`
Expected: PASS (4 tests OK).

- [ ] **Step 5: Commit**

```bash
git add scripts/telemetry_metrics.py tests/test_telemetry.py
git commit -m "feat(telemetry): add metrics, streak, and language normalization engine"
```

---

### Task 2: 3D SVG Renderer (`scripts/telemetry_svg.py`)

**Files:**
- Create: `scripts/telemetry_svg.py`
- Modify: `tests/test_telemetry.py`

**Interfaces:**
- Consumes: `TelemetryData`, `compute_telemetry_hash` from `scripts.telemetry_metrics`.
- Produces:
  - `extract_existing_hash(svg_text: str) -> str | None`
  - `render_telemetry_svg(data: TelemetryData, synced_label_wib: str) -> str`

**Spec-Pinned Geometry & Layout:**
- Root SVG: `viewBox="0 0 1200 540" width="100%" height="100%"`, baris ke-2 memuat komentar `<!-- telemetry-hash: <sha256> -->`.
- Header: kiri `ENGINEERING TELEMETRY  ·  PUBLIC & PRIVATE REPOSITORIES` + judul `3D Contribution Terrain & True Language Distribution`; kanan atas (`x="1164" y="38" text-anchor="end"`) `SYNCED <synced_label_wib>`.
- Panel kiri (`x="36" y="84" width="648" height="348"`): `<g clip-path="url(#terrainClip)">` membungkus `<g transform="translate(85, 86) scale(0.46, 0.37)">`.
- Setiap sel `(week_idx, day_idx)` pada grid `days_52w`: `base_x = 140 + 20 * week_idx - 20 * day_idx`, `base_y = 154.18 + 11.547 * week_idx + 11.547 * day_idx`.
  - Jika `count == 0`: tinggi `2.6`, warna `("#162032", "#111827", "#0d131f")`, tanpa animasi SMIL.
  - Jika `count > 0`: tinggi `h = 5.24 + ((count - 1) / max(1, max_count - 1)) * 82.88` (maks `88.12`), posisi terangkat `bar_y = base_y - (h - 2.6) * 1.1547`, animasi SMIL grow-in dari `base_y` dan tinggi `2.6` ke `h` (`dur="3s"`). Level warna: `<= 0.25 * max_count` -> `("#0284c7", "#0369a1", "#075985")`, `<= 0.65 * max_count` -> `("#0ea5e9", "#0284c7", "#0369a1")`, selainnya `("#38bdf8", "#0ea5e9", "#0284c7")`.
- Legend kiri bawah: total kontribusi 52 minggu terformat (`1,442 CONTRIBUTIONS (52W)`).
- Panel kanan (`x="704" y="84" width="460" height="348"`): 6 baris kategori bahasa (`y = 56 + idx * 48`) dengan lebar bar proporsional terhadap skor teratas (`round(pct / max(1, top_pct) * 354)` dengan minimum `6` jika `pct > 0`).
- Strip 4 kartu bawah (`y="448"`, tinggi `66`, lebar `268, 268, 268, 270`):
  1. `TOTAL CONTRIBUTIONS` -> `{total_all:,} Total` / `ALL-TIME`
  2. `TOTAL REPOSITORIES` -> `{total_repos} Projects` / `{public_repos} PUB · {private_repos} PRIV`
  3. `CURRENT STREAK` -> `{current_days} Day(s)` / rentang tanggal atau `NO ACTIVE STREAK`
  4. `LONGEST STREAK` -> `{longest_days} Day(s)` / `{active_days_52w} ACTIVE DAYS`
- Semua teks dinamis wajib melalui `xml.sax.saxutils.escape`.

- [ ] **Step 1: Add failing SVG renderer tests to `tests/test_telemetry.py`**

```python
import xml.etree.ElementTree as ET
from scripts.telemetry_metrics import LanguageCategory, StreakStats, TelemetryData
from scripts.telemetry_svg import extract_existing_hash, render_telemetry_svg


class TestTelemetrySvg(unittest.TestCase):
    def test_render_svg_valid_xml_and_cards(self):
        data = TelemetryData(
            days_52w=[
                {"date": "2026-11-26", "contributionCount": 0, "weekday": 4},
                {"date": "2026-11-27", "contributionCount": 5, "weekday": 5},
            ],
            total_contributions_52w=5,
            total_contributions_all_time=1542,
            total_repos=55,
            public_repos=50,
            private_repos=5,
            languages=[
                LanguageCategory("Python & AI Pipelines", "FastAPI · AI/ML", "#38bdf8", 17, 60, 12.0),
                LanguageCategory("Java & Kotlin Systems", "Android · JVM", "#60a5fa", 20, 40, 8.0),
            ],
            streak=StreakStats(112, "2026-08-08", "2026-11-27", 112, "2026-08-08", "2026-11-27", 229, 365),
        )
        svg = render_telemetry_svg(data, "NOV 27 · 16:30 WIB")
        root = ET.fromstring(svg)
        self.assertEqual(root.attrib["viewBox"], "0 0 1200 540")
        self.assertIn("1,542 Total", svg)
        self.assertIn("55 Projects", svg)
        self.assertIn("112 Days", svg)
        self.assertIn("229 ACTIVE DAYS", svg)
        self.assertIn("SYNCED NOV 27 · 16:30 WIB", svg)
        self.assertIsNotNone(extract_existing_hash(svg))

    def test_render_svg_zero_activity_no_div_zero(self):
        data = TelemetryData(
            days_52w=[{"date": "2026-11-27", "contributionCount": 0, "weekday": 5}],
            total_contributions_52w=0,
            total_contributions_all_time=0,
            total_repos=0,
            public_repos=0,
            private_repos=0,
            languages=[],
            streak=StreakStats(0, "", "", 0, "", "", 0, 1),
        )
        svg = render_telemetry_svg(data, "NOV 27 · 16:30 WIB")
        ET.fromstring(svg)
        self.assertIn("0 Days", svg)

    def test_render_svg_xml_escaping_and_hash_extraction(self):
        data = TelemetryData(
            days_52w=[{"date": "2026-11-27", "contributionCount": 1, "weekday": 5}],
            total_contributions_52w=1,
            total_contributions_all_time=1,
            total_repos=1,
            public_repos=1,
            private_repos=0,
            languages=[LanguageCategory("C++ & Go <CLI>", "A & B", "#94a3b8", 1, 100, 1.0)],
            streak=StreakStats(1, "2026-11-27", "2026-11-27", 1, "2026-11-27", "2026-11-27", 1, 1),
        )
        svg = render_telemetry_svg(data, "NOV 27 <16:30> & WIB")
        ET.fromstring(svg)
        self.assertIn("1 Day", svg)
        self.assertIsNone(extract_existing_hash("<svg></svg>"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_telemetry -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.telemetry_svg'`.

- [ ] **Step 3: Implement `scripts/telemetry_svg.py`**

Implement `extract_existing_hash(svg_text: str) -> str | None` and `render_telemetry_svg(data: TelemetryData, synced_label_wib: str) -> str` in `scripts/telemetry_svg.py`, menjaga agar warna, layout, font, dan geometri balok 3D selaras dengan `assets/telemetry-3d.svg`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_telemetry -v`
Expected: PASS (7 tests OK).

- [ ] **Step 5: Commit**

```bash
git add scripts/telemetry_svg.py tests/test_telemetry.py
git commit -m "feat(telemetry): add Midnight Slate 3D isometric SVG renderer"
```

---

### Task 3: GraphQL Client & CLI (`scripts/generate_telemetry.py`)

**Files:**
- Create: `scripts/generate_telemetry.py`
- Modify: `tests/test_telemetry.py`

**Interfaces:**
- Consumes: `build_telemetry`, `compute_telemetry_hash` from `scripts.telemetry_metrics`; `extract_existing_hash`, `render_telemetry_svg` from `scripts.telemetry_svg`.
- Produces:
  - `fetch_github_data(token: str, graphql_fn=None) -> tuple[list[dict], list[dict], dict]`
  - `run_generation(output_path: Path, token: str, force: bool = False, now_wib: datetime | None = None, fetch_fn=None) -> bool`
  - `main(argv: list[str] | None = None) -> int`

**Requirements:**
- Jika `token` kosong atau whitespace, raise error / keluar non-zero dengan pesan yang jelas ke `stderr` tanpa menyentuh `output_path`.
- Jika respons JSON GraphQL memiliki key `"errors"`, raise `RuntimeError` yang memuat detail errornya.
- Pagination `repositories(first: 100, after: $cursor, ownerAffiliations: [OWNER], isFork: false)` wajib mengulang request selama `pageInfo.hasNextPage` bernilai `True`.
- Query `contributionsCollection` untuk seluruh tahun dari tahun `createdAt` hingga `now_wib.year` plus kalender 52 minggu bergulir.
- Gunakan `ZoneInfo("Asia/Jakarta")` (fallback `timezone(timedelta(hours=7))` bila tzdata sistem tidak tersedia) untuk `today_wib` dan format label `SYNCED <MON DD> · <HH:MM> WIB`.
- Jika `extract_existing_hash` file lama sama dengan `compute_telemetry_hash(data)` dan `force` False, lewati penulisan file dan kembalikan `False`; jika berbeda atau `force` True, tulis atomik lewat file sementara lalu `os.replace` dan kembalikan `True`.
- CLI mendukung `--output` (default `assets/telemetry-3d.svg`) dan `--force`.

- [ ] **Step 1: Add failing client & CLI tests to `tests/test_telemetry.py`**

```python
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from scripts.generate_telemetry import fetch_github_data, main, run_generation


class TestGenerateTelemetry(unittest.TestCase):
    def test_missing_token_fails_without_modifying_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "telemetry.svg"
            out.write_text("KEEP_ME", encoding="utf-8")
            rc = main(["--output", str(out), "--token-env", "NON_EXISTENT_TEST_TOKEN_XYZ"])
            self.assertNotEqual(rc, 0)
            self.assertEqual(out.read_text(encoding="utf-8"), "KEEP_ME")

    def test_graphql_pagination_and_error_handling(self):
        calls = []

        def fake_graphql(token, query, variables):
            calls.append(variables)
            if variables.get("cursor") is None and "createdAt" in query:
                return {
                    "data": {
                        "viewer": {
                            "createdAt": "2025-05-01T00:00:00Z",
                            "repositories": {
                                "pageInfo": {"hasNextPage": True, "endCursor": "C1"},
                                "nodes": [{"name": "r1", "isPrivate": False, "languages": {"edges": []}}],
                            },
                            "contributionsCollection": {
                                "contributionCalendar": {"totalContributions": 1, "weeks": []}
                            },
                        }
                    }
                }
            if variables.get("cursor") == "C1":
                return {
                    "data": {
                        "viewer": {
                            "repositories": {
                                "pageInfo": {"hasNextPage": False, "endCursor": None},
                                "nodes": [{"name": "r2", "isPrivate": True, "languages": {"edges": []}}],
                            }
                        }
                    }
                }
            return {
                "data": {
                    "viewer": {
                        "contributionsCollection": {
                            "contributionCalendar": {"totalContributions": 2, "weeks": []}
                        }
                    }
                }
            }

        repos, yearly, cal52 = fetch_github_data("tok", graphql_fn=fake_graphql, now_year=2026)
        self.assertEqual([r["name"] for r in repos], ["r1", "r2"])
        self.assertEqual(len(yearly), 2)
        self.assertEqual(cal52["totalContributions"], 1)

        def err_graphql(token, query, variables):
            return {"errors": [{"message": "Bad credentials"}]}

        with self.assertRaises(RuntimeError):
            fetch_github_data("bad", graphql_fn=err_graphql, now_year=2026)

    def test_run_generation_skips_write_on_same_hash_and_writes_on_change_or_force(self):
        def fake_fetch(token, now_year):
            repos = [{"name": "a", "isPrivate": True, "languages": {"edges": [{"size": 100, "node": {"name": "Python"}}]}}]
            days = [{"date": "2026-11-27", "contributionCount": 3, "weekday": 5}]
            cal = {"totalContributions": 3, "weeks": [{"contributionDays": days}]}
            return repos, [cal], cal

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "telemetry.svg"
            wib = timezone(timedelta(hours=7))
            t1 = datetime(2026, 11, 27, 16, 0, tzinfo=wib)
            t2 = datetime(2026, 11, 27, 19, 0, tzinfo=wib)
            self.assertTrue(run_generation(out, "tok", force=False, now_wib=t1, fetch_fn=fake_fetch))
            first_content = out.read_text(encoding="utf-8")
            self.assertFalse(run_generation(out, "tok", force=False, now_wib=t2, fetch_fn=fake_fetch))
            self.assertEqual(out.read_text(encoding="utf-8"), first_content)
            self.assertTrue(run_generation(out, "tok", force=True, now_wib=t2, fetch_fn=fake_fetch))
            self.assertIn("19:00 WIB", out.read_text(encoding="utf-8"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_telemetry -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.generate_telemetry'`.

- [ ] **Step 3: Implement `scripts/generate_telemetry.py`**

Implement `post_graphql`, `fetch_github_data`, `run_generation`, and `main` in `scripts/generate_telemetry.py`. Pastikan `fetch_github_data` mendukung parameter opsional `now_year: int | None = None`, dan `main` mendukung `--output`, `--force`, serta `--token-env` (default `METRICS_TOKEN`).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_telemetry -v`
Expected: PASS (10 tests OK).

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_telemetry.py tests/test_telemetry.py
git commit -m "feat(telemetry): add paginated GitHub GraphQL client and CLI"
```

---

### Task 4: GitHub Actions Workflow, Cleanup & Live Regeneration

**Files:**
- Create: `.github/workflows/update-telemetry.yml`
- Delete: `.github/workflows/generate-animation.yml`
- Delete: `profile-3d-contrib/`
- Modify: `assets/telemetry-3d.svg`

- [ ] **Step 1: Create `.github/workflows/update-telemetry.yml`**

Tulis workflow dengan:
- `name: Update Realtime Telemetry`
- `on`: `schedule` (`cron: "0 */3 * * *"`), `workflow_dispatch`, dan `push` ke `main` pada paths `scripts/**`, `.github/workflows/update-telemetry.yml`.
- `permissions: contents: write` dan `concurrency: group: update-telemetry, cancel-in-progress: false`.
- Job steps: `actions/checkout@v4`, `actions/setup-python@v5` (`python-version: "3.12"`), pengecekan wajib `METRICS_TOKEN` terisi (exit 1 jika kosong), menjalankan `python -m unittest discover -s tests -v`, menjalankan `python scripts/generate_telemetry.py`, lalu commit `assets/telemetry-3d.svg` dan push hanya jika `git diff --quiet assets/telemetry-3d.svg` mengembalikan perubahan, dengan author `github-actions[bot]` (`github-actions[bot]@users.noreply.github.com`).

- [ ] **Step 2: Remove legacy `.github/workflows/generate-animation.yml` and `profile-3d-contrib/`**

Jalankan `git rm` terhadap `.github/workflows/generate-animation.yml` dan `profile-3d-contrib/` (verifikasi dulu bahwa `README.md` dan file lain tidak mereferensikan `profile-3d-contrib`).

- [ ] **Step 3: Regenerate `assets/telemetry-3d.svg` with live data and verify idempotency**

Jalankan secara lokal:
- `$env:METRICS_TOKEN = (gh auth token)`
- `python -m unittest discover -s tests -v`
- `python scripts/generate_telemetry.py --force`
- Verifikasi `assets/telemetry-3d.svg` valid XML (`xml.etree.ElementTree.parse`), memuat `CURRENT STREAK`, `LONGEST STREAK`, `telemetry-hash`, serta angka kontribusi dan streak aktual.
- Jalankan ulang `python scripts/generate_telemetry.py` tanpa `--force` dan pastikan output menyatakan hash tidak berubah dan file tidak ditulis ulang.

- [ ] **Step 4: Commit workflow, cleanup, and regenerated SVG locally**

```bash
git add .github/workflows/update-telemetry.yml assets/telemetry-3d.svg
git commit -m "feat(telemetry): automate 3D telemetry and streak SVG via GitHub Actions"
```

Jangan lupa mengecek `git status -sb` dan `git log -n 6 --oneline` sebelum memberi tahu user langkah menambahkan `METRICS_TOKEN` di GitHub repository secrets dan persetujuan push ke `origin/main`.
