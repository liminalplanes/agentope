import { ChevronDown } from "lucide-react";
import { Verdict } from "#/components/verdict";

// One scale for the whole drawing: x = (value + 0.05) * 1280 over −0.05 … 0.20.
const scale = (v: number) => (v + 0.05) * 1280;
const ticks = [-0.05, 0, 0.05, 0.1, 0.15, 0.2];
const estimate = 0.088;
const ci: [number, number] = [0.041, 0.134];

const figures = [
	["Current agent", "0.583"],
	["Target (SNIPS)", "0.671"],
	["95% CI", "+0.041, +0.134"],
	["Effective sample", "337 · 33%"],
	["Explored decisions", "1,012"],
	["Support violations", "0"],
] as const;

const assumptions = [
	"Logged propensities are the probabilities actually used",
	"Whether a decision was explored did not depend on its context",
	"Which tool is called matters, not its arguments or wording",
	"Only tool_choice changes; later steps behave as before",
	"A ticket with no outcome within 3d was not resolved",
];

function tickLabel(t: number) {
	if (t === 0) return "0";
	return t < 0 ? `−${Math.abs(t).toFixed(2)}` : t.toFixed(2);
}

export function ExampleReport() {
	return (
		<figure className="m-0 min-w-0 rounded-xl border bg-card p-6">
			<div className="flex items-start justify-between gap-3">
				<div className="min-w-0 font-mono text-xs leading-relaxed text-muted-foreground">
					<p className="m-0 truncate">tool_choice · lookup_when_order_number</p>
					<p className="m-0">L1 Logged · ε-exploration</p>
				</div>
				<Verdict kind="ok" />
			</div>

			<p className="mt-6 mb-1 font-mono text-5xl leading-none font-semibold tracking-tighter tabular-nums">
				+0.088
			</p>
			<p className="m-0 text-sm text-muted-foreground">
				more tickets resolved than the current agent
			</p>

			<svg
				viewBox="-16 0 352 50"
				className="mt-6 w-full"
				role="img"
				aria-label="95% interval from +0.041 to +0.134, estimate +0.088, zero for reference"
			>
				<line
					x1="0"
					y1="20"
					x2="320"
					y2="20"
					strokeWidth="1.5"
					className="stroke-border"
				/>
				<rect
					x={scale(ci[0])}
					y="12"
					width={scale(ci[1]) - scale(ci[0])}
					height="16"
					rx="3"
					className="fill-foreground/12"
				/>
				<line
					x1={scale(0)}
					y1="6"
					x2={scale(0)}
					y2="34"
					strokeDasharray="2 3"
					className="stroke-muted-foreground"
				/>
				<circle
					cx={scale(estimate)}
					cy="20"
					r="4.5"
					className="fill-foreground"
				/>
				<g
					textAnchor="middle"
					className="fill-muted-foreground font-mono text-[10.5px]"
				>
					{ticks.map((t) => (
						<text key={t} x={scale(t)} y="48">
							{tickLabel(t)}
						</text>
					))}
				</g>
			</svg>

			<dl className="mt-5 mb-0 grid grid-cols-2 gap-x-6 gap-y-4 border-t pt-5 sm:grid-cols-3">
				{figures.map(([label, value]) => (
					<div key={label} className="min-w-0">
						<dt className="text-xs text-muted-foreground">{label}</dt>
						<dd className="m-0 mt-1 truncate font-mono text-sm tabular-nums">
							{value}
						</dd>
					</div>
				))}
			</dl>

			<details className="group mt-5 border-t pt-4 text-sm">
				<summary className="flex cursor-pointer list-none items-center justify-between text-muted-foreground hover:text-foreground [&::-webkit-details-marker]:hidden">
					This estimate assumes {assumptions.length} things
					<ChevronDown className="size-4 transition-transform group-open:rotate-180" />
				</summary>
				<ul className="mt-3 mb-0 grid list-disc gap-1 pl-4 text-muted-foreground">
					{assumptions.map((a) => (
						<li key={a}>{a}</li>
					))}
				</ul>
			</details>
		</figure>
	);
}
