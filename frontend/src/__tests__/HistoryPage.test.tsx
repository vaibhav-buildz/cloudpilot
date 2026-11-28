import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { HistoryPage } from "../pages/HistoryPage";
import type { ExperimentMode, ExperimentResult, SavedRun } from "../types/api";

function sampleRun(index = 1): SavedRun {
  return {
    id: String(index).padStart(8, "0") + "-dcaf-4020-9beb-6afe8acfd369",
    created_at: "2025-05-06T12:03:00Z",
    source: "simulated",
    params: { n_services: 4, n_steps: 600, seed: 42, target_violation: 0.01 },
    status: "ok",
    duration_ms: 2530,
    result: null,
    error: null,
  };
}

const response = (data: unknown) => ({ ok: true, json: async () => data });

function savedEvaluation(mode: ExperimentMode, elapsed = 2): ExperimentResult {
  const parameters = { n_services: 3, n_steps: 482, seed: 42, target_violation: 0.01 };
  const comparison = {
    comparator: "static",
    comparator_is_feasible: true,
    methods: {
      static: {
        margin_value: 1, margin_type: "multiplicative", is_feasible: true,
        violation_rate: 0, savings: 0, utilization: 0.6, wastage: 0.4,
      },
    },
  };
  if (mode === "extended-v1") {
    const split = {
      cpu: comparison, memory: comparison, offered_tasks: 1, offered_tasks_sha256: "test",
      policies: {
        static: {
          jointly_feasible: true,
          validation_joint_violation_rate: 0,
          test_joint_violation_rate: 0,
          tasks: null,
        },
      },
    };
    return { mode, parameters, execution_time_seconds: elapsed, time_split: split, service_split: split };
  }
  const hypothesis = { hypothesis: "", verdict: "SUPPORTED", estimate: 0, ci_lower: 0, ci_upper: 0, p_value: 1 };
  return {
    parameters, execution_time_seconds: elapsed, disclaimer: "",
    time_split: { ...comparison, h1: hypothesis },
    service_split: { ...comparison, h2: hypothesis },
    h3: { hypothesis: "", verdict: "SUPPORTED", test_violation_time: 0, test_violation_service: 0, threshold: 0.01 },
  };
}

function renderHistory(path = "/history") {
  return render(
    <MemoryRouter initialEntries={[path]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes>
        <Route path="/history/:id?" element={<HistoryPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("HistoryPage", () => {
  beforeAll(() => {
    // jsdom does not implement native dialog open/close methods.
    HTMLDialogElement.prototype.showModal ??= function () {
      this.setAttribute("open", "");
    };
    HTMLDialogElement.prototype.close ??= function () {
      this.removeAttribute("open");
    };
  });

  afterEach(() => vi.unstubAllGlobals());

  it("renders the visitor's empty history and a link to start an experiment", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response([])));
    renderHistory();
    expect(screen.getByRole("heading", { name: "Experiment history" })).toBeVisible();
    expect(await screen.findByText(/No simulation runs saved yet/i)).toBeVisible();
    expect(screen.getByText(/this browser’s visitor session/i)).toBeVisible();
    expect(screen.getByRole("link", { name: /New simulation/i })).toHaveAttribute("href", "/simulate");
  });

  it("displays recorded status and duration, and expands the selected row", async () => {
    const run = { ...sampleRun(), source: "csv", status: "error", error: "Execution timed out." };
    vi.stubGlobal("fetch", vi.fn(async (url: string) => response(url.includes("?") ? [run] : run)));
    renderHistory();

    const expand = await screen.findByRole("button", { name: `Expand run ${run.id}` });
    expect(expand).toHaveTextContent("CSV workload");
    expect(expand).toHaveTextContent("Failed");
    expect(expand).toHaveTextContent("2.5 s");
    expect(expand).toHaveTextContent("4 services");
    expect(expand).toHaveTextContent("600 steps");
    expect(screen.getByRole("time")).toHaveAttribute("datetime", run.created_at);

    fireEvent.click(expand);
    expect(await screen.findByText(run.error)).toBeVisible();
    expect(screen.getByText("1%")).toBeVisible();
    const collapse = screen.getByRole("button", { name: `Collapse run ${run.id}` });
    expect(collapse).toHaveAttribute("aria-expanded", "true");
    fireEvent.click(collapse);
    expect(screen.queryByText(run.error)).not.toBeInTheDocument();
  });

  it.each([
    ["cpu-only", "Experiment results"],
    ["extended-v1", "Extended CPU + Memory + Tasks"],
  ] as const)("fetches and renders full %s results only after expanding", async (mode, heading) => {
    const summary = { ...sampleRun(), params: { ...sampleRun().params, mode } };
    let complete!: (value: ReturnType<typeof response>) => void;
    const detail = new Promise<ReturnType<typeof response>>((resolve) => { complete = resolve; });
    const fetchRun = vi.fn((url: string) => url.includes("?") ? Promise.resolve(response([summary])) : detail);
    vi.stubGlobal("fetch", fetchRun);
    renderHistory();
    const expand = await screen.findByRole("button", { name: `Expand run ${summary.id}` });
    expect(fetchRun).toHaveBeenCalledTimes(1);
    fireEvent.click(expand);
    expect(await screen.findByText("Loading run details…")).toBeVisible();
    expect(screen.queryByText(/No evaluation results were recorded/)).not.toBeInTheDocument();
    expect(fetchRun).toHaveBeenCalledWith(`/api/runs/${summary.id}`, expect.objectContaining({ signal: expect.any(AbortSignal) }));
    complete(response({ ...summary, result: savedEvaluation(mode) }));
    expect(await screen.findByRole("heading", { name: heading })).toBeVisible();
  });

  it("retries a failed detail fetch without reloading the history list", async () => {
    const summary = sampleRun();
    const request = vi.fn()
      .mockResolvedValueOnce(response([summary]))
      .mockResolvedValueOnce(new Response("{}", { status: 502 }))
      .mockResolvedValueOnce(response({ ...summary, result: savedEvaluation("cpu-only") }));
    vi.stubGlobal("fetch", request);
    renderHistory(`/history/${summary.id}`);
    expect(await screen.findByRole("alert")).toHaveTextContent(/backend may be starting/i);
    expect(screen.queryByText(/No evaluation results were recorded/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry loading run" }));
    expect(await screen.findByRole("heading", { name: "Experiment results" })).toBeVisible();
    expect(request.mock.calls.map(([url]) => url)).toEqual([
      "/api/runs?limit=11&offset=0", `/api/runs/${summary.id}`, `/api/runs/${summary.id}`,
    ]);
  });

  it("aborts a pending detail request and ignores its response after switching rows", async () => {
    const first = sampleRun();
    const second = sampleRun(2);
    let finishFirst!: (value: ReturnType<typeof response>) => void;
    const firstDetail = new Promise<ReturnType<typeof response>>((resolve) => { finishFirst = resolve; });
    const request = vi.fn(async (url: string, _init: RequestInit) => {
      if (url.includes("?")) return response([first, second]);
      if (url.endsWith(first.id)) return firstDetail;
      return response({ ...second, result: savedEvaluation("extended-v1") });
    });
    vi.stubGlobal("fetch", request);
    renderHistory();
    fireEvent.click(await screen.findByRole("button", { name: `Expand run ${first.id}` }));
    expect(await screen.findByText("Loading run details…")).toBeVisible();
    const firstSignal = request.mock.calls.find(([url]) => url.endsWith(first.id))?.[1].signal;
    fireEvent.click(screen.getByRole("button", { name: `Expand run ${second.id}` }));
    expect(await screen.findByRole("heading", { name: "Extended CPU + Memory + Tasks" })).toBeVisible();
    expect(firstSignal?.aborted).toBe(true);
    await act(async () => finishFirst(response({ ...first, result: savedEvaluation("cpu-only") })));
    expect(screen.queryByRole("heading", { name: "Experiment results" })).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: `Details for run ${second.id}` })).toBeVisible();
  });

  it("pages through real API rows and requests deletion only after confirmation", async () => {
    const rows = Array.from({ length: 11 }, (_, i) => sampleRun(i + 1));
    const last = rows[10];
    const request = vi.fn(async (url: string, init: RequestInit) => {
      if (init.method === "DELETE") {
        expect(url).toBe(`/api/runs/${last.id}`);
        rows.pop();
        return response({ id: last.id, deleted: true });
      }
      const offset = Number(new URL(url, "https://example.test").searchParams.get("offset"));
      return response(rows.slice(offset, offset + 11));
    });
    vi.stubGlobal("fetch", request);
    renderHistory();
    expect(await screen.findByText("Showing 1–10")).toBeVisible();
    expect(screen.queryByRole("button", { name: `Expand run ${last.id}` })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    expect(await screen.findByText("Showing 11–11")).toBeVisible();
    expect(screen.getByRole("button", { name: "Next page" })).toBeDisabled();

    const deleteButton = screen.getByRole("button", { name: `Delete run ${last.id}` });
    fireEvent.click(deleteButton);
    const dialog = screen.getByRole("dialog", { name: "Delete this run?" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(request.mock.calls.some(([, init]) => init.method === "DELETE")).toBe(false);

    fireEvent.click(deleteButton);
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Delete run" }));
    expect(await screen.findByText("Showing 1–10")).toBeVisible();
    expect(request.mock.calls.filter(([, init]) => init.method === "DELETE")).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Next page" })).toBeDisabled();
  });

  it("opens a direct link outside the first page using the visitor-scoped detail endpoint", async () => {
    const linked = { ...sampleRun(15), status: "error", error: "Unavailable evaluation." };
    const request = vi.fn(async (url: string) => response(url.includes("?") ? [sampleRun()] : linked));
    vi.stubGlobal("fetch", request);
    renderHistory(`/history/${linked.id}`);
    expect(await screen.findByText(linked.error)).toBeVisible();
    expect(request).toHaveBeenCalledWith(`/api/runs/${linked.id}`, expect.anything());
  });

  it("keeps an unavailable backend distinct from an empty visitor history and retries", async () => {
    const request = vi.fn().mockRejectedValueOnce(new Error("Connection refused")).mockResolvedValue(response([]));
    vi.stubGlobal("fetch", request);
    renderHistory();
    expect(await screen.findByRole("alert")).toHaveTextContent("Backend unavailable");
    expect(screen.queryByText(/No simulation runs saved yet/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(screen.getByText(/No simulation runs saved yet/i)).toBeVisible());
  });
});
