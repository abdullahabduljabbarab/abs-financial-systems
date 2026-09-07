// A small dependency-free area chart for one series over time.

interface Point { label: string; value: number; }

export function AreaChart({ points, height = 200 }: { points: Point[]; height?: number }) {
  if (points.length < 2) {
    return <p className="muted">Not enough history yet for a trend.</p>;
  }
  const W = 1000;
  const H = height;
  const padX = 8;
  const padY = 18;
  const max = Math.max(...points.map((p) => p.value), 1);
  const stepX = (W - padX * 2) / (points.length - 1);
  const x = (i: number) => padX + i * stepX;
  const y = (v: number) => padY + (H - padY * 2) * (1 - v / max);

  const line = points.map((p, i) => `${i === 0 ? "M" : "L"} ${x(i).toFixed(1)} ${y(p.value).toFixed(1)}`).join(" ");
  const area = `${line} L ${x(points.length - 1).toFixed(1)} ${H - padY} L ${x(0).toFixed(1)} ${H - padY} Z`;
  const last = points[points.length - 1];

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={height} preserveAspectRatio="none" role="img">
        <defs>
          <linearGradient id="ac" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgba(53,214,191,0.30)" />
            <stop offset="100%" stopColor="rgba(53,214,191,0)" />
          </linearGradient>
        </defs>
        {[0.25, 0.5, 0.75].map((g) => (
          <line key={g} x1={padX} x2={W - padX} y1={padY + (H - padY * 2) * g} y2={padY + (H - padY * 2) * g} stroke="var(--border-soft)" strokeWidth="1" />
        ))}
        <path d={area} fill="url(#ac)" />
        <path d={line} fill="none" stroke="var(--teal)" strokeWidth="2.5" vectorEffect="non-scaling-stroke" />
        <circle cx={x(points.length - 1)} cy={y(last.value)} r="4" fill="var(--teal)" />
      </svg>
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6, fontFamily: "var(--mono)", fontSize: 12, color: "var(--faint)" }}>
        <span>{points[0].label}</span>
        <span>peak {max}</span>
        <span>{last.label}</span>
      </div>
    </div>
  );
}
