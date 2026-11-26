import React, { useEffect, useRef, useState } from "react";
import { getLimits, runSimulationCsv, ApiError } from "../api/client";
import { LimitsResponse, SimulationResponse } from "../types/api";
import { DisclaimerBanner } from "../components/DisclaimerBanner";
import { SimulationResultView } from "../components/SimulationResultView";

export const UploadPage: React.FC = () => {
  const [limits, setLimits] = useState<LimitsResponse>({
    max_services: 50,
    max_steps: 1000,
    max_csv_bytes: 5242880,
    timeout_seconds: 60,
    history_limit: 100,
  });

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [targetViolation, setTargetViolation] = useState(0.01);

  const [isLoading, setIsLoading] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [result, setResult] = useState<SimulationResponse | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    getLimits()
      .then((data) => setLimits(data))
      .catch((_) => {
        // Fallback limits
      });
  }, []);

  const handleFileChange = (file: File | null) => {
    setErrorMsg(null);
    if (!file) {
      setSelectedFile(null);
      return;
    }

    if (file.size > limits.max_csv_bytes) {
      setErrorMsg(
        `File size (${(file.size / (1024 * 1024)).toFixed(2)} MB) exceeds maximum allowed limit of ${(
          limits.max_csv_bytes /
          (1024 * 1024)
        ).toFixed(1)} MB.`
      );
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }

    setSelectedFile(file);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileChange(e.dataTransfer.files[0]);
    }
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
  };

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setErrorMsg("Please select a valid CSV workload file.");
      return;
    }

    if (targetViolation <= 0 || targetViolation >= 1) {
      setErrorMsg("Target violation must be between 0 and 1.");
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
      const data = await runSimulationCsv(
        selectedFile,
        targetViolation,
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
          setErrorMsg("Simulation timed out on backend.");
        } else if (err.status === 499) {
          setErrorMsg("Upload evaluation cancelled.");
        } else {
          setErrorMsg(err.message || "Evaluation failed.");
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
    <div className="upload-page">
      <DisclaimerBanner />

      <section className="card">
        <h1 className="card-title" style={{ fontSize: "1.4rem" }}>
          Upload Workload CSV
        </h1>
        <p style={{ color: "var(--text-muted)", fontSize: "0.95rem", marginBottom: "1rem" }}>
          Upload your own workload trace to test machine learning and baseline
          right-sizing algorithms.
        </p>

        <div className="card" style={{ backgroundColor: "var(--neutral-bg)" }}>
          <h2 style={{ fontSize: "0.9rem", fontWeight: 600, marginBottom: "0.25rem" }}>
            Expected CSV Format
          </h2>
          <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginBottom: "0.5rem" }}>
            The CSV file must include headers for <code>service_id</code>,{" "}
            <code>timestamp</code> (ISO-8601 or integer step), and <code>cpu_demand</code>:
          </p>
          <pre className="code-block">
{`service_id,timestamp,cpu_demand
svc_1,2026-01-01T00:00:00Z,0.42
svc_1,2026-01-01T00:05:00Z,0.38`}
          </pre>
          <p style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
            At least 3 services and 482 steps per service. Maximum file size:{" "}
            {(limits.max_csv_bytes / (1024 * 1024)).toFixed(1)} MB.
          </p>
        </div>

        <form onSubmit={handleUploadSubmit} noValidate>
          <div
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            style={{
              border: "2px dashed var(--border)",
              borderRadius: "var(--radius-md)",
              padding: "2rem 1rem",
              textAlign: "center",
              marginBottom: "1rem",
              backgroundColor: "var(--surface-raised)",
              cursor: "pointer",
            }}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              type="file"
              ref={fileInputRef}
              accept=".csv,text/csv"
              style={{ display: "none" }}
              onChange={(e) => handleFileChange(e.target.files?.[0] || null)}
              disabled={isLoading}
            />
            <div style={{ fontWeight: 600, marginBottom: "0.25rem" }}>
              {selectedFile ? selectedFile.name : "Choose CSV or drag and drop here"}
            </div>
            <div style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
              {selectedFile
                ? `${(selectedFile.size / 1024).toFixed(1)} KB selected`
                : `Accepts standard CSV up to ${(limits.max_csv_bytes / (1024 * 1024)).toFixed(1)} MB`}
            </div>
          </div>

          <div className="form-group" style={{ maxWidth: 320 }}>
            <label htmlFor="target-violation-csv" className="form-label">
              Target Violation Rate (SLA threshold)
            </label>
            <input
              id="target-violation-csv"
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
              disabled={isLoading || !selectedFile}
            >
              {isLoading
                ? `Evaluating CSV... (${elapsedSeconds}s)`
                : "Upload and Evaluate"}
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
