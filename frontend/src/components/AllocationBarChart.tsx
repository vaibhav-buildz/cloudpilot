import type { CSSProperties } from "react";
import { ChevronDown } from "lucide-react";
import "./allocation-chart.css";

export interface AllocationBarItem {
  label: string;
  value: number;
  color?: string;
  sublabel?: string;
}

interface AllocationBarChartProps {
  title: string;
  items: AllocationBarItem[];
  unit?: string;
}

export function AllocationBarChart({
  title,
  items,
  unit = "CPU units",
}: AllocationBarChartProps) {
  if (!items.length) return null;

  const values = items.map((item) => item.value);
  const min = Math.min(0, ...values);
  const max = Math.max(0, ...values);
  const roughStep = (max - min || 1) / 4;
  const base = 10 ** Math.floor(Math.log10(roughStep));
  const step =
    ([1, 2, 2.5, 5, 10].find((tick) => tick * base >= roughStep) ?? 10) * base;
  const lower = Math.floor(min / step) * step;
  const upper = Math.max(lower + step, Math.ceil(max / step) * step);
  const ticks = Array.from(
    { length: Math.round((upper - lower) / step) + 1 },
    (_, i) => lower + i * step,
  );
  const position = (value: number) => (100 * (value - lower)) / (upper - lower);
  const format = (value: number) =>
    value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  const chartStyle = {
    "--allocation-grid-step": `${100 / (ticks.length - 1)}%`,
  } as CSSProperties;

  return (
    <figure className="allocation-chart" aria-label={title} style={chartStyle}>
      <figcaption>{title}</figcaption>
      <div className="allocation-axis" aria-hidden="true">
        <div>
          {ticks.map((tick) => (
            <span key={tick}>{format(tick)}</span>
          ))}
        </div>
      </div>
      {items.map((item) => {
        const bar = (
          <>
            <span className="allocation-label">{item.label}</span>
            <span className="allocation-track" aria-hidden="true">
              <span
                style={{
                  left: `${position(Math.min(0, item.value))}%`,
                  width: `${(100 * Math.abs(item.value)) / (upper - lower)}%`,
                  backgroundColor: item.color ?? "var(--muted)",
                }}
              />
            </span>
            <span className="allocation-number">
              {format(item.value)}
              {unit === "%" ? unit : ` ${unit}`}
              {item.sublabel && <ChevronDown size={13} aria-hidden="true" />}
            </span>
          </>
        );
        return item.sublabel ? (
          <details className="allocation-item" key={item.label}>
            <summary className="allocation-row">{bar}</summary>
            <p>{item.sublabel}</p>
          </details>
        ) : (
          <div className="allocation-row" key={item.label}>
            {bar}
          </div>
        );
      })}
    </figure>
  );
}
