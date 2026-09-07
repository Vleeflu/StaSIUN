# Session Termination — StaSIUN

Berkas ini dikerjakan **di akhir setiap sesi**, sebelum percakapan ditutup. Tujuannya satu:
apa pun yang terjadi di sesi ini harus tersimpan di berkas, bukan di ingatan percakapan.
Sesi berikutnya dimulai dari nol dan hanya bisa membaca berkas.

Pasangannya adalah `session_initialization.md`.

---

## 1. Checklist akhir sesi

Dikerjakan berurutan. Nomor 1 sampai 4 wajib; nomor 5 adalah laporan ke Villyan.

### 1. Catat semua penyesuaian ke `ADJUSTMENT.md`

Setiap penyesuaian yang datang dari Villyan di sesi ini dicatat di sini — ini satu-satunya
tempatnya. Termasuk:

- perubahan arah atau lingkup produk,
- keputusan yang menyimpang dari PRD beserta alasannya,
- keputusan teknis yang mengikat pekerjaan berikutnya,
- temuan yang membatalkan asumsi lama.

Format satu entri:

| Bagian | Isi |
|---|---|
| Judul | Apa yang berubah, ditulis sebagai kalimat, bukan istilah |
| Tanggal | Tanggal keputusan diambil |
| Yang digantikan | Baris atau bagian mana di ADJUSTMENT yang jadi tidak berlaku |
| Kedudukan terhadap PRD | Sesuai PRD, memperjelas PRD, atau menyimpang dari PRD. Kalau menyimpang, tulis alasannya |
| Dampak | Berkas dan pekerjaan mana yang ikut berubah |

Kalau entri baru membatalkan entri lama, **jangan hapus yang lama** — tandai sebagai terjawab
atau dibatalkan, lalu tunjuk ke entri barunya. Riwayat keputusan itu sendiri berharga; enam hari
lagi tidak ada yang ingat kenapa sesuatu diputuskan begitu.

### 2. Selaraskan `OVERVIEW.md` dan `LAYER.md`

Keduanya adalah ringkasan turunan, jadi wajib dibuat cocok lagi dengan PRD + ADJUSTMENT sebelum
sesi ditutup. Caranya:

1. Ambil daftar penyesuaian sesi ini (hasil langkah 1).
2. Untuk tiap penyesuaian, tanya: apakah ini menyentuh isi `OVERVIEW.md` atau `LAYER.md`?
3. Kalau ya, perbarui berkasnya, dan sebutkan rujukan ke bagian ADJUSTMENT yang jadi dasarnya.
4. Terakhir, periksa sekilas: adakah kalimat di dua berkas itu yang sekarang bertentangan
   dengan PRD?

Pembagian isi keduanya: `OVERVIEW.md` menjawab **"produk ini apa"** (tujuan, data, cara kerja,
keluaran, batas lingkup). `LAYER.md` menjawab **"apa yang harus dibangun"** (per lapisan teknis:
data, ingest, AI, spasial, skor, tampilan). Kalau bingung sesuatu masuk mana: kalau juri atau
orang luar perlu tahu, itu OVERVIEW; kalau hanya yang menulis kode yang perlu tahu, itu LAYER.

### 3. Perbarui `PROGRESS.md`

- Status tiap pekerjaan sesi ini diperbarui.
- Blocker yang terbuka ditandai terbuka; blocker baru ditambahkan.
- Kalau rencana berubah, papan kerjanya ikut diubah, bukan cuma dicatat di ADJUSTMENT.
- Tambahkan satu baris ke Riwayat Milestone: tanggal, apa yang selesai.

### 4. Periksa `KNOWLEDGE.md` — bukan mengisinya dari nol

Bank pengetahuan **dicatat saat itu juga setiap kali kuis dijawab**, bukan di akhir sesi
(aturannya di `session_initialization.md` bagian 3.4). Jadi di sini tugasnya hanya memeriksa:

- Apakah semua kuis sesi ini sudah masuk ke Riwayat Kuis **dalam bentuk lengkap** (pertanyaan
  utuh, semua pilihan, jawaban benar, inti penjelasan), dan yang jawabannya benar sudah
  menaikkan status konsepnya? Kalau ada yang terlewat, susulkan sekarang.
- Adakah konsep yang dijelaskan panjang di sesi ini tetapi belum masuk bank? Konsep semacam itu
  dicatat dengan status `Dijelaskan`, tidak perlu menunggu ada kuisnya.
- Adakah hal yang Villyan kerjakan sendiri sampai berhasil di sesi ini — menjalankan migrasi,
  memperbaiki `.env`, membaca log error sampai ketemu penyebabnya? Itu juga pengetahuan nyata;
  catat dengan sumber "praktik langsung", tidak harus lewat kuis.

### 5. Laporan penutup ke Villyan

Ditulis di percakapan, singkat, lima poin:

1. **Selesai apa** di sesi ini.
2. **Berubah apa** — keputusan atau arah yang bergeser, dan di berkas mana tercatat.
3. **Blocker** yang masih menahan, dan mana yang paling mendesak.
4. **Langkah berikutnya** yang direncanakan untuk sesi depan.
5. **Yang dibutuhkan dari Villyan** sebelum sesi depan — data, kredensial, keputusan, atau
   tindakan manual.

---

## 2. Yang tidak dilakukan di akhir sesi

- **Jangan commit atau push** kecuali diminta. Perubahan dibiarkan di working tree.
- **Jangan menghapus catatan lama** di ADJUSTMENT hanya karena sudah tidak berlaku — tandai,
  jangan hapus.
- **Jangan menutup blocker tanpa bukti.** Blocker hanya ditandai terbuka kalau memang sudah
  diverifikasi, bukan karena sudah ada rencana untuk membukanya.
- **Jangan menulis status "berfungsi" untuk kode yang belum pernah dijalankan.** Pakai kata
  "ditulis, belum diuji" — itu status yang sah dan jujur.

---

## 3. Pemeriksaan cepat sebelum menutup

Empat pertanyaan. Kalau ada satu saja yang jawabannya "tidak", sesi belum boleh ditutup.

1. Apakah semua keputusan hari ini bisa ditemukan orang lain besok tanpa membaca percakapan ini?
2. Apakah `OVERVIEW.md` dan `LAYER.md` masih cocok dengan PRD + ADJUSTMENT?
3. Apakah `PROGRESS.md` mencerminkan keadaan sebenarnya, termasuk yang gagal dan yang terblokir?
4. Apakah Villyan tahu persis apa yang harus dia kerjakan sebelum sesi berikutnya?
