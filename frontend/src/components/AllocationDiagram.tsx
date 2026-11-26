/* Three isometric allocation layers on a shared projection. */
export function AllocationDiagram() {
  return (
    <svg
      className="allocation-diagram"
      viewBox="0 0 510 220"
      fill="none"
      aria-hidden="true"
    >
      <defs>
        <pattern
          id="board-dots"
          width="9"
          height="9"
          patternUnits="userSpaceOnUse"
        >
          <circle cx="2" cy="2" r=".72" fill="var(--muted)" opacity=".52" />
        </pattern>
        <radialGradient id="board-fade">
          <stop offset="0" stopColor="white" />
          <stop offset=".7" stopColor="white" stopOpacity=".9" />
          <stop offset="1" stopColor="white" stopOpacity="0" />
        </radialGradient>
        <mask id="board-mask">
          <ellipse
            cx="275"
            cy="111"
            rx="236"
            ry="126"
            fill="url(#board-fade)"
          />
        </mask>
      </defs>
      <rect
        width="510"
        height="220"
        fill="url(#board-dots)"
        mask="url(#board-mask)"
      />
      <g stroke="var(--diagram-line)" strokeWidth=".8" strokeLinejoin="round">
        <path d="m60 125 30 15 38-20 35 18 38-20m-95 40 25 13 41-21 16 8 39-20M309 171l41 20 59-30 32 16M332 151l28 14 42-21 37 18 23-12M294 68l53-27 19 9 40-20M333 88l34-17 22 11 42-21 30 15M204 86l-33-17-19 9-44-22-24 12" />
        {[
          [60, 125],
          [106, 158],
          [441, 177],
          [462, 150],
          [406, 30],
          [461, 76],
          [84, 68],
        ].map(([x, y]) => (
          <circle key={x} cx={x} cy={y} r="2.2" fill="var(--bg)" />
        ))}
      </g>
      {[122, 94, 66].map((y, layer) => (
        <g key={y} transform={`translate(265 ${y})`} strokeLinejoin="round">
          <path
            d="M-103 0 0-51.5 103 0 0 51.5Z"
            fill="var(--diagram-top)"
            stroke="var(--diagram-edge)"
          />
          <path
            d="M-103 0 0 51.5v10L-103 10Z"
            fill="var(--surface-raised)"
            stroke="var(--diagram-edge)"
          />
          <path
            d="M0 51.5 103 0v10L0 61.5Z"
            fill="var(--surface)"
            stroke="var(--diagram-edge)"
          />
          {Array.from({ length: 15 }, (_, i) => (
            <path
              key={i}
              d={`M${8 + i * 6.2} ${51.5 - (8 + i * 6.2) / 2 + 2.4}v4.5`}
              stroke="var(--diagram-line)"
              strokeWidth="1.4"
            />
          ))}
          {[0, 1, 2].map((i) => (
            <path
              key={i}
              d={`m${-90 + i * 7} ${11 + i * 3.5} 3 1.5`}
              stroke={
                layer === 2 ? "var(--accent-text)" : "var(--diagram-line)"
              }
              strokeWidth="1.5"
            />
          ))}
          {layer === 2 && (
            <g transform="matrix(1 .5 -1 .5 0 -42)">
              <rect
                width="84"
                height="84"
                rx="2"
                stroke="var(--diagram-line)"
                fill="var(--surface)"
              />
              {Array.from({ length: 16 }, (_, i) => {
                const x = 5 + (i % 4) * 19,
                  top = 5 + Math.floor(i / 4) * 19;
                const highlighted = [0, 1, 4, 5].includes(i);
                return (
                  <rect
                    key={i}
                    x={x}
                    y={top}
                    width="16.5"
                    height="16.5"
                    fill={
                      highlighted ? "var(--diagram-cell)" : "var(--diagram-top)"
                    }
                    stroke={
                      highlighted ? "var(--accent-text)" : "var(--diagram-line)"
                    }
                    strokeWidth=".85"
                  />
                );
              })}
            </g>
          )}
        </g>
      ))}
    </svg>
  );
}
