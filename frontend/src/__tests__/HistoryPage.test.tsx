import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { HistoryPage } from "../pages/HistoryPage";

describe("HistoryPage", () => {
  it("renders empty state when no runs exist", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ runs: [], total: 0, limit: 10, offset: 0 }),
    });

    render(
      <BrowserRouter>
        <HistoryPage />
      </BrowserRouter>
    );

    expect(screen.getByText(/Visitor Simulation History/i)).toBeInTheDocument();
    expect(
      await screen.findByText(/No simulation runs saved yet/i)
    ).toBeInTheDocument();
  });
});
