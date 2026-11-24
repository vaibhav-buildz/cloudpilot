import React from "react";

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

export const AllocationBarChart: React.FC<AllocationBarChartProps> = ({
  title,
  items,
  unit = "CPU units",
}) => {
  if (!items.length) {
    return null;
  }

  const maxValue = Math.max(...items.map((i) => i.value), 1e-6);
  const chartHeight = items.length * 48 + 32;
  const barHeight = 22;
  const labelWidth = 140;
  const chartWidth = 560;
  const barAreaWidth = chartWidth - labelWidth - 80;

  return (
    <div className="chart-container" role="figure" aria-label={title}>
      <div style={{ fontWeight: 600, fontSize: "0.9rem", marginBottom: "0.75rem" }}>
        {title}
      </div>
      <div style={{ overflowX: "auto" }}>
        <svg
          viewBox={`0 0 ${chartWidth} ${chartHeight}`}
          width="100%"
          style={{ maxWidth: `${chartWidth}px`, display: "block" }}
        >
          {items.map((item, idx) => {
            const y = idx * 48 + 16;
            const barWidth = Math.max((item.value / maxValue) * barAreaWidth, 2);
            const fill = item.color || "#0284c7";

            return (
              <g key={item.label}>
                <text
                  x={labelWidth - 10}
                  y={y + 15}
                  textAnchor="end"
                  fill="currentColor"
                  fontSize="12"
                  fontFamily="inherit"
                >
                  {item.label}
                </text>
                <rect
                  x={labelWidth}
                  y={y}
                  width={barWidth}
                  height={barHeight}
                  fill={fill}
                  rx="3"
                />
                <text
                  x={labelWidth + barWidth + 8}
                  y={y + 15}
                  textAnchor="start"
                  fill="currentColor"
                  fontSize="11"
                  fontFamily="var(--font-mono)"
                >
                  {item.value.toLocaleString(undefined, { maximumFractionDigits: 1 })}{" "}
                  {unit}
                </text>
                {item.sublabel && (
                  <text
                    x={labelWidth}
                    y={y + barHeight + 10}
                    fill="var(--text-muted)"
                    fontSize="10"
                  >
                    {item.sublabel}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
};
