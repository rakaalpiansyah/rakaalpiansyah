# Desain Sistem Telemetri GitHub Realtime & Streak

Tanggal: 2026-11-27
Repo: `rakaalpiansyah/rakaalpiansyah`
Target utama: `assets/telemetry-3d.svg` dan workflow `.github/workflows/`

## Tujuan dan Latar Belakang

Kartu `assets/telemetry-3d.svg` di `README.md` saat ini berisi data statis sejak 10 November 2026: kontur 3D kontribusi 52 minggu, persentase bahasa, jumlah proyek (`56 Projects`), dan total commit (`1,400+ Commits`) seluruhnya hardcoded. Sementara itu, workflow `.github/workflows/generate-animation.yml` berjalan setiap hari hanya untuk memperbarui folder `profile-3d-contrib/` yang tidak lagi direferensikan di `README.md`. Angka pada panel bahasa kanan (`17+20+9+5+15+7 = 73`) juga tidak konsisten dengan kartu bawah (`56 Projects`), dan belum ada metrik streak kontribusi.

Perubahan ini menjadikan `assets/telemetry-3d.svg` diperbarui secara otomatis dari data aktual GitHub (Public + Private) termasuk statistik streak, dengan tetap menjaga estetika Midnight Slate dan Sky-Blue 3D pada `README.md`.

## Goals

1. **3D Isometric Contribution Terrain Live (52 Minggu)**
   Merender langsung grafik kontribusi 52 minggu berbentuk balok isometrik 3D menggunakan Python tanpa dependensi pihak ketiga, mempertahankan palet Midnight Slate dan Sky-Blue (`#0b0f17`, `#0f172a`, `#162032`, `#0284c7`, `#0ea5e9`, `#38bdf8`) lengkap dengan animasi SMIL grow-in serta total kontribusi 52 minggu di legend kiri bawah.
2. **Distribusi Bahasa Public + Private yang Proporsional**
   Mengambil seluruh bahasa dari repo milik user (`ownerAffiliations: [OWNER]`, `isFork: false`) baik public maupun private, lalu menormalkan bobot per repo (setiap repo berbobot `1.0` yang dibagi sesuai proporsi byte bahasa kode non-markup). Langkah ini mencegah outlier ukuran file besar (misalnya `chess-arena-learn` dengan sekitar 1,47 GB C/C++) menenggelamkan Python, Java/Kotlin, PHP/Laravel, Dart, maupun JavaScript/TypeScript. Jumlah repo pada setiap baris kategori dihitung sebagai jumlah repo unik yang menggunakan kategori tersebut.
3. **Strip 4 Kartu Bawah Live dengan Streak**
   Memperbarui keempat kartu di bagian bawah SVG menggunakan data GraphQL live:
   - Kartu 1: `TOTAL CONTRIBUTIONS` (total kontribusi all-time dari tahun `createdAt` hingga tahun berjalan, misalnya `1,542 Total` dan label `ALL-TIME`).
   - Kartu 2: `TOTAL REPOSITORIES` (jumlah repo owned non-fork, misalnya `55 Projects` dan rincian `50 PUB · 5 PRIV`).
   - Kartu 3: `CURRENT STREAK` (jumlah hari aktif beruntun di zona `Asia/Jakarta` UTC+7 dengan grace period hari berjalan, serta rentang tanggal, misalnya `112 Days` dan `AUG 8 - NOW`).
   - Kartu 4: `LONGEST STREAK` (rekor streak terpanjang all-time beserta jumlah hari aktif dalam 52 minggu terakhir, misalnya `112 Days` dan `229 ACTIVE DAYS`).
4. **Indikator Sinkronisasi Header**
   Menambahkan label ringkas di pojok kanan atas header (`SYNCED <MON DD> · <HH:MM> WIB`) untuk menunjukkan waktu pembaruan terakhir.
5. **Otomatisasi GitHub Actions dengan Secret PAT**
   Menjalankan skrip generator melalui GitHub Actions setiap 3 jam (`0 */3 * * *`), via `workflow_dispatch`, serta saat skrip atau workflow berubah, menggunakan secret `METRICS_TOKEN` (PAT dengan scope `repo` dan `read:user`).
6. **Pembersihan Aset Lama**
   Menghapus langkah `yoshi389111/github-profile-3d-contrib` yang tidak dipakai lagi beserta folder `profile-3d-contrib/` (~2,4 MB) dari repositori.

## Non-Goals

- Tidak mengubah aset SVG profil lain (`hero-3d.svg`, `architecture-3d.svg`, `proj-1` sampai `proj-6`, `experience-3d.svg`, `btn-*.svg`) maupun struktur dan tata letak `README.md`.
- Tidak membangun backend, serverless function, atau layanan hosting eksternal (Vercel, Cloudflare Workers, dan sejenisnya).

## Anti-Goals

- Menghitung persentase bahasa dari byte mentah global yang menghasilkan angka bias (`C++ 86%`, `Python 0%`).
- Diam-diam fallback ke `GITHUB_TOKEN` bawaan ketika `METRICS_TOKEN` kosong, karena akan menimpa kartu dengan angka publik yang menyusut; workflow harus gagal dengan pesan error yang jelas.
- Melakukan commit otomatis setiap 3 jam ketika data metrik tidak berubah, atau menulis author commit memakai akun pribadi sehingga mengacaukan perhitungan streak asli.
- Teks terpotong/overflow, karakter XML yang tidak di-escape, atau perubahan dimensi `viewBox="0 0 1200 540"`.

## Constraints

- **Python 3 Standard Library Only**: Skrip hanya boleh memakai modul bawaan Python (`urllib.request`, `json`, `datetime`, `zoneinfo`, `hashlib`, `xml.sax.saxutils`, `argparse`, dan sejenisnya) tanpa `pip install`.
- **Pagination GraphQL Penuh**: Query `repositories` wajib menggunakan cursor pagination (`after`) agar tetap akurat jika jumlah repo melewati 100.
- **Riwayat Kontribusi All-Time**: Query `contributionsCollection` mencakup setiap tahun dari tahun `createdAt` (2023) hingga tahun berjalan untuk mendapatkan total kontribusi dan longest streak all-time yang akurat.
- **Zona Waktu dan Grace Period Streak**: Batas pergantian hari mengikuti `Asia/Jakarta` (UTC+7). Jika pada hari berjalan kontribusi masih `0`, perhitungan `CURRENT STREAK` mundur mulai kemarin sehingga streak tidak mendadak putus sebelum commit hari tersebut dilakukan.
- **Deteksi Perubahan Berbasis Hash**: SVG menyertakan komentar `<!-- telemetry-hash: <sha256> -->` yang dihitung dari data metrik kanonis tanpa timestamp sinkronisasi. Jika hash sama dengan file `assets/telemetry-3d.svg` yang sudah ada (dan flag `--force` tidak diberikan), skrip melewati penulisan ulang file sehingga bot tidak membuat commit kosong.
- **Identitas Commit Bot**: Workflow commit menggunakan `github-actions[bot]` (`github-actions[bot]@users.noreply.github.com`) pada branch `main`.

## Pendekatan yang Dipertimbangkan

1. **Skrip Python Mandiri + GitHub Actions Terjadwal (Dipilih)**
   Satu skrip Python di repo memanggil GitHub GraphQL API memakai `METRICS_TOKEN`, menghitung semua metrik (terrain 52 minggu, bahasa ter-normalisasi, repo, all-time contributions, current dan longest streak), lalu merender ulang `assets/telemetry-3d.svg`. GitHub Actions menjadwalkannya tiap 3 jam dan melakukan commit hanya saat hash data berubah.
   - Trade-off: Pembaruan mengikuti interval cron 3 jam dan menghasilkan commit bot saat ada aktivitas baru, namun 100% gratis, bebas downtime/cold start eksternal, aman menyimpan PAT di GitHub Secrets sendiri, dan visualnya identik dengan tema saat ini.
2. **Serverless Live SVG Endpoint (Vercel / Cloudflare Workers)**
   Menyajikan SVG dinamis dari URL eksternal yang dipanggil `README.md`.
   - Trade-off: Pembaruan lebih cepat (menitan) tanpa commit bot, tetapi memerlukan hosting terpisah, menyimpan PAT di pihak ketiga, rentan error/cold start saat profil dibuka, dan tetap terkena cache proxy gambar GitHub (Camo).
3. **Hybrid dengan `github-profile-3d-contrib`**
   Mempertahankan action pihak ketiga untuk menggambar terrain 3D lalu memodifikasi hasil SVG-nya di Python.
   - Trade-off: Rentan rusak jika markup action pihak ketiga berubah, tetap menyisakan folder `profile-3d-contrib/` yang besar, dan tetap membutuhkan skrip GraphQL terpisah untuk bahasa dan streak.

Pendekatan 1 dipilih karena paling stabil, ringan dirawat, tanpa ketergantungan layanan eksternal, dan memberi kendali penuh atas tampilan SVG.

## Keputusan dan Default

Keputusan yang sudah disepakati bersama:
- Cakupan data meliputi repo dan kontribusi public serta private melalui PAT di GitHub Secrets.
- Distribusi bahasa menggunakan normalisasi proporsional per repo.
- Strip bawah memakai 4 kartu live dengan mengganti dua kartu kanan menjadi `CURRENT STREAK` dan `LONGEST STREAK`.
- Arsitektur menggunakan skrip Python mandiri dan GitHub Actions terjadwal (Pendekatan 1).

Default teknis yang ditetapkan (dapat disesuaikan bila perlu):
- Jadwal cron workflow: setiap 3 jam (`0 */3 * * *`).
- Nama secret repository: `METRICS_TOKEN`.
- Pembersihan aset lama: menghapus folder `profile-3d-contrib/` dan menghentikan action `github-profile-3d-contrib`.
- Kategori bahasa kode: mengecualikan bahasa markup/konfigurasi (seperti HTML, CSS, SCSS, Makefile, Dockerfile) dari 6 grup bahasa utama (`Python & AI`, `Java & Kotlin`, `PHP & Laravel`, `JavaScript & TypeScript`, `Dart & Flutter`, serta `Systems (C++/C/Go/Shell)`).
- Zona waktu perhitungan hari streak dan label waktu update: `Asia/Jakarta` (UTC+7).
- Deduplikasi commit: melewati penulisan file jika `telemetry-hash` metrik tidak berubah.

## Bagian yang Diserahkan ke Implementer

- Rumus skala tinggi balok 3D isometrik agar tetap proporsional terhadap nilai puncak kontribusi 52 minggu tanpa keluar dari area `clipPath`.
- Detail koordinat SVG, lebar progress bar, serta XML escaping untuk 6 baris bahasa dan 4 kartu strip bawah.
- Struktur modul `scripts/generate_telemetry.py` dan cakupan unit test `tests/test_generate_telemetry.py` untuk logika streak (grace period, pergantian tahun, rekor all-time), normalisasi bahasa, escaping SVG, dan perbandingan hash.
- Verifikasi lokal menggunakan data live via `gh` serta instruksi ringkas konfigurasi `METRICS_TOKEN` di GitHub repository secrets.
