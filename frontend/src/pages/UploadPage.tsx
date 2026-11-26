import {
  Braces,
  FileSpreadsheet,
  FileUp,
  FolderOpen,
  Upload,
  X,
} from "lucide-react";
import { useRef, useState, type DragEvent, type FormEvent } from "react";
import { runSimulationCsv } from "../api/client";
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

const example = `service_id,timestamp,cpu_demand
api,2026-01-01T00:00Z,0.42
api,2026-01-01T00:05Z,0.38`;

export function UploadPage() {
  const { limits, usingFallback } = useLimits();
  const experiment = useExperiment();
  const [file, setFile] = useState<File | null>(null);
  const [target, setTarget] = useState("0.01");
  const [dragging, setDragging] = useState(false);
  const [fraction, setFraction] = useState<number | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const maxSize = (limits.max_csv_bytes / (1024 * 1024)).toFixed(1);

  function selectFile(files: FileList | null) {
    if (experiment.loading || !files?.length) return;
    const candidate = files[0];
    let error = "";
    if (files.length > 1) error = "Choose one CSV file per experiment.";
    else if (candidate.size > limits.max_csv_bytes)
      error = `File size exceeds maximum allowed limit of ${maxSize} MB.`;
    else if (!candidate.size)
      error = "This file is empty. Choose a CSV with workload rows.";
    experiment.setError(error);
    setFile(error ? null : candidate);
    if (fileInput.current) fileInput.current.value = "";
  }

  function drop(event: DragEvent) {
    event.preventDefault();
    setDragging(false);
    selectFile(event.dataTransfer.files);
  }

  function upload(event: FormEvent) {
    event.preventDefault();
    if (!file) {
      experiment.setError("Choose a CSV workload file.");
      return;
    }
    if (file.size > limits.max_csv_bytes) {
      experiment.setError(
        `File size exceeds maximum allowed limit of ${maxSize} MB.`,
      );
      return;
    }
    const rate = Number(target);
    if (!(rate >= TARGET_MIN && rate <= TARGET_MAX)) {
      experiment.setError(TARGET_ERROR);
      document.getElementById("target-violation-csv")?.focus();
      return;
    }
    setFraction(null);
    void experiment.execute((signal) =>
      runSimulationCsv(file, rate, signal, setFraction),
    );
  }

  const uploadComplete = fraction === 1;
  return (
    <div className="exp-page">
      <header className="exp-title">
        <h1>CSV upload</h1>
        <p>
          Replay a workload trace to evaluate CPU allocation on your own service
          data.
        </p>
      </header>
      <div className="exp-workspace">
        <form noValidate onSubmit={upload} className="exp-panel">
          <header className="exp-panel-heading">
            <FileUp aria-hidden="true" />
            <h2>Workload file</h2>
          </header>
          <fieldset className="exp-section" disabled={experiment.loading}>
            <legend className="sr-only">CSV workload configuration</legend>
            <input
              ref={fileInput}
              type="file"
              aria-label="CSV workload file"
              accept=".csv,text/csv"
              hidden
              onChange={(e) => selectFile(e.target.files)}
            />
            <div
              className="exp-dropzone"
              data-dragging={dragging || undefined}
              onDragOver={(e) => {
                e.preventDefault();
                if (!experiment.loading) setDragging(true);
              }}
              onDragLeave={(e) => {
                if (!e.currentTarget.contains(e.relatedTarget as Node | null))
                  setDragging(false);
              }}
              onDrop={drop}
            >
              {file ? (
                <FileSpreadsheet
                  className="exp-drop-icon"
                  size={28}
                  aria-hidden="true"
                />
              ) : (
                <Upload
                  className="exp-drop-icon"
                  size={28}
                  aria-hidden="true"
                />
              )}
              <strong>{file ? file.name : "Drop your CSV here"}</strong>
              <small>
                {file
                  ? `${file.size.toLocaleString()} bytes selected`
                  : `UTF-8 CSV · Up to ${maxSize} MB`}
              </small>
              <div className="exp-file-actions">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => fileInput.current?.click()}
                >
                  <FolderOpen size={15} aria-hidden="true" />
                  {file ? "Change file" : "Choose file"}
                </button>
                {file && (
                  <button
                    type="button"
                    className="btn btn-secondary"
                    aria-label="Remove selected file"
                    onClick={() => {
                      setFile(null);
                      experiment.setError("");
                    }}
                  >
                    <X size={15} aria-hidden="true" />
                  </button>
                )}
              </div>
            </div>
            <NumberField
              id="target-violation-csv"
              label="Target violation rate"
              hint="0.005–0.05 · 0.01 equals 1%"
              min={TARGET_MIN}
              max={TARGET_MAX}
              step="any"
              value={target}
              onChange={(value) => {
                setTarget(value);
                experiment.setError("");
              }}
              invalid={experiment.error === TARGET_ERROR}
            />
            {experiment.loading && (
              <div className="exp-transfer">
                <div>
                  <span role="status">
                    {uploadComplete
                      ? "Upload complete · awaiting evaluation"
                      : "Transferring workload"}
                  </span>
                  {fraction !== null && (
                    <span>{Math.floor(fraction * 100)}%</span>
                  )}
                </div>
                <progress
                  aria-label="File transfer progress"
                  value={fraction ?? undefined}
                  max={1}
                />
              </div>
            )}
          </fieldset>
          <RunActions
            loading={experiment.loading}
            elapsed={experiment.elapsed}
            onCancel={experiment.cancel}
            error={experiment.error}
            action="Upload and evaluate"
            busyLabel={
              uploadComplete ? "Evaluating workload" : "Uploading workload"
            }
            icon={<Upload size={15} aria-hidden="true" />}
            disabled={!file}
          />
        </form>
        <aside className="exp-panel exp-aside" aria-label="CSV requirements">
          <header className="exp-panel-heading">
            <Braces aria-hidden="true" />
            <h2>Expected CSV format</h2>
          </header>
          <div className="exp-section">
            <dl className="exp-schema">
              <div>
                <dt>service_id</dt>
                <dd>Service identifier</dd>
              </div>
              <div>
                <dt>timestamp</dt>
                <dd>Sortable time or zero-padded step</dd>
              </div>
              <div>
                <dt>cpu_demand</dt>
                <dd>Finite, non-negative CPU demand</dd>
              </div>
            </dl>
            <pre className="exp-code">
              <code>{example}</code>
            </pre>
            <h3>Trace requirements</h3>
            <ul className="exp-requirements">
              <li>
                {MIN_SERVICES}–{limits.max_services} services per workload
              </li>
              <li>
                {MIN_STEPS}–{limits.max_steps.toLocaleString()} steps in the
                shortest trace
              </li>
              <li>Longer traces are trimmed to the shortest service trace.</li>
            </ul>
            {usingFallback && (
              <p className="exp-note">
                Server limits are unavailable. Default workload limits are
                shown.
              </p>
            )}
          </div>
        </aside>
      </div>
      {experiment.result && (
        <SimulationResultView result={experiment.result} source="csv" />
      )}
    </div>
  );
}
