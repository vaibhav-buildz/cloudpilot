import React, { useEffect, useRef, useState } from "react";
import { getLimits, runSimulation, ApiError } from "../api/client";
import { LimitsResponse, SimulationResponse } from "../types/api";
import { DisclaimerBanner } from "../components/DisclaimerBanner";
import { SimulationResultView } from "../components/SimulationResultView";

export const SimulatePage: React.FC = () => {
  const [limits, setLimits] = useState<LimitsResponse>({
    max_services: 50,
    max_steps: 1000,
    max_csv_bytes: 5242880,
    timeout_seconds: 60,
    history_limit: 100,
  });

  const [nServices, setNServices] = useState(20);
  const [nSteps, setNSteps] = useState(288);
  const [seed, setSeed] = useState(42);
  const [targetViolation, setTargetViolation] = useState(0.01);

  const [isLoading, setIsLoading] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [result, setResult] = useState<SimulationResponse | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    getLimits()
      .then((data) => setLimits(data))
      .catch((_) => {
        // Fallback limits are active
      });
  }, []);

  const handlePreset = (services: number, steps: number) => {
    setNServices(Math.min(services, limits.max_services));
    setNSteps(Math.min(steps, limits.max_steps));
    setErrorMsg(null);
  };

  const validate = (): string | null => {
    if (nServices < 1 || nServices > limits.max_services) {
      return `Services count must be between 1 and ${limits.max_services}.`;
    }
    if (nSteps < 48 || nSteps > limits.max_steps) {
      return `Steps count must be between 48 and ${limits.max_steps}.`;
    }
    if (seed < 0 || !Number.isInteger(seed)) {
      return "Seed must be a non-negative integer.";
    }
    if (targetViolation <= 0 || targetViolation >= 1) {
      return "Target violation rate must be between 0 and 1 (exclusive).";
    }
    return null;
  };

  const handleRun = async (e: React.FormEvent) => {
    e.preventDefault();
    const validationError = validate();
    if (validationError) {
      setErrorMsg(validationError);
      return;
    }

    setErrorMsg(null);
    setResult(null);
    setIsLoading(true);
    setElapsedSeconds(0);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    const startTime = Date.now();
    timerRef.current = window.setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);

    try {
      const data = await runSimulation(
        {
          n_services: nServices,
          n_steps: nSteps,
          seed,
          target_violation: targetViolation,
        },
        controller.signal
      );
      setResult(data);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          setErrorMsg("Proxy key missing or authentication failed.");
        } else if (err.status === 429) {
          setErrorMsg(
            err.retryAfter
              ? `Rate limit reached. Try again in ${err.retryAfter}s.`
              : "Rate limit reached. Please wait a moment."
          );
        } else if (err.status === 504) {
          setErrorMsg("Simulation timed out. Try smaller parameters.");
        } else if (err.status === 499) {
          setErrorMsg("Simulation cancelled by user.");
        } else {
          setErrorMsg(err.message || "Simulation failed.");
        }
      } else {
        setErrorMsg("Backend unavailable. Please verify connection.");
      }
    } finally {
      setIsLoading(false);
      if (timerRef.current !== null) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      abortControllerRef.current = null;
    }
  };

  const handleCancel = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  };

  return (
    <div className="simulate-page">
      <DisclaimerBanner />

      <section className="card">
        <h1 className="card-title" style={{ fontSize: "1.4rem" }}>
          Run Synthetic Simulation
        </h1>
        <p style={{ color: "var(--text-muted)", fontSize: "0.95rem", marginBottom: "1rem" }}>
          Configure simulated synthetic workloads to evaluate margin selection and
          comparisons across models on the fly.
        </p>

        {/* Presets */}
        <div className="preset-buttons">
          <span style={{ fontSize: "0.875rem", alignSelf: "center", fontWeight: 500 }}>
            Quick Presets:
          </span>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => handlePreset(5, 288)}
            disabled={isLoading}
          >
            Small (5 svc, 1 day)
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => handlePreset(20, 864)}
            disabled={isLoading}
          >
            Medium (20 svc, 3 days)
          </button>
        </div>

        <form onSubmit={handleRun} noValidate>
          <div className="grid-2">
            <div className="form-group">
              <label htmlFor="n-services" className="form-label">
                Number of Services (max: {limits.max_services})
              </label>
              <input
                id="n-services"
                type="number"
                className="form-input"
                min={1}
                max={limits.max_services}
                value={nServices}
                onChange={(e) => setNServices(parseInt(e.target.value, 10) || 0)}
                disabled={isLoading}
                required
              />
              <div className="form-help">Synthetic services generated per workload</div>
            </div>

            <div className="form-group">
              <label htmlFor="n-steps" className="form-label">
                Time Steps (5-min intervals, max: {limits.max_steps})
              </label>
              <input
                id="n-steps"
                type="number"
                className="form-input"
                min={48}
                max={limits.max_steps}
                value={nSteps}
                onChange={(e) => setNSteps(parseInt(e.target.value, 10) || 0)}
                disabled={isLoading}
                required
              />
              <div className="form-help">288 steps = 24 hours, 864 steps = 3 days</div>
            </div>

            <div className="form-group">
              <label htmlFor="seed" className="form-label">
                Random Seed
              </label>
              <input
                id="seed"
                type="number"
                className="form-input"
                value={seed}
                onChange={(e) => setSeed(parseInt(e.target.value, 10) || 0)}
                disabled={isLoading}
                required
              />
              <div className="form-help">Deterministic workload generation seed</div>
            </div>

            <div className="form-group">
              <label htmlFor="target-violation" className="form-label">
                Target Violation Rate (SLA threshold)
              </label>
              <input
                id="target-violation"
                type="number"
                step="0.001"
                min="0.001"
                max="0.5"
                className="form-input"
                value={targetViolation}
                onChange={(e) => setTargetViolation(parseFloat(e.target.value) || 0.01)}
                disabled={isLoading}
                required
              />
              <div className="form-help">Default 0.01 = 1% SLA violation limit</div>
            </div>
          </div>

          {errorMsg && (
            <div className="alert alert-error" role="alert">
              {errorMsg}
            </div>
          )}

          <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={isLoading}
            >
              {isLoading ? `Running Simulation... (${elapsedSeconds}s)` : "Run Simulation"}
            </button>
            {isLoading && (
              <button
                type="button"
                className="btn btn-danger"
                onClick={handleCancel}
              >
                Cancel
              </button>
            )}
          </div>
        </form>
      </section>

      {result && <SimulationResultView result={result} />}
    </div>
  );
};
