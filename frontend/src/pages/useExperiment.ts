import { useEffect, useRef, useState } from "react";
import { ApiError, getLimits } from "../api/client";
import type { ExperimentResult, LimitsResponse } from "../types/api";

export const MIN_SERVICES = 3;
export const MIN_STEPS = 482;
export const TARGET_MIN = 0.005;
export const TARGET_MAX = 0.05;
export const TARGET_ERROR =
  "Target violation rate must be between 0.005 and 0.05 (0.5–5%).";

const defaultLimits: LimitsResponse = {
  max_services: 20,
  max_steps: 1000,
  max_csv_bytes: 5242880,
  timeout_seconds: 42,
  history_limit: 50,
};

export function useLimits() {
  const [limits, setLimits] = useState(defaultLimits);
  const [usingFallback, setUsingFallback] = useState(false);
  useEffect(() => {
    let active = true;
    getLimits().then(
      (data) => {
        if (active) setLimits(data);
      },
      () => {
        if (active) setUsingFallback(true);
      },
    );
    return () => {
      active = false;
    };
  }, []);
  return { limits, usingFallback };
}

export function useExperiment() {
  const controller = useRef<AbortController | null>(null);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState("");
  const [result, setResult] = useState<ExperimentResult | null>(null);

  useEffect(
    () => () => {
      controller.current?.abort();
      controller.current = null;
    },
    [],
  );

  useEffect(() => {
    if (startedAt === null) return;
    const timer = window.setInterval(() => {
      setElapsed((performance.now() - startedAt) / 1000);
    }, 100);
    return () => window.clearInterval(timer);
  }, [startedAt]);

  async function execute(
    request: (signal: AbortSignal) => Promise<ExperimentResult>,
  ) {
    if (controller.current) return;
    const active = new AbortController();
    controller.current = active;
    setError("");
    setResult(null);
    setElapsed(0);
    setStartedAt(performance.now());
    try {
      const response = await request(active.signal);
      if (controller.current === active) setResult(response);
    } catch (reason) {
      if (controller.current !== active) return;
      if (reason instanceof ApiError && reason.status === 499) {
        setError("Request cancelled. Check History if the run finished before cancellation.");
      } else if (reason instanceof ApiError) {
        const retryHint = reason.retryAfter
          ? ` Retry after ${reason.retryAfter} seconds.`
          : "";
        setError(
          reason.message +
            (reason.message.includes("Try again in") ? "" : retryHint),
        );
      } else {
        setError("The experiment response could not be read. Try again.");
      }
    } finally {
      if (controller.current === active) {
        controller.current = null;
        setStartedAt(null);
      }
    }
  }

  return {
    execute,
    cancel: () => controller.current?.abort(),
    loading: startedAt !== null,
    elapsed,
    error,
    setError,
    result,
  };
}
