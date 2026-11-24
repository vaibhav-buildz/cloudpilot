import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { StudyPage } from "../pages/StudyPage";

describe("StudyPage", () => {
  it("renders benchmark verdicts, per-seed table, generator note, and deviations link", () => {
    render(
      <BrowserRouter>
        <StudyPage />
      </BrowserRouter>
    );

    // Headline verdicts
    expect(screen.getByText(/Empirical Study Findings/i)).toBeInTheDocument();
    expect(screen.getByText(/H1: Time Split/i)).toBeInTheDocument();
    expect(screen.getByText(/H2: Service Split/i)).toBeInTheDocument();
    expect(screen.getByText(/H3: Safety Bound/i)).toBeInTheDocument();

    // Discussion of the negative result
    expect(screen.getByText(/Analysis of the Negative Result/i)).toBeInTheDocument();
    expect(
      screen.getByText(/In our controlled 10-seed evaluation/i)
    ).toBeInTheDocument();

    // Generator over-provisioning note
    expect(
      screen.getByText(/Generator Over-Provisioning Note/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Savings are relative to the simulator's static request/i)
    ).toBeInTheDocument();

    // Link to GitHub deviations doc
    const devLink = screen.getByRole("link", { name: /docs\/deviations\.md/i });
    expect(devLink).toBeInTheDocument();
    expect(devLink).toHaveAttribute(
      "href",
      "https://github.com/vy979/cloudpilot/blob/main/docs/deviations.md"
    );

    // Per-seed comparison table
    expect(screen.getByText(/Per-Seed Comparison/i)).toBeInTheDocument();
    expect(screen.getAllByText(/rolling_max_48/i).length).toBeGreaterThan(0);
  });
});
