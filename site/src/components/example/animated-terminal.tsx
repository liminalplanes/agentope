import { RotateCcw } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "#/components/ui/button";
import { excerpt, sampled, signed } from "#/lib/example";
import { cn } from "#/lib/utils";

type Line = { kind: "cmd" | "out" | "gap"; text: string; step: number };

/** Cut a long output line at a natural break, so it fits the terminal. */
function tidy(line: string): string {
	const breaks = [
		" · logging model",
		"  → ",
		" (needs",
		" (availability",
		" → Level",
	];
	let cut = line;
	for (const b of breaks) {
		const i = cut.indexOf(b);
		if (i > 0) cut = cut.slice(0, i);
	}
	return cut;
}

const STEPS = [
	{
		title: "Check what's possible",
		note: "Your traces are read as they are. No exploration was logged, but they include the messages, so agentope can use Level 2.",
	},
	{
		title: "Import the traces",
		note: "Each conversation's first move becomes a decision: what the agent did, in what situation, and what it saw.",
	},
	{
		title: "Ask the model again",
		note: "The same messages go back to the same model, 64 times each, to learn how likely every logged choice was.",
	},
	{
		title: "Evaluate the change",
		note: "The rule “look up the order whenever there's an order number”, measured on tickets resolved within three days.",
	},
];

function buildLines(): Line[] {
	const s = sampled.steps;
	const blocks: { cmd: string; out: string }[] = [
		{
			cmd: "agentope check --traces traces.otlp.json.gz",
			out: excerpt(s.check.output, [
				"tool_choice ·",
				"Level 1",
				"Level 2",
				"Level 3",
				"Best available",
			]),
		},
		{
			cmd: "agentope import --traces traces.otlp.json.gz -o decisions.jsonl",
			out: excerpt(s.import.output, ["traces.otlp.json.gz", "chosen", "wrote"]),
		},
		{
			cmd: "agentope sample decisions.jsonl -o samples.jsonl --n 64 --yes",
			out: s.sample.output.split("\n")[0],
		},
		{
			cmd: "agentope eval decisions.jsonl --samples samples.jsonl --outcomes helpdesk.csv \\\n    --horizon 3d --target policies.py:lookup_when_order_number",
			out: excerpt(s.eval.output, [
				"Evidence level",
				"Logging policy",
				"Target policy",
				"Difference",
				"Verdict",
			]),
		},
	];
	const lines: Line[] = [];
	blocks.forEach((block, step) => {
		if (step > 0) lines.push({ kind: "gap", text: "", step });
		block.cmd.split("\n").forEach((text, i) => {
			lines.push({ kind: "cmd", text: i === 0 ? `$ ${text}` : text, step });
		});
		for (const text of block.out.split("\n")) {
			lines.push({ kind: "out", text: tidy(text), step });
		}
	});
	return lines;
}

type Phase = "idle" | "running" | "done";

/**
 * The example's real session, replayed: commands are typed, output appears. Starts when
 * scrolled into view; shows everything at once with reduced motion or without JavaScript.
 */
export function AnimatedTerminal() {
	const lines = useMemo(buildLines, []);
	const [phase, setPhase] = useState<Phase>("idle");
	const [line, setLine] = useState(0);
	const [chars, setChars] = useState(0);
	const ref = useRef<HTMLElement>(null);
	const report = sampled.report;

	const start = useCallback(() => {
		setLine(0);
		setChars(0);
		setPhase("running");
	}, []);

	// Start once the terminal is on screen (or show it all with reduced motion).
	useEffect(() => {
		if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
			setPhase("done");
			return;
		}
		const node = ref.current;
		if (!node) return;
		const rect = node.getBoundingClientRect();
		if (rect.top < window.innerHeight && rect.bottom > 0) {
			start();
			return;
		}
		const observer = new IntersectionObserver(
			(entries) => {
				if (entries.some((e) => e.isIntersecting)) {
					start();
					observer.disconnect();
				}
			},
			{ threshold: 0.35 },
		);
		observer.observe(node);
		return () => observer.disconnect();
	}, [start]);

	// Advance the animation.
	useEffect(() => {
		if (phase !== "running") return;
		if (line >= lines.length) {
			setPhase("done");
			return;
		}
		const current = lines[line];
		let delay = 45;
		let next = () => setLine((l) => l + 1);
		if (current.kind === "cmd") {
			if (chars < current.text.length) {
				delay = chars === 0 ? 250 : 22;
				next = () => setChars((c) => c + 1);
			} else {
				delay = 380;
				next = () => {
					setChars(0);
					setLine((l) => l + 1);
				};
			}
		} else if (current.kind === "gap") {
			delay = 1500;
		}
		const timer = setTimeout(next, delay);
		return () => clearTimeout(timer);
	}, [phase, line, chars, lines]);

	const activeStep =
		phase === "done"
			? STEPS.length - 1
			: (lines[Math.min(line, lines.length - 1)]?.step ?? 0);
	const [lo, hi] = report.estimates.ci95 as [number, number];

	return (
		<div className="grid grid-cols-1 gap-8 lg:grid-cols-[15rem_minmax(0,1fr)] lg:gap-10">
			<ol className="m-0 flex list-none flex-col gap-1 p-0">
				{STEPS.map((step, i) => (
					<li
						key={step.title}
						className={cn(
							"rounded-md px-3 py-2.5 transition-colors",
							i === activeStep ? "bg-muted" : "",
						)}
					>
						<p
							className={cn(
								"m-0 flex items-baseline gap-2.5 text-sm",
								i <= activeStep || phase === "idle"
									? "text-foreground"
									: "text-muted-foreground",
							)}
						>
							<span className="font-mono text-xs text-muted-foreground">
								{i + 1}
							</span>
							{step.title}
						</p>
						{i === activeStep && phase !== "idle" && (
							<p className="mt-1.5 mb-0 pl-5 text-xs leading-relaxed text-muted-foreground">
								{step.note}
							</p>
						)}
					</li>
				))}
			</ol>

			<div className="min-w-0">
				<section
					ref={ref}
					aria-label="An agentope session, replayed"
					className="term overflow-hidden rounded-[4px] border bg-card"
					data-phase={phase}
				>
					<div className="flex h-8 items-center justify-between border-b bg-muted/60 pr-1 pl-3">
						<span className="font-mono text-[0.7rem] tracking-wide text-muted-foreground">
							terminal · support-agent traces
						</span>
						<Button
							type="button"
							variant="ghost"
							size="icon"
							className="size-6 [&_svg]:size-3.5"
							aria-label="Replay"
							onClick={start}
							disabled={phase === "running"}
						>
							<RotateCcw />
						</Button>
					</div>
					<pre className="m-0 overflow-x-auto px-4 py-3.5 font-mono text-[0.76rem] leading-relaxed">
						{lines.map((l, i) => {
							const hidden = phase === "running" && i > line;
							const typing =
								phase === "running" && i === line && l.kind === "cmd";
							const text = typing ? l.text.slice(0, chars) : l.text;
							return (
								<span
									// biome-ignore lint/suspicious/noArrayIndexKey: lines are static
									key={i}
									className={cn(
										"term-line block min-h-[1.3em] whitespace-pre",
										l.kind === "cmd"
											? "text-foreground"
											: "text-muted-foreground",
										l.kind === "gap" && "h-3 min-h-0",
									)}
									style={hidden ? { visibility: "hidden" } : undefined}
								>
									{text}
									{typing && (
										<span className="ml-px inline-block h-[1.05em] w-[0.5em] translate-y-[0.15em] animate-pulse bg-foreground/70" />
									)}
								</span>
							);
						})}
					</pre>
				</section>
				<p className="mt-3 mb-0 text-xs text-muted-foreground">
					Excerpts of a real run on simulated traces. The rule would have
					resolved {signed(report.estimates.difference as number)} more tickets
					(95%: {signed(lo)} to {signed(hi)}); the true effect, known because
					it's simulated, is {signed(sampled.truth.lookup_difference)}.
				</p>
			</div>
		</div>
	);
}
