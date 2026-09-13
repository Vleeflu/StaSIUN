const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

async function readError(res: Response, path: string): Promise<Error> {
  try {
    const payload: unknown = await res.json();
    if (
      payload &&
      typeof payload === "object" &&
      "detail" in payload &&
      typeof payload.detail === "string"
    ) {
      return new Error(payload.detail);
    }
  } catch {
  }

  return new Error(`Request ${path} gagal (${res.status})`);
}

/**
 * Alamat lengkap satu endpoint API.
 *
 * Dipakai untuk tautan yang dibuka langsung di tab baru, seperti dokumen
 * ekspor, yang tidak lewat `apiGet` sehingga tidak kebagian awalan `/api`.
 *
 * Sebelum ada fungsi ini, `EksporModal` menyusun alamatnya sendiri dan
 * awalannya tertinggal, sehingga tombol ekspor membalas `{"detail":"Not
 * Found"}` - dan gejalanya terlihat seperti endpoint yang belum dibuat,
 * padahal endpointnya sehat dan hanya alamatnya yang kurang empat huruf.
 */
export function urlApi(path: string): string {
  return `${BASE_URL}/api${path}`;
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(urlApi(path), { cache: "no-store" });
  if (!res.ok) throw await readError(res, path);
  return res.json() as Promise<T>;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(urlApi(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw await readError(res, path);
  return res.json() as Promise<T>;
}

/**
 * Alamat foto survei yang pasti bisa ditampilkan browser.
 *
 * Foto HEIC - bawaan kamera iPhone, 76 di antara foto Activity - hanya bisa
 * ditampilkan Safari. Yang berformat itu dilewatkan endpoint konversi di
 * backend; sisanya memakai URL aslinya langsung, supaya ribuan foto yang sudah
 * bisa ditampilkan tidak ikut disalurkan lewat server kita tanpa alasan.
 */
export function urlFoto(url: string): string {
  if (!/\.hei[cf](\?|$)/i.test(url)) return url;
  return `${BASE_URL}/foto?url=${encodeURIComponent(url)}`;
}
