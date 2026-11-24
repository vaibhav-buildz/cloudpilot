import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SimulatePage } from "../pages/SimulatePage";

describe("SimulatePage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("loads limits and applies presets correctly", async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === "/api/limits") {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              max_services: 40,
              max_steps: 800,
              max_csv_bytes: 5242880,
              timeout_seconds: 60,
              history_limit: 100,
            }),
        });
      }
      return Promise.reject(new Error("Unknown route"));
    });

    render(
      <BrowserRouter>
        <SimulatePage />
      </BrowserRouter>
    );

    expect(screen.getByText(/Run Synthetic Simulation/i)).toBeInTheDocument();

    // Wait for limits to load
    await waitFor(() => {
      expect(
        screen.getByText(/Number of Services \(max: 40\)/i)
      ).toBeInTheDocument();
    });

    // Click Small Preset
    const smallBtn = screen.getByRole("button", {
      name: /Small \(5 svc, 1 day\)/i,
    });
    fireEvent.click(smallBtn);

    const servicesInput = screen.getByLabelText(/Number of Services/i) as HTMLInputElement;
    const stepsInput = screen.getByLabelText(/Time Steps/i) as HTMLInputElement;

    expect(servicesInput.value).toBe("5");
    expect(stepsInput.value).toBe("288");

    // Click Medium Preset
    const mediumBtn = screen.getByRole("button", {
      name: /Medium \(20 svc, 3 days\)/i,
    });
    fireEvent.click(mediumBtn);
    expect(servicesInput.value).toBe("20");
    // Capped by limits.max_steps (800)
    expect(stepsInput.value).toBe("800");
  });

  it("validates input fields against caps before submitting", async () => {
    render(
      <BrowserRouter>
        <SimulatePage />
      </BrowserRouter>
    );

    const servicesInput = screen.getByLabelText(/Number of Services/i);
    fireEvent.change(servicesInput, { target: { value: "9999" } });

    const submitBtn = screen.getByRole("button", { name: /^Run Simulation$/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(
        screen.getByText(/Services count must be between 1 and/i)
      ).toBeInTheDocument();
    });
  });
});
