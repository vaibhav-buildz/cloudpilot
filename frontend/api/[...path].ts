import type { IncomingMessage, ServerResponse } from "http";
import {
  isPathSafe,
  isRouteAllowed,
  resolveVisitorId,
  sanitizeForwardHeaders,
  validateBodySizeAndType,
  validateQueryParams,
  validateUpstreamUrl,
  verifySameOrigin,
  MAX_BODY_BYTES,
} from "./_proxyHelper.js";

async function readBodyBuffer(
  req: IncomingMessage
): Promise<{ buffer: Buffer; exceeded: boolean }> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    let bytes = 0;
    let exceeded = false;

    req.on("data", (chunk: Buffer) => {
      bytes += chunk.length;
      if (bytes > MAX_BODY_BYTES) {
        exceeded = true;
        chunks.length = 0;
        return;
      }
      chunks.push(chunk);
    });

    req.on("end", () => {
      resolve({ buffer: Buffer.concat(chunks), exceeded });
    });

    req.on("error", (err) => {
      reject(err);
    });
    req.on("aborted", () => reject(new Error("Client disconnected")));
  });
}

export default async function handler(
  req: IncomingMessage,
  res: ServerResponse
): Promise<void> {
  res.setHeader("Cache-Control", "no-store");

  const method = (req.method || "GET").toUpperCase();

  // Validate upstream configuration
  const upstreamCheck = validateUpstreamUrl(process.env.BACKEND_URL);
  if (!upstreamCheck.valid || !upstreamCheck.url) {
    res.statusCode = 503;
    res.setHeader("Content-Type", "application/json");
    res.end(
      JSON.stringify({
        detail: "Backend service unconfigured or invalid protocol.",
      })
    );
    return;
  }
  const backendBaseUrl = upstreamCheck.url;

  const apiKey = process.env.CLOUDPILOT_API_KEY;
  if (!apiKey) {
    res.statusCode = 503;
    res.setHeader("Content-Type", "application/json");
    res.end(
      JSON.stringify({
        detail: "Proxy API key unconfigured on server.",
      })
    );
    return;
  }

  // Parse path and query
  const rawUrl = req.url || "/";
  let pathname: string;
  const queryObj: Record<string, string> = {};

  try {
    const parsed = new URL(rawUrl, "http://localhost");
    pathname = parsed.pathname;
    parsed.searchParams.forEach((val, key) => {
      queryObj[key] = val;
    });
  } catch {
    res.statusCode = 400;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ detail: "Malformed URL" }));
    return;
  }

  // Path sanitization
  if (!isPathSafe(pathname) || !isPathSafe(rawUrl)) {
    res.statusCode = 400;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ detail: "Invalid or unsafe path characters" }));
    return;
  }

  // Route allowlist
  if (!isRouteAllowed(method, pathname)) {
    res.statusCode = 404;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ detail: "Route not found or method not allowed" }));
    return;
  }

  // Query parameter validation
  const queryValidation = validateQueryParams(pathname, queryObj);
  if (!queryValidation.valid) {
    res.statusCode = 400;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ detail: "Invalid query parameters" }));
    return;
  }

  // Same-origin CSRF check for state-modifying methods
  if (method === "POST" || method === "DELETE") {
    const origin = req.headers["origin"] as string | undefined;
    const host = req.headers["host"] as string | undefined;
    if (!verifySameOrigin(origin, host)) {
      res.statusCode = 403;
      res.setHeader("Content-Type", "application/json");
      res.end(JSON.stringify({ detail: "Cross-origin request forbidden" }));
      return;
    }
  }

  // Request size and Content-Type validation
  const bodyCheck = validateBodySizeAndType(
    req.headers["content-length"],
    req.headers["content-type"] as string | undefined,
    method
  );
  if (!bodyCheck.valid) {
    res.statusCode = bodyCheck.status || 400;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ detail: bodyCheck.error }));
    return;
  }

  // Visitor scoping
  const { visitorId, isNew, setCookieHeader } = resolveVisitorId(
    req.headers["cookie"] as string | undefined
  );
  if (isNew && setCookieHeader) {
    res.setHeader("Set-Cookie", setCookieHeader);
  }

  // Forwarding headers
  const forwardHeaders = sanitizeForwardHeaders(req.headers, apiKey, visitorId);

  // Read request body for POST
  let bodyBuffer: Buffer | undefined;
  if (method === "POST") {
    try {
      const readResult = await readBodyBuffer(req);
      if (readResult.exceeded) {
        res.statusCode = 413;
        res.setHeader("Content-Type", "application/json");
        res.end(
          JSON.stringify({ detail: "Payload Too Large: maximum body is 5.5 MB" })
        );
        return;
      }
      bodyBuffer = readResult.buffer;
    } catch {
      res.statusCode = 400;
      res.setHeader("Content-Type", "application/json");
      res.end(JSON.stringify({ detail: "Failed reading request payload" }));
      return;
    }
  }

  const upstreamTarget = `${backendBaseUrl}${pathname}${queryValidation.sanitizedQuery || ""}`;

  // Upstream dispatch with 55s timeout
  const controller = new AbortController();
  const disconnect = () => controller.abort();
  res.once("close", disconnect);
  if (res.destroyed) disconnect();
  const timeoutTimer = setTimeout(() => {
    controller.abort();
  }, 55000);

  try {
    const upstreamRes = await fetch(upstreamTarget, {
      method,
      headers: forwardHeaders,
      body: bodyBuffer,
      signal: controller.signal,
    });
    res.statusCode = upstreamRes.status;
    const contentType = upstreamRes.headers.get("content-type");
    if (contentType) {
      res.setHeader("Content-Type", contentType);
    }
    const retryAfter = upstreamRes.headers.get("retry-after");
    if (retryAfter) {
      res.setHeader("Retry-After", retryAfter);
    }

    const resArrayBuffer = await upstreamRes.arrayBuffer();
    res.end(Buffer.from(resArrayBuffer));
  } catch (err: unknown) {
    if (res.destroyed) return;
    if (err instanceof Error && err.name === "AbortError") {
      res.statusCode = 504;
      res.setHeader("Content-Type", "application/json");
      res.end(
        JSON.stringify({
          detail: "The backend did not respond in time. If it was idle, wait for it to start and try again.",
        })
      );
      return;
    }

    res.statusCode = 502;
    res.setHeader("Content-Type", "application/json");
    res.end(
      JSON.stringify({ detail: "Bad Gateway: upstream service unavailable" })
    );
  } finally {
    clearTimeout(timeoutTimer);
    res.off("close", disconnect);
  }
}
