import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import type { ExtendedResponse, TaskMetrics } from "../types/api";
import { AllocationBarChart } from "./AllocationBarChart";
import { downloadExperiment } from "./experimentExport";
import { HeldOutCharts, TraceChart } from "./ResearchDiagnostics";

const number = (value: number | null | undefined) =>
  value == null
    ? "—"
    : value.toLocaleString(undefined, { maximumFractionDigits: 4 });
const percent = (value: number | null | undefined) =>
  value == null ? "—" : number(value * 100) + "%";

function TaskResults({ tasks }: { tasks: TaskMetrics }) {
  const intervals = tasks.timeline.map((step) => step.elapsed_seconds);
  return (
    <div className="diag-section">
      {tasks.scheduler_utilization && (
        <p>
          Scheduler utilization from actual task consumption. CPU{" "}
          {percent(tasks.scheduler_utilization.cpu_fraction)} of allocated
          core-seconds. Resident task memory{" "}
          {percent(tasks.scheduler_utilization.memory_fraction)} of allocated
          GiB-seconds. Suspended tasks release their memory reservation.
        </p>
      )}
      <dl className="extended-stats">
        <div>
          <dt>Completion</dt>
          <dd>
            {tasks.completed}/{tasks.offered} · {percent(tasks.completion_rate)}
          </dd>
        </div>
        <div>
          <dt>Unfinished</dt>
          <dd>
            {tasks.unfinished} · {tasks.rejected} rejected
          </dd>
        </div>
        <div>
          <dt>Never admitted</dt>
          <dd>{tasks.never_admitted}</dd>
        </div>
        <div>
          <dt>Admitted, unfinished</dt>
          <dd>
            {tasks.admitted_unfinished} · {tasks.suspended_final} suspended at
            end
          </dd>
        </div>
        <div>
          <dt>Throughput</dt>
          <dd>{number(tasks.throughput_per_second)} tasks/s</dd>
        </div>
        <div>
          <dt>Peak / final backlog</dt>
          <dd>
            {tasks.peak_backlog} / {tasks.final_backlog} tasks
          </dd>
        </div>
      </dl>
      <div
        className="exp-table-wrap"
        role="region"
        aria-label="Task timings"
        tabIndex={0}
      >
        <table className="exp-table">
          <thead>
            <tr>
              <th scope="col">Simulated timing</th>
              <th scope="col">Observed tasks</th>
              <th scope="col">Mean (s)</th>
              <th scope="col">Median (s)</th>
              <th scope="col">P95 (s)</th>
            </tr>
          </thead>
          <tbody>
            {(
              ["waiting", "first_service", "response", "execution"] as const
            ).map((key, index) => {
              const values = tasks.timing_seconds[key];
              return (
                <tr key={key}>
                  <th scope="row">
                    {
                      [
                        "Arrival to admission",
                        "Arrival to first CPU service",
                        "Arrival to completion",
                        "Admission to completion",
                      ][index]
                    }
                  </th>
                  <td>{values.count}</td>
                  <td>{number(values.mean)}</td>
                  <td>{number(values.median)}</td>
                  <td>{number(values.p95)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p>
        Response and execution summaries cover completed tasks. Unfinished and
        rejected tasks remain in the completion denominator.
      </p>
      {tasks.completed > 0 ? (
        <AllocationBarChart
          title="Completed-task response time distribution · bin bounds in seconds"
          unit="tasks"
          items={tasks.response_distribution.counts.map((count, i) => ({
            label:
              number(tasks.response_distribution.edges[i]) +
              "–" +
              number(tasks.response_distribution.edges[i + 1]),
            value: count,
          }))}
        />
      ) : (
        <p>No tasks completed within the evaluation window.</p>
      )}
      <TraceChart
        title="Queue and suspension backlog"
        steps={intervals}
        stepLabel="Elapsed seconds"
        unit="tasks"
        series={[
          {
            label: "Backlog",
            values: tasks.timeline.map((row) => row.backlog),
          },
        ]}
      />
      <TraceChart
        title="Completion throughput"
        steps={intervals}
        stepLabel="Elapsed seconds"
        unit="tasks/s"
        series={[
          {
            label: "Throughput",
            values: tasks.timeline.map((row) => row.throughput_per_second),
          },
        ]}
      />
    </div>
  );
}

export function ExtendedResults({
  result,
  persisted,
}: {
  result: ExtendedResponse;
  persisted?: boolean;
}) {
  const [splitKey, setSplit] = useState<"time_split" | "service_split">(
    "time_split",
  );
  const [resource, setResource] = useState<"cpu" | "memory">("memory");
  const [policy, setPolicy] = useState("static");
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (!persisted) heading.current?.focus();
  }, [result, persisted]);
  const split = result[splitKey];
  const unit = resource === "cpu" ? "cores" : "GiB";
  const comparison = split[resource];
  const taskPolicy = split.policies[policy];

  return (
    <section className="exp-result" aria-label="Extended experiment results">
      <header className="exp-result-heading">
        <div>
          <h2 tabIndex={-1} ref={heading}>
            Extended CPU + Memory + Tasks
          </h2>
          <p>
            extended-v1 · {result.parameters.n_services} services ·{" "}
            {result.parameters.n_steps} steps ·{" "}
            {number(result.execution_time_seconds)} s engine time
          </p>
        </div>
        <div className="diag-exports">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => downloadExperiment(result, "json")}
          >
            Export JSON
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => downloadExperiment(result, "csv")}
          >
            Export metrics CSV
          </button>
        </div>
      </header>
      <p className="exp-context">
        {persisted || result.saved
          ? "Saved to history."
          : result.saved === false
            ? "Run completed without a history save."
            : "Offline experiment."}{" "}
        {result.run_id && !persisted && (
          <Link to={"/history/" + encodeURIComponent(result.run_id)}>
            View saved run
          </Link>
        )}
      </p>
      <div className="exp-panel diag-section">
        <div className="diag-controls">
          <label>
            Evaluation split{" "}
            <select
              value={splitKey}
              onChange={(event) =>
                setSplit(
                  event.target.value === "time_split"
                    ? "time_split"
                    : "service_split",
                )
              }
            >
              <option value="time_split">TIME</option>
              <option value="service_split">SERVICE</option>
            </select>
          </label>
          <label>
            Resource{" "}
            <select
              value={resource}
              onChange={(event) =>
                setResource(event.target.value === "cpu" ? "cpu" : "memory")
              }
            >
              <option value="cpu">CPU</option>
              <option value="memory">Memory</option>
            </select>
          </label>
        </div>
        <p>
          Each resource uses its own causal static capacity. Joint validation
          counts rows where either resource is under-allocated.
          Demand-to-capacity utilization compares observed workload demand with
          allocated capacity. Task consumption is shown separately below.
        </p>
        <div
          className="exp-table-wrap"
          role="region"
          aria-label="Extended policy comparison"
          tabIndex={0}
        >
          <table className="exp-table">
            <thead>
              <tr>
                {[
                  "Policy",
                  "Resource feasible",
                  "Jointly feasible",
                  "MAE (" + unit + ")",
                  "MSE (" + unit + "²)",
                  "RMSE (" + unit + ")",
                  "Test violation",
                  "Savings",
                  "Demand / capacity",
                  "Wastage",
                  "Joint validation violation",
                  "Joint test violation",
                ].map((label) => (
                  <th scope="col" key={label}>
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Object.entries(comparison.methods).map(([name, metric]) => (
                <tr key={name}>
                  <th scope="row">{name}</th>
                  <td>{metric.is_feasible ? "Yes" : "No"}</td>
                  <td>
                    {split.policies[name].jointly_feasible ? "Yes" : "No"}
                  </td>
                  <td>{number(metric.mae)}</td>
                  <td>{number(metric.mse)}</td>
                  <td>{number(metric.rmse)}</td>
                  <td>
                    {percent(metric.violation_rate)}
                    {!metric.is_feasible && " (raw)"}
                  </td>
                  {[metric.savings, metric.utilization, metric.wastage].map(
                    (value, i) => (
                      <td key={i}>
                        {metric.is_feasible ? percent(value) : "—"}
                      </td>
                    ),
                  )}
                  <td>
                    {percent(
                      split.policies[name].validation_joint_violation_rate,
                    )}
                  </td>
                  <td>
                    {percent(split.policies[name].test_joint_violation_rate)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {comparison.traces?.length ? (
          <HeldOutCharts
            key={splitKey + resource}
            traces={comparison.traces}
            unit={unit}
          />
        ) : (
          <p>Sampled traces are unavailable for this run.</p>
        )}
      </div>
      <div className="exp-panel">
        <header className="exp-panel-heading">
          <h3>Task execution</h3>
        </header>
        <div className="diag-section">
          <label className="diag-controls">
            Scheduling policy{" "}
            <select
              value={policy}
              onChange={(event) => setPolicy(event.target.value)}
            >
              {Object.keys(split.policies).map((name) => (
                <option key={name}>{name}</option>
              ))}
            </select>
          </label>
          <p>
            {split.offered_tasks} identical offered tasks per policy. Times are
            simulated. Static remains the reference comparator when it misses
            the joint target.
          </p>
          {!taskPolicy.tasks && (
            <p>
              Task execution is unavailable because the dynamic policy missed
              joint validation feasibility.
            </p>
          )}
        </div>
        {taskPolicy.tasks && <TaskResults tasks={taskPolicy.tasks} />}
      </div>
    </section>
  );
}
