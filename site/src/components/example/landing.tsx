import { Check, Minus, Plug } from "lucide-react";
import { siOllama, siOpentelemetry, siVllm } from "simple-icons";
import { CodeBlock } from "#/components/docs/mdx-components";
import { IntervalChart } from "#/components/example/interval";
import { Verdict, type VerdictKind } from "#/components/verdict";
import ExploreShort from "#/content/example/explore-short.mdx";
import { example, type SavedReport, sampled, signed } from "#/lib/example";
import { cn } from "#/lib/utils";

/* ── What you can evaluate ───────────────────────────────────────────── */

const fits = [
	{
		what: "Which tool the agent calls first",
		example: "Look up the order before searching the help articles",
		level: "Any level",
	},
	{
		what: "Which model a request goes to",
		example: "Send short questions to the small model",
		level: "Any level",
	},
	{
		what: "When to hand over to a person",
		example: "Escalate every pro customer",
		level: "Any level",
	},
	{
		what: "A new prompt or model at that step",
		example: "Does the v2 system prompt pick better first moves?",
		level: "Needs the messages (Level 2+)",
	},
];

const misfits = [
	{
		what: "A whole new agent, or several changes at once",
		why: "Later steps are assumed to go as they did. Choose the agent per conversation with agentope.randomize instead.",
	},
	{
		what: "The quality of free-text answers",
		why: "agentope compares a few distinct options. Map answers to options first, or judge them some other way.",
	},
	{
		what: "Outcomes you don't record",
		why: "Every estimate is measured on an outcome you already track, linked by conversation.",
	},
];

export function Evaluable() {
	return (
		<div className="grid grid-cols-1 gap-12 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)] lg:gap-16">
			<div>
				<h3 className="m-0 flex items-center gap-2 font-medium">
					<Check className="size-4 text-ok" /> One decision, changed
				</h3>
				<ul className="m-0 mt-4 list-none divide-y border-y p-0">
					{fits.map((f) => (
						<li
							key={f.what}
							className="grid grid-cols-1 gap-x-6 gap-y-1 py-3.5 sm:grid-cols-[minmax(0,1fr)_10rem]"
						>
							<div>
								<p className="m-0">{f.what}</p>
								<p className="m-0 mt-0.5 text-sm text-muted-foreground">
									{f.example}
								</p>
							</div>
							<span className="font-mono text-xs leading-6 text-muted-foreground sm:text-right">
								{f.level}
							</span>
						</li>
					))}
				</ul>
			</div>
			<div>
				<h3 className="m-0 flex items-center gap-2 font-medium">
					<Minus className="size-4 text-muted-foreground" /> Not a fit (yet)
				</h3>
				<ul className="m-0 mt-4 list-none divide-y border-y p-0">
					{misfits.map((m) => (
						<li key={m.what} className="py-3.5">
							<p className="m-0">{m.what}</p>
							<p className="m-0 mt-0.5 text-sm text-muted-foreground">
								{m.why}
							</p>
						</li>
					))}
				</ul>
			</div>
		</div>
	);
}

/* ── Better evidence, on the same agent ──────────────────────────────── */

type Rung = {
	report: SavedReport;
	truth: number;
	title: string;
	have: string;
	note: string;
	current?: boolean;
	extra?: React.ReactNode;
};

export function EvidenceLadder() {
	const rungs: Rung[] = [
		{
			report: sampled.estimated as SavedReport,
			truth: sampled.truth.lookup_difference,
			title: "Level 3 · from what was logged",
			have: "Traces without the messages",
			note: "agentope models how the agent chose from what each trace recorded. Here the range just misses the true value: that model is slightly off, and nothing in the data can show it. So Level 3 only runs once you agree, and is never rated better than weak.",
		},
		{
			report: sampled.report as SavedReport,
			truth: sampled.truth.lookup_difference,
			title: "Level 2 · asking the model again",
			have: "Traces with the messages (this example)",
			note: "A tight range around the true value. It relies on the model behaving today as it did then, which the report checks.",
			current: true,
		},
		{
			report: example.report as SavedReport,
			truth: example.truth.lookup_difference,
			title: "Level 1 · with exploration",
			have: `Add exploration: ${Math.round(example.meta.epsilon * 100)}% of conversations try a random safe option`,
			note: `Relies on nothing about the model. The range is wider because only the explored conversations count; more traffic or time narrows it. (Exploring changes slightly what the agent did, so its true value differs a little.)`,
			extra: (
				<div className="min-w-0">
					<ExploreShort components={{ pre: CodeBlock }} />
				</div>
			),
		},
	];
	const ranges = rungs.flatMap((r) => [
		...(r.report.estimates.ci95 as number[]),
		r.truth,
		0,
	]);
	const domain: [number, number] = [
		Math.floor((Math.min(...ranges) - 0.01) / 0.05) * 0.05,
		Math.ceil((Math.max(...ranges) + 0.01) / 0.05) * 0.05,
	];

	return (
		<ol className="m-0 flex list-none flex-col gap-0 divide-y border-y p-0">
			{rungs.map((rung) => {
				const [lo, hi] = rung.report.estimates.ci95 as [number, number];
				return (
					<li
						key={rung.title}
						className="grid grid-cols-1 gap-6 py-8 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)] lg:gap-14"
					>
						<div>
							<div className="flex items-center gap-2">
								<h3 className="m-0 font-medium">{rung.title}</h3>
								{rung.current && (
									<span className="font-mono text-[0.7rem] text-muted-foreground">
										← you are here
									</span>
								)}
							</div>
							<p className="mt-1 mb-0 text-sm">{rung.have}</p>
							<p className="mt-3 mb-0 text-sm text-muted-foreground">
								{rung.note}
							</p>
						</div>
						<div className="flex min-w-0 flex-col gap-3">
							<div className="max-w-xl rounded-md border bg-card px-5 pt-4 pb-3">
								<div className="mb-1 flex items-center justify-between gap-3 text-sm">
									<span className="font-mono">
										{signed(rung.report.estimates.difference as number)}{" "}
										<span className="text-muted-foreground">
											[{signed(lo)}, {signed(hi)}]
										</span>
									</span>
									<Verdict kind={rung.report.verdict as VerdictKind} />
								</div>
								<IntervalChart
									estimate={rung.report.estimates.difference as number}
									lo={lo}
									hi={hi}
									truth={rung.truth}
									domain={domain}
								/>
							</div>
							{rung.extra}
						</div>
					</li>
				);
			})}
		</ol>
	);
}

/* ── Works with ──────────────────────────────────────────────────────── */

type Logo = { kind: "icon"; path: string } | { kind: "image"; src: string };

export type Integration = {
	name: string;
	detail: string;
	href: string;
	logo: Logo | null;
	tested: boolean;
};

const otel: Logo = { kind: "icon", path: siOpentelemetry.path };
const arize: Logo = { kind: "image", src: "/logos/arize.jpg" };

export const traceTools: Integration[] = [
	{
		name: "OpenTelemetry GenAI",
		detail: "The gen_ai.* conventions for model calls and tool calls",
		href: "https://opentelemetry.io/docs/specs/semconv/gen-ai/",
		logo: otel,
		tested: true,
	},
	{
		name: "OpenTelemetry Collector",
		detail: "Exports from the file exporter, optionally gzipped",
		href: "https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/exporter/fileexporter",
		logo: otel,
		tested: true,
	},
	{
		name: "OpenInference",
		detail: "Arize's conventions for LLM and tool spans",
		href: "https://github.com/Arize-ai/openinference",
		logo: arize,
		tested: true,
	},
	{
		name: "Arize Phoenix",
		detail: "OTLP exports of Phoenix traces",
		href: "https://github.com/Arize-ai/phoenix",
		logo: arize,
		tested: false,
	},
	{
		name: "Langfuse",
		detail: "OTLP exports of Langfuse traces",
		href: "https://langfuse.com",
		logo: { kind: "image", src: "/logos/langfuse.png" },
		tested: false,
	},
];

export const modelTools: Integration[] = [
	{
		name: "Any OpenAI-compatible API",
		detail: "The chat-completions API, with retries and rate-limit handling",
		href: "/docs/sampling",
		logo: null,
		tested: true,
	},
	{
		name: "vLLM",
		detail: "Many samples per request with --n-per-request",
		href: "https://docs.vllm.ai",
		logo: { kind: "icon", path: siVllm.path },
		tested: false,
	},
	{
		name: "Ollama",
		detail: "Local models through its OpenAI-compatible endpoint",
		href: "https://ollama.com",
		logo: { kind: "icon", path: siOllama.path },
		tested: false,
	},
	{
		name: "llama.cpp",
		detail: "llama-server's OpenAI-compatible endpoint",
		href: "https://github.com/ggml-org/llama.cpp",
		logo: { kind: "image", src: "/logos/ggml.jpg" },
		tested: false,
	},
];

export function IntegrationLogo({
	logo,
	large = false,
}: {
	logo: Logo | null;
	large?: boolean;
}) {
	const size = large ? "size-7" : "size-5";
	if (logo === null) {
		return <Plug aria-hidden="true" className={cn(size, "text-current")} />;
	}
	if (logo.kind === "icon") {
		return (
			<svg
				viewBox="0 0 24 24"
				aria-hidden="true"
				className={cn(size, "fill-current")}
			>
				<path d={logo.path} />
			</svg>
		);
	}
	return (
		<img
			src={logo.src}
			alt=""
			width={large ? 28 : 24}
			height={large ? 28 : 24}
			className={cn(
				large ? "size-7" : "size-6",
				"rounded-[5px] grayscale transition-[filter,opacity] group-hover:grayscale-0",
				large && "opacity-70 group-hover:opacity-100",
			)}
		/>
	);
}
