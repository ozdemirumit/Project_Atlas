const configuredCsrfCookieName: unknown = import.meta.env.VITE_ATLAS_CSRF_COOKIE_NAME;
const configuredCsrfHeaderName: unknown = import.meta.env.VITE_ATLAS_CSRF_HEADER_NAME;
const CSRF_COOKIE_NAME =
  typeof configuredCsrfCookieName === "string" ? configuredCsrfCookieName : "atlas_csrf";
const CSRF_HEADER_NAME =
  typeof configuredCsrfHeaderName === "string" ? configuredCsrfHeaderName : "X-CSRF-Token";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

export class ApiRequestError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

function readCookie(name: string): string | null {
  const prefix = `${encodeURIComponent(name)}=`;
  for (const item of document.cookie.split(";")) {
    const candidate = item.trim();
    if (candidate.startsWith(prefix)) {
      return decodeURIComponent(candidate.slice(prefix.length));
    }
  }
  return null;
}

export async function apiFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<Response> {
  const requestUrl = input instanceof Request ? input.url : input.toString();
  const resolvedUrl = new URL(requestUrl, window.location.origin);
  if (resolvedUrl.origin !== window.location.origin) {
    throw new ApiRequestError("Cross-origin API requests are not allowed", 0);
  }
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  if (!SAFE_METHODS.has(method)) {
    const csrfToken = readCookie(CSRF_COOKIE_NAME);
    if (csrfToken) headers.set(CSRF_HEADER_NAME, csrfToken);
  }
  return fetch(input, { ...init, credentials: "same-origin", headers });
}
