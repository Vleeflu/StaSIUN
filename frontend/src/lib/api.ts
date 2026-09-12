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

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}/api${path}`, { cache: "no-store" });
  if (!res.ok) throw await readError(res, path);
  return res.json() as Promise<T>;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}/api${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw await readError(res, path);
  return res.json() as Promise<T>;
}
