import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { HistoryPage } from "../pages/HistoryPage";
import type { SavedRun } from "../types/api";

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
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response([run])));
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
