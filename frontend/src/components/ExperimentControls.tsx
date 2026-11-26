import { AlertCircle, LoaderCircle, Play, Timer } from "lucide-react";
import type { ReactNode } from "react";

interface NumberFieldProps {
  id: string;
  label: string;
  hint: string;
  value: string;
  onChange: (value: string) => void;
  min: number;
  max?: number;
  step?: number | "any";
  invalid?: boolean;
}

export function NumberField({
  id,
  label,
  hint,
  value,
  onChange,
  min,
  max,
  step = 1,
  invalid,
}: NumberFieldProps) {
  return (
    <div className="exp-field">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        type="number"
        required
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={invalid || undefined}
        aria-describedby={`${id}-hint`}
      />
      <small id={`${id}-hint`}>{hint}</small>
    </div>
  );
}

interface RunActionsProps {
  loading: boolean;
  elapsed: number;
  onCancel: () => void;
  error: string;
  action: string;
  busyLabel: string;
  disabled?: boolean;
  icon?: ReactNode;
}

export function RunActions({
  loading,
  elapsed,
  onCancel,
  error,
  action,
  busyLabel,
  disabled,
  icon,
}: RunActionsProps) {
  return (
    <div className="exp-actions">
      {error && (
        <div className="exp-error" role="alert">
          <AlertCircle size={16} aria-hidden="true" />
          {error}
        </div>
      )}
      <div className="exp-action-line">
        <button
          type="submit"
          className="btn btn-primary"
          disabled={loading || disabled}
        >
          {loading ? (
            <LoaderCircle
              size={15}
              className="exp-spinner"
              aria-hidden="true"
            />
          ) : (
            (icon ?? <Play size={15} aria-hidden="true" />)
          )}
          {loading ? busyLabel : action}
        </button>
        {loading && (
          <>
            <span
              className="exp-clock"
              role="timer"
              aria-label="Elapsed request time"
            >
              <Timer size={15} aria-hidden="true" />
              {elapsed.toFixed(1)} s
            </span>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={onCancel}
            >
              Cancel request
            </button>
          </>
        )}
      </div>
    </div>
  );
}
