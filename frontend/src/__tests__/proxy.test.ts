import fs from "fs";
import path from "path";
import ts from "typescript";
import { describe, expect, it } from "vitest";
import {
  isPathSafe,
  isRouteAllowed,
  isValidUuid4,
  parseCookies,
  resolveVisitorId,
  sanitizeForwardHeaders,
  validateBodySizeAndType,
  validateQueryParams,
  validateUpstreamUrl,
  verifySameOrigin,
} from "../../api/_proxyHelper";

it("resolves Vercel handler imports under native Node ESM rules", () => {
  const program = ts.createProgram([path.resolve("api/[...path].ts")], {
    module: ts.ModuleKind.NodeNext,
    target: ts.ScriptTarget.ES2022,
    strict: true,
    noEmit: true,
    skipLibCheck: true,
  });
  const diagnostics = ts.getPreEmitDiagnostics(program).map((diagnostic) =>
    ts.flattenDiagnosticMessageText(diagnostic.messageText, "\n")
  );
  expect(diagnostics).toEqual([]);
});

describe("Proxy Helper: Route Allowlist", () => {
  it("allows permitted GET routes", () => {
    expect(isRouteAllowed("GET", "/api/limits")).toBe(true);
    expect(isRouteAllowed("GET", "/api/methods")).toBe(true);
    expect(isRouteAllowed("GET", "/api/runs")).toBe(true);
    expect(
      isRouteAllowed(
        "GET",
        "/api/runs/a0000000-0000-4000-8000-000000000001"
      )
    ).toBe(true);
  });

  it("allows permitted POST routes", () => {
    expect(isRouteAllowed("POST", "/api/simulate")).toBe(true);
    expect(isRouteAllowed("POST", "/api/simulate/csv")).toBe(true);
  });

  it("allows permitted DELETE routes", () => {
    expect(
      isRouteAllowed(
        "DELETE",
        "/api/runs/a0000000-0000-4000-8000-000000000001"
      )
    ).toBe(true);
  });

  it("rejects unauthorized routes and methods", () => {
    expect(isRouteAllowed("GET", "/api/admin")).toBe(false);
    expect(isRouteAllowed("POST", "/api/runs")).toBe(false);
    expect(isRouteAllowed("DELETE", "/api/simulate")).toBe(false);
    expect(isRouteAllowed("PUT", "/api/simulate")).toBe(false);
    expect(isRouteAllowed("GET", "/api/runs/invalid-uuid")).toBe(false);
    expect(isRouteAllowed("DELETE", "/api/runs/not-a-uuid")).toBe(false);
  });
});

describe("Proxy Helper: Path Sanitization", () => {
  it("accepts clean canonical paths", () => {
    expect(isPathSafe("/api/limits")).toBe(true);
    expect(isPathSafe("/api/runs/123e4567-e89b-42d3-a456-426614174000")).toBe(
      true
    );
  });

  it("rejects path traversal and directory separators", () => {
    expect(isPathSafe("/api/../secret")).toBe(false);
    expect(isPathSafe("/api/%2e%2e/secret")).toBe(false);
    expect(isPathSafe("/api/runs/..")).toBe(false);
    expect(isPathSafe("/api//limits")).toBe(false);
    expect(isPathSafe("/api\\limits")).toBe(false);
    expect(isPathSafe("/api/%2f/limits")).toBe(false);
    expect(isPathSafe("/api/%5c/limits")).toBe(false);
  });
});

describe("Proxy Helper: Query Parameter Validation", () => {
  it("allows integer limit and offset on /api/runs", () => {
    const res = validateQueryParams("/api/runs", {
      limit: "10",
      offset: "20",
    });
    expect(res.valid).toBe(true);
    expect(res.sanitizedQuery).toBe("?limit=10&offset=20");
  });

  it("rejects non-digit query parameters on /api/runs", () => {
    expect(
      validateQueryParams("/api/runs", { limit: "10; DROP TABLE" }).valid
    ).toBe(false);
    expect(validateQueryParams("/api/runs", { limit: "abc" }).valid).toBe(
      false
    );
    expect(validateQueryParams("/api/runs", { other: "foo" }).valid).toBe(
      false
    );
  });

  it("rejects query parameters on endpoints that do not accept them", () => {
    expect(
      validateQueryParams("/api/limits", { foo: "bar" }).valid
    ).toBe(false);
    expect(
      validateQueryParams("/api/simulate", { debug: "true" }).valid
    ).toBe(false);
  });
});

describe("Proxy Helper: Header Sanitization and Injection", () => {
  it("strips client-supplied security headers and injects server credentials", () => {
    const clientHeaders = {
      "x-api-key": "evil-client-key",
      authorization: "Bearer evil-token",
      "x-visitor-id": "spoofed-uuid",
      host: "cloudpilot.vercel.app",
      cookie: "session=123",
      "content-type": "application/json",
      accept: "application/json",
    };

    const forwarded = sanitizeForwardHeaders(
      clientHeaders,
      "server-secret-key-12345",
      "valid-visitor-uuid-4"
    );

    expect(forwarded["X-API-Key"]).toBe("server-secret-key-12345");
    expect(forwarded["X-Visitor-Id"]).toBe("valid-visitor-uuid-4");
    expect(forwarded["content-type"]).toBe("application/json");
    expect(forwarded["accept"]).toBe("application/json");
    expect(forwarded["authorization"]).toBeUndefined();
    expect(forwarded["cookie"]).toBeUndefined();
    expect(forwarded["host"]).toBeUndefined();
  });
});

describe("Proxy Helper: Cookie and Visitor Scoping", () => {
  it("parses cookies accurately", () => {
    const parsed = parseCookies("cp_vid=test-uuid; other=value; foo=bar");
    expect(parsed["cp_vid"]).toBe("test-uuid");
    expect(parsed["other"]).toBe("value");
    expect(parsed["foo"]).toBe("bar");
  });

  it("preserves an existing valid UUID4 cookie", () => {
    const existingUuid = "c0000000-0000-4000-8000-000000000001";
    const res = resolveVisitorId(`cp_vid=${existingUuid}`);
    expect(res.visitorId).toBe(existingUuid);
    expect(res.isNew).toBe(false);
    expect(res.setCookieHeader).toBeUndefined();
  });

  it("generates a new UUID4 and sets cookie if missing or invalid", () => {
    const resMissing = resolveVisitorId(undefined);
    expect(isValidUuid4(resMissing.visitorId)).toBe(true);
    expect(resMissing.isNew).toBe(true);
    expect(resMissing.setCookieHeader).toContain(
      `cp_vid=${resMissing.visitorId}; Path=/; HttpOnly; Secure; SameSite=Lax`
    );

    const resInvalid = resolveVisitorId("cp_vid=not-a-uuid-format");
    expect(isValidUuid4(resInvalid.visitorId)).toBe(true);
    expect(resInvalid.isNew).toBe(true);
  });
});

describe("Proxy Helper: CSRF Same-Origin Verification", () => {
  it("allows matching origin and host", () => {
    expect(
      verifySameOrigin("https://cloudpilot.vercel.app", "cloudpilot.vercel.app")
    ).toBe(true);
    expect(
      verifySameOrigin("http://localhost:5173", "localhost:5173")
    ).toBe(true);
  });

  it("rejects mismatched origin and host", () => {
    expect(
      verifySameOrigin("https://evil.com", "cloudpilot.vercel.app")
    ).toBe(false);
  });
});

describe("Proxy Helper: Upstream URL and Body Validation", () => {
  it("validates upstream URLs strictly", () => {
    expect(validateUpstreamUrl("https://api.example.com").valid).toBe(true);
    expect(validateUpstreamUrl("http://localhost:8000").valid).toBe(true);
    expect(validateUpstreamUrl("http://insecure-backend.com").valid).toBe(
      false
    );
    expect(validateUpstreamUrl("").valid).toBe(false);
  });

  it("enforces 5.5 MB payload limit and Content-Type restrictions", () => {
    const validJson = validateBodySizeAndType(
      1024,
      "application/json",
      "POST"
    );
    expect(validJson.valid).toBe(true);

    const validMultipart = validateBodySizeAndType(
      2048,
      "multipart/form-data; boundary=---123",
      "POST"
    );
    expect(validMultipart.valid).toBe(true);

    const oversized = validateBodySizeAndType(
      6 * 1024 * 1024,
      "application/json",
      "POST"
    );
    expect(oversized.valid).toBe(false);
    expect(oversized.status).toBe(413);

    const invalidType = validateBodySizeAndType(
      100,
      "text/plain",
      "POST"
    );
    expect(invalidType.valid).toBe(false);
    expect(invalidType.status).toBe(415);
  });

  it("configures vercel.json function maxDuration >= SIM_TIMEOUT_SECONDS + margin", () => {
    const vercelConfigPath = path.resolve(__dirname, "../../vercel.json");
    const vercelConfig = JSON.parse(fs.readFileSync(vercelConfigPath, "utf-8"));
    const maxDuration = vercelConfig?.functions?.["api/[...path].ts"]?.maxDuration;
    expect(maxDuration).toBeGreaterThanOrEqual(60);
  });
});
