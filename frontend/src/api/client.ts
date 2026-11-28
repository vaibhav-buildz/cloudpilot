import {
  LimitsResponse,
  SavedRun,
  ExperimentMode,
  ExperimentResult,
} from "../types/api";

export class ApiError extends Error {
  public status: number;
  public retryAfter?: number;

  constructor(message: string, status: number, retryAfter?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.retryAfter = retryAfter;
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      if (Array.isArray(body.detail)) {
        detail = body.detail
          .map((issue: { msg?: string }) => issue.msg)
          .filter(Boolean)
          .join(". ");
      } else {
        detail = body.detail || body.message || "";
      }
    } catch {
      // response was not JSON
    }

    if (res.status === 401) {
      throw new ApiError(
        detail || "Proxy key missing or authentication failed.",
        401,
      );
    }
    if (res.status === 422) {
      throw new ApiError(
        detail || "Invalid input parameters. Please check your inputs.",
        422,
      );
    }
    if (res.status === 429) {
      const retryAfterHeader = res.headers.get("Retry-After");
      const retryAfter = retryAfterHeader
        ? parseInt(retryAfterHeader, 10)
        : undefined;
      const msg = retryAfter
        ? `Rate limit exceeded. Try again in ${retryAfter}s.`
        : "Rate limit exceeded. Please wait a moment.";
      throw new ApiError(detail || msg, 429, retryAfter);
    }
    if (res.status === 504) {
      throw new ApiError(
        detail || "The request timed out. Try a smaller workload once the backend is ready.",
        504,
      );
    }
    if (res.status === 502 || res.status === 503) {
      const retryAfter = Number(res.headers.get("Retry-After")) || undefined;
      throw new ApiError(
        retryAfter && detail
          ? detail
          : "The backend may be starting. Wait a moment and try again.",
        res.status,
        retryAfter,
      );
    }

    throw new ApiError(
      detail || `Request failed with status ${res.status}`,
      res.status,
    );
  }

  return (await res.json()) as T;
}

export async function getLimits(): Promise<LimitsResponse> {
  try {
    const res = await fetch("/api/limits", {
      headers: { Accept: "application/json" },
    });
    return await handleResponse<LimitsResponse>(res);
  } catch (err) {
    if (err instanceof ApiError) throw err;
    throw new ApiError("Backend unavailable", 0);
  }
}

export async function runSimulation(
  payload: {
    n_services: number;
    n_steps: number;
    seed: number;
    target_violation: number;
    mode?: ExperimentMode;
  },
  signal?: AbortSignal,
): Promise<ExperimentResult> {
  try {
    const res = await fetch("/api/simulate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
      signal,
    });
    return await handleResponse<ExperimentResult>(res);
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError("Simulation cancelled", 499);
    }
    throw new ApiError("Backend unavailable", 0);
  }
}

export function runSimulationCsv(
  file: File,
  targetViolation: number,
  signal?: AbortSignal,
  onProgress?: (fraction: number) => void,
  mode: ExperimentMode = "cpu-only",
): Promise<ExperimentResult> {
  // Fetch does not expose upload byte counts. XHR uses the same same-origin proxy
  // and browser-managed cookie as the other experiment calls.
  return new Promise((resolve, reject) => {
    const cancelled = () =>
      reject(
        new ApiError(
          "Request cancelled. Check History if the run finished before cancellation.",
          499,
        ),
      );
    if (signal?.aborted) {
      cancelled();
      return;
    }
    const request = new XMLHttpRequest();
    const abort = () => request.abort();
    signal?.addEventListener("abort", abort, { once: true });
    request.onloadend = () => signal?.removeEventListener("abort", abort);
    request.onabort = cancelled;
    request.onerror = () => reject(new ApiError("Backend unavailable", 0));
    request.ontimeout = () =>
      reject(new ApiError("Upload request timed out.", 504));
    request.upload.onprogress = (event) => {
      if (event.lengthComputable && event.total > 0)
        onProgress?.(event.loaded / event.total);
    };
    request.upload.onload = () => onProgress?.(1);
    request.onload = () => {
      const retryAfter = request.getResponseHeader("Retry-After");
      const response = new Response(request.responseText, {
        status: request.status,
        headers: retryAfter ? { "Retry-After": retryAfter } : {},
      });
      handleResponse<ExperimentResult>(response).then(resolve, reject);
    };

    request.open("POST", "/api/simulate/csv");
    request.setRequestHeader("Accept", "application/json");
    const formData = new FormData();
    formData.append("file", file);
    formData.append("target_violation", targetViolation.toString());
    if (mode === "extended-v1") formData.append("mode", mode);
    request.send(formData);
  });
}

export async function getRuns(
  limit: number = 10,
  offset: number = 0,
): Promise<SavedRun[]> {
  try {
    const res = await fetch(`/api/runs?limit=${limit}&offset=${offset}`, {
      headers: { Accept: "application/json" },
    });
    return await handleResponse<SavedRun[]>(res);
  } catch (err) {
    if (err instanceof ApiError) throw err;
    throw new ApiError("Backend unavailable", 0);
  }
}

export async function getRun(id: string, signal?: AbortSignal): Promise<SavedRun> {
  try {
    const res = await fetch(`/api/runs/${encodeURIComponent(id)}`, {
      headers: { Accept: "application/json" },
      signal,
    });
    return await handleResponse<SavedRun>(res);
  } catch (err) {
    if (err instanceof ApiError) throw err;
    throw new ApiError("Backend unavailable", 0);
  }
}

export async function deleteRun(id: string): Promise<{ deleted: boolean }> {
  try {
    const res = await fetch(`/api/runs/${encodeURIComponent(id)}`, {
      method: "DELETE",
      headers: { Accept: "application/json" },
    });
    return await handleResponse<{ deleted: boolean }>(res);
  } catch (err) {
    if (err instanceof ApiError) throw err;
    throw new ApiError("Backend unavailable", 0);
  }
}
