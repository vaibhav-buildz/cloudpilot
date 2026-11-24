import {
  LimitsResponse,
  RunsListResponse,
  SimulationResponse,
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
      detail = body.detail || body.message || "";
    } catch {
      // response was not JSON
    }

    if (res.status === 401) {
      throw new ApiError(
        detail || "Proxy key missing or authentication failed.",
        401
      );
    }
    if (res.status === 422) {
      throw new ApiError(
        detail || "Invalid input parameters. Please check your inputs.",
        422
      );
    }
    if (res.status === 429) {
      const retryAfterHeader = res.headers.get("Retry-After");
      const retryAfter = retryAfterHeader ? parseInt(retryAfterHeader, 10) : undefined;
      const msg = retryAfter
        ? `Rate limit exceeded. Try again in ${retryAfter}s.`
        : "Rate limit exceeded. Please wait a moment.";
      throw new ApiError(detail || msg, 429, retryAfter);
    }
    if (res.status === 504) {
      throw new ApiError(
        "Simulation timed out on backend. Try smaller workload settings.",
        504
      );
    }
    if (res.status === 502 || res.status === 503) {
      throw new ApiError(
        "Backend service unavailable. Please check that the server is running.",
        res.status
      );
    }

    throw new ApiError(
      detail || `Request failed with status ${res.status}`,
      res.status
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
  },
  signal?: AbortSignal
): Promise<SimulationResponse> {
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
    return await handleResponse<SimulationResponse>(res);
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError("Simulation cancelled", 499);
    }
    throw new ApiError("Backend unavailable", 0);
  }
}

export async function runSimulationCsv(
  file: File,
  targetViolation: number,
  signal?: AbortSignal
): Promise<SimulationResponse> {
  try {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("target_violation", targetViolation.toString());

    const res = await fetch("/api/simulate/csv", {
      method: "POST",
      headers: {
        Accept: "application/json",
      },
      body: formData,
      signal,
    });
    return await handleResponse<SimulationResponse>(res);
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError("Simulation cancelled", 499);
    }
    throw new ApiError("Backend unavailable", 0);
  }
}

export async function getRuns(
  limit: number = 10,
  offset: number = 0
): Promise<RunsListResponse> {
  try {
    const res = await fetch(`/api/runs?limit=${limit}&offset=${offset}`, {
      headers: { Accept: "application/json" },
    });
    return await handleResponse<RunsListResponse>(res);
  } catch (err) {
    if (err instanceof ApiError) throw err;
    throw new ApiError("Backend unavailable", 0);
  }
}

export async function getRun(id: string): Promise<SimulationResponse> {
  try {
    const res = await fetch(`/api/runs/${encodeURIComponent(id)}`, {
      headers: { Accept: "application/json" },
    });
    return await handleResponse<SimulationResponse>(res);
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
