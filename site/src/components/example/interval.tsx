import { signed } from "#/lib/example";

const WIDTH = 320;
const STEP = 0.05;

/**
 * A 95% interval on one scale: the band, the estimate, a dashed zero line, and
 * optionally the true value (known only in a simulation).
 */
export function IntervalChart({
	estimate,
	lo,
	hi,
	truth,
	domain,
}: {
	estimate: number;
	lo: number;
	hi: number;
	truth?: number;
	/** A fixed [min, max] scale, so several charts can be compared directly. */
	domain?: [number, number];
}) {
	const values = [0, lo, hi, estimate, ...(truth === undefined ? [] : [truth])];
	const min =
		domain?.[0] ?? Math.floor((Math.min(...values) - 0.02) / STEP) * STEP;
	const max =
		domain?.[1] ?? Math.ceil((Math.max(...values) + 0.02) / STEP) * STEP;
	const x = (v: number) => ((v - min) / (max - min)) * WIDTH;
	const ticks: number[] = [];
	for (let t = min; t <= max + 1e-9; t += STEP)
		ticks.push(Math.round(t * 100) / 100);
	const top = truth === undefined ? 0 : 18;

	return (
		<svg
			viewBox={`-18 0 ${WIDTH + 36} ${52 + top}`}
			className="w-full"
			role="img"
			aria-label={`95% interval from ${signed(lo)} to ${signed(hi)}, estimate ${signed(estimate)}${
				truth === undefined ? "" : `, true value ${signed(truth)}`
			}`}
		>
			{truth !== undefined && (
				<g>
					<line
						x1={x(truth)}
						y1={top - 4}
						x2={x(truth)}
						y2={top + 32}
						strokeWidth="1.5"
						className="stroke-ok"
					/>
					<text
						x={x(truth)}
						y={top - 8}
						textAnchor="middle"
						className="fill-ok font-mono text-[10.5px]"
					>
						true {signed(truth)}
					</text>
				</g>
			)}
			<line
				x1="0"
				y1={top + 20}
				x2={WIDTH}
				y2={top + 20}
				strokeWidth="1.5"
				className="stroke-border"
			/>
			<rect
				x={x(lo)}
				y={top + 12}
				width={x(hi) - x(lo)}
				height="16"
				rx="3"
				className="fill-foreground/12"
			/>
			<line
				x1={x(0)}
				y1={top + 6}
				x2={x(0)}
				y2={top + 34}
				strokeDasharray="2 3"
				className="stroke-muted-foreground"
			/>
			<circle
				cx={x(estimate)}
				cy={top + 20}
				r="4.5"
				className="fill-foreground"
			/>
			<g
				textAnchor="middle"
				className="fill-muted-foreground font-mono text-[10.5px]"
			>
				{ticks.map((t) => (
					<text key={t} x={x(t)} y={top + 48}>
						{t === 0
							? "0"
							: t < 0
								? `−${Math.abs(t).toFixed(2)}`
								: t.toFixed(2)}
					</text>
				))}
			</g>
		</svg>
	);
}
