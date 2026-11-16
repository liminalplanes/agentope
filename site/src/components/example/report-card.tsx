import { ChevronDown } from "lucide-react";
import { IntervalChart } from "#/components/example/interval";
import { Verdict, type VerdictKind } from "#/components/verdict";
import {
	count,
	example,
	num,
	percent,
	type SavedReport,
	signed,
} from "#/lib/example";

/** The example's evaluation, drawn from the saved report. Pass `truth` to mark the true
 * difference (known only because the example is simulated). */
export function ReportCard({
	report = example.report,
	truth,
}: {
	report?: SavedReport;
	truth?: number;
}) {
	const r = report;
	const e = r.estimates;
	const d = r.diagnostics;
	const [lo, hi] = e.ci95 as [number, number];
	const difference = e.difference as number;
	const figures = [
		["Current agent", num(e.logging_mean)],
		["New rule (SNIPS)", num(e.snips as number)],
		["95% CI", `${signed(lo)}, ${signed(hi)}`],
		[
			"Effective sample",
			`${count(Math.round(d.ess))} · ${percent(d.ess_share)}`,
		],
		[r.level.level === 1 ? "Explored decisions" : "Decisions", count(d.n)],
		["Support violations", percent(d.support_violation_mass)],
	];

	return (
		<figure className="m-0 min-w-0 rounded-md border bg-card p-6">
			<div className="flex items-start justify-between gap-3">
				<div className="min-w-0 font-mono text-xs leading-relaxed text-muted-foreground">
					<p className="m-0 truncate">
						{r.decision_point} · {r.target.replace(/^policies\.py:/, "")}
					</p>
					<p className="m-0">
						L{r.level.level} {r.level.name} · {r.level.detail}
					</p>
				</div>
				<Verdict kind={r.verdict as VerdictKind} />
			</div>

			<p className="mt-6 mb-1 font-mono text-5xl leading-none font-semibold tracking-tighter tabular-nums">
				{signed(difference)}
			</p>
			<p className="m-0 text-sm text-muted-foreground">
				change in resolution rate vs. the current agent
			</p>

			<div className="mt-6">
				<IntervalChart estimate={difference} lo={lo} hi={hi} truth={truth} />
			</div>

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
					This estimate assumes {r.assumptions.length} things
					<ChevronDown className="size-4 transition-transform group-open:rotate-180" />
				</summary>
				<ul className="mt-3 mb-0 grid list-disc gap-1 pl-4 text-muted-foreground">
					{r.assumptions.map((a) => (
						<li key={a}>{a}</li>
					))}
				</ul>
			</details>
		</figure>
	);
}
