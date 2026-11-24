import crypto from "crypto";

export const MAX_BODY_BYTES = 5.5 * 1024 * 1024; // 5.5 MB

const UUID4_REGEX =
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function isValidUuid4(val?: string | null): boolean {
  if (!val || typeof val !== "string" || val.length !== 36) {
    return false;
  }
  return UUID4_REGEX.test(val);
}

export function validateUpstreamUrl(url?: string): {
  valid: boolean;
  error?: string;
  url?: string;
} {
  if (!url || typeof url !== "string") {
    return { valid: false, error: "BACKEND_URL environment variable is missing" };
  }
  const trimmed = url.trim().replace(/\/+$/, "");
  try {
    const parsed = new URL(trimmed);
    const isLocal =
      parsed.hostname === "localhost" ||
      parsed.hostname === "127.0.0.1" ||
      parsed.hostname === "0.0.0.0";
    if (!isLocal && parsed.protocol !== "https:") {
      return {
        valid: false,
        error: "BACKEND_URL must use HTTPS protocol in production",
      };
    }
    return { valid: true, url: trimmed };
  } catch {
    return { valid: false, error: "BACKEND_URL is not a valid URL" };
  }
}

export function isPathSafe(rawPath: string): boolean {
  if (!rawPath || typeof rawPath !== "string") return false;
  const decoded = decodeURIComponent(rawPath);
  if (
    rawPath.includes("..") ||
    rawPath.includes("\\") ||
    rawPath.includes("//") ||
    decoded.includes("..") ||
    decoded.includes("\\") ||
    decoded.includes("//") ||
    /%2f/i.test(rawPath) ||
    /%5c/i.test(rawPath)
  ) {
    return false;
  }
  return true;
}

export function isRouteAllowed(method: string, path: string): boolean {
  const normMethod = method.toUpperCase();
  const normPath = path.replace(/\/+$/, "");

  if (normMethod === "GET") {
    if (normPath === "/api/limits" || normPath === "/api/methods") return true;
    if (normPath === "/api/runs") return true;
    const runMatch = normPath.match(/^\/api\/runs\/([0-9a-fA-F-]{36})$/);
    if (runMatch && isValidUuid4(runMatch[1])) return true;
  } else if (normMethod === "POST") {
    if (normPath === "/api/simulate" || normPath === "/api/simulate/csv")
      return true;
  } else if (normMethod === "DELETE") {
    const runMatch = normPath.match(/^\/api\/runs\/([0-9a-fA-F-]{36})$/);
    if (runMatch && isValidUuid4(runMatch[1])) return true;
  }

  return false;
}

export function validateQueryParams(
  path: string,
  query: Record<string, string | string[] | undefined>
): { valid: boolean; sanitizedQuery?: string } {
  const keys = Object.keys(query);
  const normPath = path.replace(/\/+$/, "");

  if (normPath === "/api/runs") {
    for (const key of keys) {
      if (key !== "limit" && key !== "offset") {
        return { valid: false };
      }
      const val = query[key];
      if (val === undefined) continue;
      const strVal = Array.isArray(val) ? val[0] : val;
      if (!/^\d+$/.test(strVal)) {
        return { valid: false };
      }
    }
    const params = new URLSearchParams();
    if (query["limit"] !== undefined) {
      const v = Array.isArray(query["limit"]) ? query["limit"][0] : query["limit"];
      params.set("limit", v);
    }
    if (query["offset"] !== undefined) {
      const v = Array.isArray(query["offset"]) ? query["offset"][0] : query["offset"];
      params.set("offset", v);
    }
    const qs = params.toString();
    return { valid: true, sanitizedQuery: qs ? `?${qs}` : "" };
  }

  // Any other route does NOT accept query params
  if (keys.length > 0) {
    return { valid: false };
  }
  return { valid: true, sanitizedQuery: "" };
}

export function parseCookies(cookieHeader?: string): Record<string, string> {
  const map: Record<string, string> = {};
  if (!cookieHeader) return map;
  const parts = cookieHeader.split(";");
  for (const p of parts) {
    const [k, ...v] = p.trim().split("=");
    if (k) {
      map[k.trim()] = v.join("=").trim();
    }
  }
  return map;
}

export function resolveVisitorId(cookieHeader?: string): {
  visitorId: string;
  isNew: boolean;
  setCookieHeader?: string;
} {
  const cookies = parseCookies(cookieHeader);
  const currentVid = cookies["cp_vid"];
  if (isValidUuid4(currentVid)) {
    return { visitorId: currentVid.toLowerCase(), isNew: false };
  }

  const newVid = crypto.randomUUID();
  const setCookieHeader = `cp_vid=${newVid}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=31536000`;
  return { visitorId: newVid, isNew: true, setCookieHeader };
}

export function verifySameOrigin(
  originHeader?: string,
  hostHeader?: string
): boolean {
  if (!originHeader) {
    return true; // Non-browser or direct
  }
  try {
    const originUrl = new URL(originHeader);
    if (!hostHeader) return false;
    const hostName = hostHeader.split(":")[0];
    const originHostName = originUrl.hostname;

    if (
      (originHostName === "localhost" || originHostName === "127.0.0.1") &&
      (hostName === "localhost" || hostName === "127.0.0.1")
    ) {
      return true;
    }
    return originUrl.host.toLowerCase() === hostHeader.toLowerCase();
  } catch {
    return false;
  }
}

export function sanitizeForwardHeaders(
  incomingHeaders: Record<string, string | string[] | undefined>,
  apiKey: string,
  visitorId: string
): Record<string, string> {
  const forwarded: Record<string, string> = {
    "X-API-Key": apiKey,
    "X-Visitor-Id": visitorId,
  };

  const allowedToForward = ["content-type", "accept", "content-length"];
  for (const [key, val] of Object.entries(incomingHeaders)) {
    const lowerKey = key.toLowerCase();
    if (allowedToForward.includes(lowerKey) && val !== undefined) {
      forwarded[lowerKey] = Array.isArray(val) ? val[0] : val;
    }
  }

  return forwarded;
}

export function validateBodySizeAndType(
  contentLength?: string | number,
  contentType?: string,
  method?: string
): { valid: boolean; status?: number; error?: string } {
  if (contentLength !== undefined) {
    const len =
      typeof contentLength === "number"
        ? contentLength
        : parseInt(contentLength, 10);
    if (!isNaN(len) && len > MAX_BODY_BYTES) {
      return {
        valid: false,
        status: 413,
        error: "Payload Too Large: maximum request body is 5.5 MB",
      };
    }
  }

  if (method?.toUpperCase() === "POST") {
    if (!contentType) {
      return {
        valid: false,
        status: 415,
        error: "Unsupported Media Type: Content-Type header is required for POST",
      };
    }
    const lowerType = contentType.toLowerCase();
    const isJson = lowerType.startsWith("application/json");
    const isMultipart = lowerType.startsWith("multipart/form-data");
    if (!isJson && !isMultipart) {
      return {
        valid: false,
        status: 415,
        error:
          "Unsupported Media Type: only application/json and multipart/form-data are allowed",
      };
    }
  }

  return { valid: true };
}
