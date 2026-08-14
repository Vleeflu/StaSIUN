const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}/api${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Request ${path} gagal (${res.status})`);
  return res.json() as Promise<T>;
}