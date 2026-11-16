import { ArrowDown, ArrowUpRight, Check, Minus, Plug } from "lucide-react";
import { siOllama, siOpentelemetry, siVllm } from "simple-icons";
import { SiteLink } from "#/components/docs/doc-link";
import { CodeBlock } from "#/components/docs/mdx-components";
import { IntervalChart } from "#/components/example/interval";
import { MonoPill, Verdict, type VerdictKind } from "#/components/verdict";
import ExploreShort from "#/content/example/explore-short.mdx";
import {
	count,
	example,
	type SavedReport,
	sampled,
	signed,
} from "#/lib/example";
import { site } from "#/lib/site";
import { cn } from "#/lib/utils";

/* ── Hero: what goes in, what comes out ──────────────────────────────── */

const inputs = [
	{
		file: "traces.otlp.json.gz",
		what: `What the agent did, in ${count(sampled.meta.conversations)} conversations`,
	},
	{ file: "helpdesk.csv", what: "Which tickets were resolved" },
	{ file: "policies.py", what: "The change: look up the order first" },
];

export function HeroInOut() {
	const r = sampled.report as SavedReport;
	const [lo, hi] = r.estimates.ci95 as [number, number];
	return (
		<figure className="m-0 flex min-w-0 flex-col gap-2">
			<div className="overflow-hidden rounded-md border bg-card">
				<div className="border-b bg-muted/60 px-4 py-2 font-mono text-[0.7rem] text-muted-foreground">
					what you give it
				</div>
				<ul className="m-0 list-none divide-y p-0">
					{inputs.map((input) => (
						<li
							key={input.file}
							className="grid grid-cols-1 gap-x-4 gap-y-0.5 px-4 py-2.5 text-sm sm:grid-cols-[11rem_minmax(0,1fr)]"
						>
							<span className="font-mono text-xs leading-5">{input.file}</span>
							<span className="text-muted-foreground">{input.what}</span>
						</li>
					))}
				</ul>
			</div>
			<ArrowDown
				aria-hidden="true"
				className="mx-auto size-4 text-muted-foreground"
			/>
			<div className="overflow-hidden rounded-md border bg-card">
				<div className="border-b bg-muted/60 px-4 py-2 font-mono text-[0.7rem] text-muted-foreground">
					what you get back
				</div>
				<div className="grid gap-3 p-4">
					<div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
						<span className="font-mono text-3xl font-semibold tracking-tight tabular-nums">
							{signed(r.estimates.difference as number)}
						</span>
						<span className="text-sm text-muted-foreground">
							resolution rate if the change had been live, 95% range{" "}
							{signed(lo)} to {signed(hi)}
						</span>
					</div>
					<div className="flex flex-wrap items-center gap-2 text-sm">
						<MonoPill>
							L{r.level.level} {r.level.name}
						</MonoPill>
						<span className="text-muted-foreground">evidence level</span>
						<Verdict kind={r.verdict as VerdictKind} className="ml-2" />
						<span className="text-muted-foreground">verdict</span>
					</div>
					<p className="m-0 text-sm text-muted-foreground">
						Plus what the estimate assumes, and what to record next for stronger
						evidence.
					</p>
				</div>
			</div>
		</figure>
	);
}

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

type Integration = {
	name: string;
	detail: string;
	href: string;
	logo: Logo | null;
	tested: boolean;
};

const otel: Logo = { kind: "icon", path: siOpentelemetry.path };
const arize: Logo = { kind: "image", src: "/logos/arize.jpg" };

const traceTools: Integration[] = [
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

const modelTools: Integration[] = [
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

function IntegrationLogo({ logo }: { logo: Logo | null }) {
	if (logo === null) {
		return <Plug aria-hidden="true" className="size-5 text-muted-foreground" />;
	}
	if (logo.kind === "icon") {
		return (
			<svg
				viewBox="0 0 24 24"
				aria-hidden="true"
				className="size-5 fill-foreground"
			>
				<path d={logo.path} />
			</svg>
		);
	}
	return (
		<img
			src={logo.src}
			alt=""
			width={24}
			height={24}
			className="size-6 rounded-[4px] grayscale transition-[filter] group-hover:grayscale-0"
		/>
	);
}

function IntegrationList({
	title,
	items,
}: {
	title: string;
	items: Integration[];
}) {
	return (
		<div>
			<h3 className="m-0 font-medium">{title}</h3>
			<ul className="m-0 mt-4 list-none divide-y border-y p-0">
				{items.map((item) => {
					const external = item.href.startsWith("http");
					const body = (
						<>
							<span className="flex size-8 shrink-0 items-center justify-center rounded-[4px] border bg-card">
								<IntegrationLogo logo={item.logo} />
							</span>
							<span className="min-w-0 flex-1">
								<span className="flex items-center gap-1.5">
									{item.name}
									{external && (
										<ArrowUpRight className="size-3.5 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
									)}
								</span>
								<span className="block text-sm text-muted-foreground">
									{item.detail}
								</span>
							</span>
							<span
								className={cn(
									"shrink-0 font-mono text-[0.7rem]",
									item.tested ? "text-ok" : "text-muted-foreground",
								)}
							>
								{item.tested ? "tested" : "should work"}
							</span>
						</>
					);
					const className =
						"group flex items-center gap-4 py-3 transition-colors hover:bg-muted/40";
					return (
						<li key={item.name}>
							{external ? (
								<a
									href={item.href}
									target="_blank"
									rel="noreferrer"
									className={className}
								>
									{body}
								</a>
							) : (
								<SiteLink href={item.href} className={className}>
									{body}
								</SiteLink>
							)}
						</li>
					);
				})}
			</ul>
		</div>
	);
}

export function Integrations() {
	return (
		<div>
			<div className="grid grid-cols-1 gap-12 lg:grid-cols-2 lg:gap-16">
				<IntegrationList title="Your traces" items={traceTools} />
				<IntegrationList title="Your model (for Level 2)" items={modelTools} />
			</div>
			<p className="mt-5 mb-0 max-w-[48em] text-sm text-muted-foreground">
				“Tested” means covered by agentope's own tests. The others speak the
				same formats and should work; if you try one,{" "}
				<a
					href={`${site.github}/issues`}
					className="text-foreground underline underline-offset-4"
				>
					an issue saying how it went
				</a>{" "}
				helps. Outcomes come in as CSV or JSONL, and changes as Python
				functions, target.jsonl or a target.yaml.
			</p>
		</div>
	);
}
