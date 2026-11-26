import {
  Braces,
  Check,
  FlaskConical,
  Layers2,
  Layers3,
  SlidersHorizontal,
} from "lucide-react";
import { useState, type FormEvent } from "react";
import { ExperimentModeField } from "../components/ExperimentModeField";
import type { ExperimentMode } from "../types/api";
import { runSimulation } from "../api/client";
import { NumberField, RunActions } from "../components/ExperimentControls";
import { SimulationResultView } from "../components/SimulationResultView";
import {
  MIN_SERVICES,
  MIN_STEPS,
  TARGET_ERROR,
  TARGET_MAX,
  TARGET_MIN,
  useExperiment,
  useLimits,
} from "./useExperiment";
import "./experiments.css";

export function SimulatePage() {
  const { limits, usingFallback } = useLimits();
  const experiment = useExperiment();
  const [mode, setMode] = useState<ExperimentMode>("cpu-only");
  const [services, setServices] = useState("20");
  const [steps, setSteps] = useState("600");
  const [seed, setSeed] = useState("42");
  const [target, setTarget] = useState("0.01");
  const [invalidField, setInvalidField] = useState("");

  const maxServices =
    (mode === "extended-v1" ? limits.extended_max_services : null) ??
    limits.max_services;
  const maxSteps =
    (mode === "extended-v1" ? limits.extended_max_steps : null) ??
    limits.max_steps;

  const payload = {
    n_services: Number(services),
    n_steps: Number(steps),
    seed: Number(seed),
    target_violation: Number(target),
    ...(mode === "extended-v1" ? { mode } : {}),
  };
  const presets = [
    { name: "Small", services: 5, steps: 600, icon: Layers2 },
    { name: "Medium", services: 20, steps: 864, icon: Layers3 },
  ];

  function run(event: FormEvent) {
    event.preventDefault();
    const checks = [
      {
        id: "n-services",
        valid:
          Number.isInteger(payload.n_services) &&
          payload.n_services >= MIN_SERVICES &&
          payload.n_services <= maxServices,
        message: `Services count must be between ${MIN_SERVICES} and ${maxServices} (whole numbers).`,
      },
      {
        id: "n-steps",
        valid:
          Number.isInteger(payload.n_steps) &&
          payload.n_steps >= MIN_STEPS &&
          payload.n_steps <= maxSteps,
        message: `Steps count must be between ${MIN_STEPS} and ${maxSteps} (whole numbers).`,
      },
      {
        id: "seed",
        valid:
          seed !== "" &&
          Number.isSafeInteger(payload.seed) &&
          payload.seed >= 0,
        message: "Seed must be a non-negative integer.",
      },
      {
        id: "target-violation",
        valid:
          payload.target_violation >= TARGET_MIN &&
          payload.target_violation <= TARGET_MAX,
        message: TARGET_ERROR,
      },
    ];
    const invalid = checks.find((check) => !check.valid);
    if (invalid) {
      setInvalidField(invalid.id);
      experiment.setError(invalid.message);
      document.getElementById(invalid.id)?.focus();
      return;
    }
    setInvalidField("");
    void experiment.execute((signal) => runSimulation(payload, signal));
  }

  function clearValidation() {
    setInvalidField("");
    experiment.setError("");
  }

  return (
    <div className="exp-page">
      <header className="exp-title">
        <h1>Simulation</h1>
        <p>
          Generate a seeded workload and compare CPU allocation policies on
          held-out data.
        </p>
      </header>
      <div className="exp-workspace">
        <form
          noValidate
          onSubmit={run}
          className="exp-panel"
          onChange={clearValidation}
        >
          <header className="exp-panel-heading">
            <SlidersHorizontal aria-hidden="true" />
            <h2>Experiment configuration</h2>
          </header>
          <fieldset className="exp-section" disabled={experiment.loading}>
            <legend className="sr-only">
              Synthetic workload configuration
            </legend>
            <ExperimentModeField
              mode={mode}
              limits={limits}
              onChange={(next) => {
                setMode(next);
                if (next === "extended-v1") {
                  setServices(String(limits.extended_max_services));
                  setSteps(String(limits.extended_max_steps));
                }
              }}
            />
            <h3>Workload preset</h3>
            <div className="exp-presets">
              {(mode === "extended-v1" ? presets.slice(0, 1) : presets).map(
                ({ name, services: size, steps: length, icon: Icon }) => {
                  const cappedServices = Math.min(size, maxServices);
                  const cappedSteps = Math.min(length, maxSteps);
                  const active =
                    payload.n_services === cappedServices &&
                    payload.n_steps === cappedSteps;
                  return (
                    <button
                      key={name}
                      className="exp-preset"
                      type="button"
                      aria-pressed={active}
                      onClick={() => {
                        setServices(String(cappedServices));
                        setSteps(String(cappedSteps));
                        clearValidation();
                      }}
                    >
                      <span>
                        <Icon size={16} aria-hidden="true" />
                        {name}
                        {active && (
                          <Check
                            className="exp-selected"
                            size={14}
                            aria-hidden="true"
                          />
                        )}
                      </span>
                      <small>
                        {cappedServices} services · {cappedSteps} steps
                      </small>
                    </button>
                  );
                },
              )}
            </div>
            <div className="exp-fields">
              <NumberField
                id="n-services"
                label="Number of services"
                hint={`${MIN_SERVICES}–${maxServices} independent services`}
                min={MIN_SERVICES}
                max={maxServices}
                value={services}
                onChange={setServices}
                invalid={invalidField === "n-services"}
              />
              <NumberField
                id="n-steps"
                label="Time steps"
                hint={`${MIN_STEPS}–${maxSteps.toLocaleString()} five-minute intervals`}
                min={MIN_STEPS}
                max={maxSteps}
                value={steps}
                onChange={setSteps}
                invalid={invalidField === "n-steps"}
              />
              <NumberField
                id="seed"
                label="Random seed"
                hint="Reproduces the same synthetic trace"
                min={0}
                value={seed}
                onChange={setSeed}
                invalid={invalidField === "seed"}
              />
              <NumberField
                id="target-violation"
                label="Target violation rate"
                hint="0.005–0.05 · 0.01 equals 1%"
                min={TARGET_MIN}
                max={TARGET_MAX}
                step="any"
                value={target}
                onChange={setTarget}
                invalid={invalidField === "target-violation"}
              />
            </div>
            {usingFallback && (
              <p className="exp-note">
                Server limits are unavailable. Default workload limits are
                shown.
              </p>
            )}
          </fieldset>
          <RunActions
            loading={experiment.loading}
            elapsed={experiment.elapsed}
            onCancel={experiment.cancel}
            error={experiment.error}
            action="Run simulation"
            busyLabel="Running simulation"
          />
        </form>
        <aside className="exp-panel exp-aside" aria-label="Experiment preview">
          <header className="exp-panel-heading">
            <Braces aria-hidden="true" />
            <h2>Request preview</h2>
          </header>
          <div className="exp-section">
            <div className="exp-endpoint">
              <span>POST</span>
              <code>/api/simulate</code>
            </div>
            <pre className="exp-code" aria-label="Configured request payload">
              <code>
                {JSON.stringify(
                  {
                    ...payload,
                    n_services: services === "" ? null : payload.n_services,
                    n_steps: steps === "" ? null : payload.n_steps,
                    seed: seed === "" ? null : payload.seed,
                    target_violation:
                      target === "" ? null : payload.target_violation,
                  },
                  null,
                  2,
                )}
              </code>
            </pre>
            <div className="exp-aside-note">
              <FlaskConical size={16} aria-hidden="true" />
              <p>
                Each run evaluates policies on future intervals and unseen
                services.{" "}
                {mode === "extended-v1"
                  ? "Extended runs model CPU, memory, and task execution."
                  : "CPU-only runs use the original allocation protocol."}
              </p>
            </div>
          </div>
        </aside>
      </div>
      {experiment.result && (
        <SimulationResultView result={experiment.result} source="simulated" />
      )}
    </div>
  );
}
