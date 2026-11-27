import type { ExperimentMode, LimitsResponse } from "../types/api";

export function ExperimentModeField({
  mode,
  limits,
  onChange,
}: {
  mode: ExperimentMode;
  limits: LimitsResponse;
  onChange: (mode: ExperimentMode) => void;
}) {
  const enabled = Boolean(
    limits.extended_max_services && limits.extended_max_steps,
  );
  return (
    <label className="exp-field diag-mode">
      <span>Experiment mode</span>
      <select
        value={mode}
        onChange={(event) =>
          onChange(
            event.target.value === "extended-v1" ? "extended-v1" : "cpu-only",
          )
        }
      >
        <option value="cpu-only">CPU-only — existing protocol</option>
        {enabled && (
          <option value="extended-v1">
            Extended CPU + Memory + Tasks — extended-v1
          </option>
        )}
      </select>
      {!enabled && (
        <small>
          Extended execution is offline.{" "}
          <a href="https://github.com/vaibhav-buildz/cloudpilot/blob/main/docs/extended_protocol.md">
            Extended protocol
          </a>
        </small>
      )}
    </label>
  );
}
