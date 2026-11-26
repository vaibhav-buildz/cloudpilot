import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StudyPage } from "../pages/StudyPage";

describe("StudyPage", () => {
  it("shows the recorded verdicts, per-seed data, limitations and deviation log", () => {
    render(<StudyPage />);
    expect(screen.getByRole("heading", { level: 1, name: "Research study" })).toBeVisible();
    for (const [label, verdict, count] of [
      ["H1 Time split", "Not supported", "0/10"],
      ["H2 Service split", "Not supported", "0/10"],
      ["H3 Safety bound", "Supported", "10/10"],
    ]) {
      const card = screen.getByRole("heading", { name: label }).closest(".research-verdict")!;
      expect(card).toHaveTextContent(verdict);
      expect(card).toHaveTextContent(`${count} seeds supported`);
    }
    fireEvent.click(screen.getByText("Per-seed comparison"));
    const seeds = screen.getByRole("table", { name: "Per-seed results for time split" });
    expect(within(seeds).getAllByRole("row")).toHaveLength(11);
    expect(within(seeds).getAllByText("rolling_max_48")).toHaveLength(10);
    expect(within(seeds).getAllByRole("row")[1]).toHaveTextContent("-2.80 [-3.96, -1.63]");

    fireEvent.click(screen.getByText("Methodology and interpretation"));
    expect(screen.getByText("Analysis of the negative result")).toBeVisible();
    expect(screen.getByText(/In this 10-seed evaluation/)).toHaveTextContent("Neither H1 nor H2 met its decision rule");
    expect(screen.getByText("Generator over-provisioning")).toBeVisible();
    expect(screen.getByText(/Savings are relative to the simulator’s static request/)).toBeVisible();
    expect(screen.getByRole("link", { name: "Study deviations" })).toHaveAttribute(
      "href", "https://github.com/vaibhav-buildz/cloudpilot/blob/main/docs/deviations.md"
    );
  });

  it("switches recorded splits, inspects confidence intervals, and changes performance metrics", () => {
    render(<StudyPage />);
    const timeChart = screen.getByRole("figure", { name: "Median savings by policy on the time split" });
    expect(within(timeChart).getByText("56.72%")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "SERVICE" }));
    expect(screen.getByRole("button", { name: "SERVICE" })).toHaveAttribute("aria-pressed", "true");
    const serviceChart = screen.getByRole("figure", { name: "Median savings by policy on the service split" });
    expect(within(serviceChart).getByText("53.95%")).toBeVisible();
    fireEvent.click(within(serviceChart).getByText("rolling_max_48"));
    expect(within(serviceChart).getByText(/Mean savings 53.74%/)).toBeVisible();
    fireEvent.change(screen.getByRole("combobox", { name: "Performance metric" }), { target: { value: "median_violation_pct" } });
    const violations = screen.getByRole("figure", { name: "Median violation by policy on the service split" });
    expect(within(violations).getByText("0.96%")).toBeVisible();

    const forest = screen.getByRole("figure", { name: "95% confidence intervals by seed" });
    const seed = within(forest).getByRole("button", { name: /Seed 5, effect 0.95 pp/ });
    fireEvent.click(seed);
    expect(seed).toHaveAttribute("aria-pressed", "true");
    expect(within(forest).getByText("95% CI [-1.08, 3.02]")).toBeVisible();
    fireEvent.click(screen.getByText("Per-seed comparison"));
    const breakdown = screen.getByRole("table", { name: "Per-seed results for service split" });
    expect(within(breakdown).getAllByRole("row")[5]).toHaveTextContent("0.95 [-1.08, 3.02]");
  });

  it("sorts policies numerically and exposes validation feasibility for the chosen split", () => {
    render(<StudyPage />);
    fireEvent.click(screen.getByRole("button", { name: "SERVICE" }));
    const table = within(screen.getByRole("table", { name: "Policy comparison for service split" }));
    expect(table.getAllByRole("row")).toHaveLength(10);
    expect(table.getAllByRole("row")[1]).toHaveTextContent("rolling_max_48");
    fireEvent.click(table.getByRole("button", { name: "Median savings" }));
    expect(table.getByRole("columnheader", { name: "Median savings" })).toHaveAttribute("aria-sort", "ascending");
    expect(table.getAllByRole("row")[1]).toHaveTextContent("0.00%");
    fireEvent.click(table.getByRole("button", { name: "Median violation" }));
    expect(table.getAllByRole("row")[1]).toHaveTextContent("static");
    fireEvent.click(table.getByRole("button", { name: "Feasible seeds" }));
    expect(table.getAllByRole("row").at(-1)).toHaveTextContent("ewma");
    expect(table.getAllByRole("row").at(-1)).toHaveTextContent("2/10");
  });
});
