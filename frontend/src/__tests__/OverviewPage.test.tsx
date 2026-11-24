import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { OverviewPage } from "../pages/OverviewPage";

describe("OverviewPage", () => {
  it("renders methodology and prominent disclaimer banner", () => {
    render(
      <BrowserRouter>
        <OverviewPage />
      </BrowserRouter>
    );

    expect(screen.getByText(/Simulator Disclaimer/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Simulated results. Does not reflect real cloud workloads/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/CloudPilot: ML-Based CPU Allocation Research/i)).toBeInTheDocument();
    expect(screen.getByText(/Methodology/i)).toBeInTheDocument();

    const studyLink = screen.getByRole("link", { name: /View Study Findings/i });
    expect(studyLink).toBeInTheDocument();
    expect(studyLink).toHaveAttribute("href", "/study");

    const simLink = screen.getByRole("link", { name: /Run Simulation/i });
    expect(simLink).toBeInTheDocument();
    expect(simLink).toHaveAttribute("href", "/simulate");
  });
});
