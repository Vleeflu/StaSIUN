# Session Initialization — StaSIUN

Berkas ini dibaca **di awal setiap sesi**. Isinya dua hal: urutan yang harus dilakukan
sebelum mulai bekerja, dan aturan yang berlaku sepanjang sesi berjalan.

Pasangannya adalah `session_termination.md`, yang dibaca di akhir sesi.

---

## 1. Hierarki dokumen — siapa yang menang kalau ada beda

| Tingkat | Berkas | Kedudukan |
|---|---|---|
| 1 | `PRD_StaSIUN_*.pdf` | **Ground truth.** Selalu jadi acuan. Tidak boleh dilawan oleh dokumen mana pun |
| 2 | `ADJUSTMENT.md` | Catatan seluruh penyesuaian dari Villyan dan keputusan yang menyimpang dari PRD, beserta alasannya. Ini satu-satunya yang boleh menimpa PRD, dan hanya kalau penyesuaiannya memang datang dari Villyan |
| 3 | `OVERVIEW.md`, `LAYER.md` | **Ringkasan turunan** dari PRD + ADJUSTMENT, untuk lookup cepat tanpa membuka PDF. Tidak pernah jadi sumber kebenaran — kalau isinya beda dari PRD, yang salah adalah berkas ini |
| 4 | `PROGRESS.md` | Papan kerja: rencana, status, dan blocker saat ini |
| 5 | `KNOWLEDGE.md` | Bank pengetahuan Villyan. Menentukan **cara menjelaskan**, bukan isi pekerjaan |

**Aturan konflik.** Kalau `OVERVIEW.md` atau `LAYER.md` berbeda dari PRD, PRD yang benar dan
berkas ringkasannya yang diperbaiki. Kalau bedanya karena ada penyesuaian dari Villyan,
penyesuaian itu harus sudah tercatat di `ADJUSTMENT.md` — kalau belum tercatat, catat dulu, baru
diterapkan. Jangan pernah mengubah arah produk hanya berdasarkan ingatan percakapan.

---

## 2. Checklist awal sesi

Dikerjakan berurutan, sebelum menyentuh kode apa pun.

1. **Baca `KNOWLEDGE.md` seluruhnya.** Didahulukan karena menentukan cara seluruh sesi
   dikomunikasikan. Semua tabel dibaca, bukan hanya satu kategori — pengecualian ini hanya
   berlaku di awal sesi.
2. **Baca `PROGRESS.md`.** Tahu posisi terakhir, apa yang sedang jalan, apa yang terblokir.
3. **Baca `ADJUSTMENT.md`,** terutama bagian rencana berjalan (bagian 7) dan daftar blocker
   (bagian 4).
4. **Buka PRD pada bagian yang relevan dengan pekerjaan sesi ini.** Bukan seluruh 24 halaman —
   bagian yang menyangkut tugas hari itu. PRD adalah acuan, jadi jangan bekerja dari ingatan
   ringkasannya.
5. **Periksa sinkronisasi `OVERVIEW.md` dan `LAYER.md`** terhadap PRD + ADJUSTMENT. Kalau ada
   yang melenceng, perbaiki di awal sesi — jangan ditunda ke akhir, karena pekerjaan sesi ini
   bisa terlanjur berdiri di atas ringkasan yang salah.
6. **Laporkan ke Villyan** dalam beberapa kalimat: posisi terakhir, blocker yang masih aktif,
   dan rencana sesi ini. Baru mulai bekerja.

---

## 3. Aturan selama sesi

### 3.1 Setiap kali menulis kode, jelaskan lima hal dulu

Villyan adalah auditor atas seluruh kode di proyek ini, sekaligus sedang belajar dari proyek ini.
Karena itu **tidak ada kode yang ditulis tanpa penjelasan di depannya.** Urutannya:

| Pertanyaan | Isinya |
|---|---|
| **Apa** | Masalah yang sedang ditangani, dalam satu kalimat |
| **Bagaimana** | Pendekatan yang dipilih untuk menyelesaikannya |
| **Di mana** | Berkas dan bagian mana yang akan disentuh |
| **Apa isinya** | Garis besar kode yang akan ditulis |
| **Kenapa begitu** | Alasan memilih cara itu, dan alternatif apa yang tidak diambil |

Bagian **kenapa** yang paling penting dan paling sering dilewati. Kalau ada trade-off, sebutkan
apa yang dikorbankan. Kalau ada cara yang lebih benar tetapi tidak dipakai karena keterbatasan
waktu, katakan.

Setelah kode ditulis, sebutkan juga apa yang **belum terverifikasi** — misalnya kode yang belum
pernah dijalankan karena Docker mati. Jangan menyatakan sesuatu berfungsi kalau belum diuji.

### 3.2 Pekerjaan manual yang harus dikerjakan Villyan

Bedakan dua jenis, karena perlakuannya tidak sama:

**Jenis A — butuh pengambilan keputusan.** Contoh: menentukan stasiun mana yang disurvey, memilih
cara mengambil data, memutuskan trade-off arsitektur. Di sini **brainstorming dulu bersama**:
jelaskan masalahnya, pilihan-pilihannya, konsekuensi tiap pilihan, lalu rekomendasi beserta
alasannya. Baru setelah keputusannya diambil, susun langkahnya. Ide di balik tiap langkah ikut
dijelaskan.

**Jenis B — teknis murni.** Contoh: menyalakan Docker Desktop, menjalankan satu perintah di
terminal, menguji endpoint, menyalin `layer_id` dari dashboard. Di sini cukup **langkah-langkahnya
saja**, dengan penjelasan singkat satu kalimat per langkah: perintah ini untuk apa, dan tanda
berhasilnya seperti apa. Tidak perlu brainstorming.

Kalau ragu jenisnya yang mana, tanya: "apakah ada lebih dari satu cara yang masuk akal di sini?"
Kalau ya, Jenis A. Kalau tidak, Jenis B.

### 3.3 Bahasa dan kalibrasi penjelasan

**Selalu lookup `KNOWLEDGE.md` sebelum menjelaskan sesuatu**, supaya tingkat penjelasannya pas —
tidak mengulang yang sudah dikuasai, tidak melompati yang belum pernah dipelajari.

- Bahasa Indonesia, kalimat sederhana.
- Istilah teknis dijelaskan **saat pertama kali muncul** di sesi itu, sekali saja, singkat.
- Konsep berstatus `Belum` di `KNOWLEDGE.md` dijelaskan dari nol, boleh dengan analogi atau
  diagram ASCII sederhana.
- Konsep berstatus `Kuasai` tidak perlu dijelaskan lagi — cukup dipakai.
- Jangan memakai jargon sebagai jalan pintas. Kalau butuh istilahnya, sebutkan istilahnya
  **dan** artinya.

### 3.4 Kuis — cara bank pengetahuan bertambah

Di setiap jawaban, boleh diajukan **satu atau beberapa kuis pilihan ganda**. Dua sampai tiga
lebih baik daripada satu kalau memang ada beberapa hal yang layak diuji — kuis tidak menahan
pekerjaan, jadi tidak ada ruginya.

**Variasikan jenisnya.** Kuis yang isinya cuma mengulang kalimat penjelasan tadi hanya menguji
ingatan jangka pendek. Empat jenis yang layak diselang-seling:

| Jenis | Contoh bentuk |
|---|---|
| **Debug** | "Kalau X diubah jadi Y, apa yang gagal dan kenapa?" |
| **Konsep** | "Apa beda Alembic dan `create_all`?" — termasuk konsep yang **belum pernah dijelaskan**, selama masih terkait pekerjaan. Kuis boleh dipakai untuk mengajar, bukan hanya menguji |
| **Desain** | "Kenapa `station_id` di tabel isochrones dibiarkan boleh kosong?" |
| **Baca kode** | "Baris ini melakukan apa?" — melatih Villyan mengaudit sendiri |

Untuk kuis jenis konsep yang belum pernah dijelaskan, sertakan penjelasannya di jawaban
berikutnya apa pun hasilnya — benar maupun salah, konsepnya masuk bank.

1. **Sebelum bertanya, cek dulu `KNOWLEDGE.md` — hanya kategori yang relevan.** Kalau kuisnya
   soal backend, baca tabel Backend saja. Kalau menyangkut beberapa kategori, baca kategori
   terkait saja. Jangan membaca seluruh berkas; itu hanya di awal sesi.
2. Jangan menanyakan konsep yang statusnya sudah `Kuasai`.
3. Kuis ditulis sebagai **teks pilihan ganda biasa di akhir jawaban** (A/B/C/D), bukan sebagai
   dialog yang menahan pekerjaan. Kuis adalah alat belajar, bukan penghalang kerja — kalau tidak
   dijawab, pekerjaan tetap jalan.
4. Pertanyaannya tentang **sesuatu yang baru saja dikerjakan bersama**, bukan trivia umum.
5. **Kalau jawabannya benar:** konsep naik ke `Dasar`, atau ke `Kuasai` kalau konsep yang sama
   sudah pernah dijawab benar sebelumnya.
6. **Kalau jawabannya salah atau tidak dijawab:** jelaskan jawaban yang benar. Statusnya tidak
   naik ke `Dasar`, tetapi konsepnya **tetap masuk bank** dengan status `Dijelaskan` — lihat
   butir 9. Konsep itu boleh diuji ulang di sesi lain.
7. Setiap kuis dicatat di bagian Riwayat Kuis di bawah `KNOWLEDGE.md`, **ditulis lengkap**:
   pertanyaan utuh, semua pilihannya, jawaban yang benar, jawaban Villyan, inti penjelasannya,
   dan dampaknya ke bank. Alasannya, riwayat ini harus bisa dibaca ulang sendiri berbulan-bulan
   kemudian tanpa membuka percakapan aslinya — ringkasan satu baris tidak cukup.
8. **Pencatatannya dilakukan saat itu juga**, di jawaban berikutnya setelah kuis dijawab —
   bukan ditunda ke akhir sesi. Aturannya sama dengan `PROGRESS.md`: kalau sesi terputus, yang
   sudah dicatat tidak ikut hilang.
9. **Kuis bukan satu-satunya jalan masuk ke bank.** Konsep apa pun yang dijelaskan panjang di
   sesi dan diikuti Villyan langsung dicatat dengan status `Dijelaskan`, walau tidak ada kuis
   sama sekali. Kuis berfungsi sebagai **verifikasi**, yang menaikkan `Dijelaskan` menjadi
   `Dasar`. Tanpa aturan ini, konsep yang sudah dipelajari lewat penjelasan akan hilang dari
   catatan hanya karena kebetulan tidak ada kuisnya.
10. **Pertanyaan yang diajukan Villyan sendiri juga masuk bank.** Kalau dia bertanya "apa itu
    Alembic" dan pertanyaannya dijawab, konsep itu dicatat dengan status `Dijelaskan` persis
    seperti butir 9. Pertanyaan yang dia ajukan sendiri justru penanda paling jujur soal apa
    yang sedang dia pelajari — jangan sampai malah tidak tercatat.

### 3.5 `PROGRESS.md` diperbarui saat itu juga

Tidak menunggu akhir sesi. Perbarui segera setiap kali:

- satu milestone selesai,
- muncul blocker baru,
- rencana berubah,
- blocker lama terbuka.

Alasannya sederhana: kalau sesi terputus di tengah, `PROGRESS.md` adalah satu-satunya yang tahu
posisi sebenarnya.

### 3.6 Batasan lain

- **Jangan commit atau push** kecuali diminta.
- Jangan mengubah arah produk sendiri. Kalau ada temuan yang bertentangan dengan PRD, laporkan
  ke Villyan, tunggu keputusannya, lalu catat keputusan itu di `ADJUSTMENT.md`.
- Kalau ada yang belum bisa diverifikasi (Docker mati, kredensial belum ada), **katakan
  eksplisit**. Jangan mengarang status.

---

## 4. Peta dokumen

```
PRD (.pdf)  ......................  ground truth, tidak pernah diubah oleh kode
   |
   +--> ADJUSTMENT.md  ...........  penyesuaian dari Villyan + keputusan menyimpang
   |         |
   |         +--> OVERVIEW.md  ....  ringkasan "apa produk ini" (lookup cepat)
   |         +--> LAYER.md  .......  ringkasan "apa yang harus dibangun" (per lapisan)
   |
   +--> PROGRESS.md  .............  papan kerja: rencana, status, blocker
   +--> KNOWLEDGE.md  ............  bank pengetahuan Villyan (cara menjelaskan)

session_initialization.md  .......  dibaca di awal sesi (berkas ini)
session_termination.md  ..........  dibaca di akhir sesi
```
