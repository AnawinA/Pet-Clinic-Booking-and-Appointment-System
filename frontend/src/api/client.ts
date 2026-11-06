const TOKEN_KEY = "petcare.access_token";
const API_BASE = "/api/v1";

export class ApiError extends Error {
  status: number;
  code: string;
  details: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details: Record<string, unknown>) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export const tokenStore = {
  get(): string | null {
    return localStorage.getItem(TOKEN_KEY);
  },
  set(token: string | null): void {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  },
};

const etagCache = new Map<string, { etag: string; data: unknown }>();

function headersFor(body?: unknown, extra?: HeadersInit): Headers {
  const headers = new Headers(extra);
  if (body !== undefined) headers.set("Content-Type", "application/json");
  const token = tokenStore.get();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return headers;
}

async function parse<T>(response: Response): Promise<T> {
  const text = await response.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text;
    }
  }
  if (!response.ok) {
    if (response.status === 401) {
      tokenStore.set(null);
      window.dispatchEvent(new Event("petcare:unauthorized"));
    }
    const error = (
      payload as { error?: { code?: string; message?: string; details?: Record<string, unknown> } } | null
    )?.error;
    throw new ApiError(
      response.status,
      error?.code ?? "ERROR",
      error?.message ?? "เกิดข้อผิดพลาดในการเชื่อมต่อ",
      error?.details ?? {},
    );
  }
  return payload as T;
}

export async function apiGet<T>(path: string, useEtag = false): Promise<T> {
  const cached = useEtag ? etagCache.get(path) : undefined;
  const response = await fetch(`${API_BASE}${path}`, {
    headers: headersFor(undefined, cached ? { "If-None-Match": cached.etag } : undefined),
    cache: "no-store",
  });
  if (response.status === 304 && cached) return cached.data as T;
  const data = await parse<T>(response);
  const etag = response.headers.get("ETag");
  if (etag) etagCache.set(path, { etag, data });
  return data;
}

export async function apiSend<T>(
  path: string,
  method: "POST" | "PATCH" | "DELETE",
  body?: unknown,
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers: headersFor(body),
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return parse<T>(response);
}

export async function apiUpload<T>(path: string, file: File): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: headersFor(),
    body: form,
  });
  return parse<T>(response);
}

export async function apiBlob(path: string): Promise<Blob> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: headersFor(),
    cache: "no-store",
  });
  if (!response.ok) {
    await parse<never>(response);
    throw new Error("ไม่สามารถโหลดรูปได้");
  }
  return response.blob();
}

export function fieldErrors(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError)) return {};
  const fields = (error.details as { fields?: { loc: string[]; msg: string }[] }).fields ?? [];
  const result: Record<string, string> = {};
  for (const field of fields) {
    const key = field.loc[field.loc.length - 1];
    if (key) result[key] = field.msg;
  }
  return result;
}
