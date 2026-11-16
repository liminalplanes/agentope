import { ArrowRight } from "lucide-react";
import { SiteLink } from "#/components/docs/doc-link";
import { Verdict } from "#/components/verdict";
import { cn } from "#/lib/utils";

export function Section({
	id,
	title,
	lede,
	children,
	className = "",
}: {
	id?: string;
	title: string;
	lede?: React.ReactNode;
	children: React.ReactNode;
	className?: string;
}) {
	return (
		<section id={id} className="mx-auto max-w-7xl px-5 pt-28 md:pt-36">
			<h2 className="max-w-[20em] text-[clamp(1.6rem,2.8vw,2.2rem)] leading-[1.15] font-semibold tracking-[-0.03em]">
				{title}
			</h2>
			{lede && (
				<p className="mt-4 max-w-[40em] text-muted-foreground">{lede}</p>
			)}
			<div className={cn("mt-12", className)}>{children}</div>
		</section>
	);
}

/* ── Evidence levels ─────────────────────────────────────────────────── */

const levels = [
	{
		id: "L1",
		name: "Logged",
		source:
			"Recorded at decision time, because a little traffic was randomized",
		need: "explore or randomize in your agent",
		assumes: "The recorded probabilities are the ones used",
		trust: 4,
		status: "available",
	},
	{
		id: "L2",
		name: "Sampled",
		source:
			"Re-running the logging model on each stored input and counting its choices",
		need: "Content capture on, and the same model still runnable",
		assumes: "Stored inputs are complete; the model is unchanged",
		trust: 3,
		status: "available",
	},
	{
		id: "L3",
		name: "Estimated",
		source: "A model of the logging policy, fit from the logged context",
		need: "Span attributes that describe the situation",
		assumes:
			"Nothing that drove the choice is missing from context. Runs only once you accept this",
		trust: 2,
		status: "available",
	},
	{
		id: "L4",
		name: "Modeled",
		source: "No probabilities; an outcome model only",
		need: "An outcome model, e.g. a calibrated judge",
		assumes: "The model is right for actions that were rarely taken",
		trust: 1,
		status: "v0.4",
	},
];

function Trust({ value }: { value: number }) {
	return (
		<span
			className="inline-flex gap-1"
			role="img"
			aria-label={`trust ${value} of 4`}
		>
			{[1, 2, 3, 4].map((i) => (
				<i
					key={i}
					className={cn(
						"size-1.5 rounded-full",
						i <= value ? "bg-foreground" : "bg-border",
					)}
				/>
			))}
		</span>
	);
}

const th =
	"py-3 pr-6 text-left text-xs font-normal text-muted-foreground align-bottom";
const td = "py-5 pr-6 align-top";

export function EvidenceLevels() {
	return (
		<div className="overflow-x-auto">
			<table className="w-full min-w-[820px] border-collapse text-[0.95rem]">
				<thead>
					<tr className="border-b">
						<th className={th}>Level</th>
						<th className={th}>Probabilities come from</th>
						<th className={th}>You need</th>
						<th className={th}>Main assumption</th>
						<th className={th}>Trust</th>
						<th className={cn(th, "pr-0 text-right")}>Status</th>
					</tr>
				</thead>
				<tbody>
					{levels.map((l) => (
						<tr key={l.id} className="border-b">
							<td className={cn(td, "whitespace-nowrap")}>
								<span className="mr-3 font-mono text-xs text-muted-foreground">
									{l.id}
								</span>
								<span className="font-medium">{l.name}</span>
							</td>
							<td className={td}>{l.source}</td>
							<td className={cn(td, "text-muted-foreground")}>{l.need}</td>
							<td className={cn(td, "text-muted-foreground")}>{l.assumes}</td>
							<td className={cn(td, "pt-[1.6rem]")}>
								<Trust value={l.trust} />
							</td>
							<td
								className={cn(
									td,
									"pr-0 text-right font-mono text-xs text-muted-foreground",
								)}
							>
								{l.status}
							</td>
						</tr>
					))}
				</tbody>
			</table>
		</div>
	);
}

/* ── The four commands ───────────────────────────────────────────────── */

const steps = [
	{
		cmd: "check",
		title: "See what's possible",
		text: "Which levels your traces support, what's missing, and what sampling would cost. No LLM calls.",
		code: "agentope check --traces traces.otlp.json.gz",
		href: "/docs/reports",
	},
	{
		cmd: "import",
		title: "Turn traces into decisions",
		text: "Reads OpenTelemetry GenAI or OpenInference exports. Prompts and message text are optional.",
		code: "agentope import --traces traces.otlp.json.gz --context intent=app.intent -o decisions.jsonl",
		href: "/docs/traces",
	},
	{
		cmd: "sample",
		title: "Ask the model again",
		text: "Optional. For Level 2, and for testing a new prompt or model. Resumes where it stopped.",
		code: "agentope sample decisions.jsonl --n 64 --target v2.yaml -o samples.jsonl",
		href: "/docs/sampling",
	},
	{
		cmd: "eval",
		title: "Get the estimate",
		text: "The difference from your current agent, a 95% interval, diagnostics, a verdict and its assumptions.",
		code: "agentope eval decisions.jsonl --outcomes helpdesk.csv --horizon 3d --target v2.yaml",
		href: "/docs/reports",
	},
];

export function Pipeline() {
	return (
		<ol className="m-0 grid list-none grid-cols-1 gap-x-10 gap-y-12 p-0 sm:grid-cols-2 lg:grid-cols-4">
			{steps.map((s, i) => (
				<li key={s.cmd} className="flex min-w-0 flex-col gap-3 border-t pt-5">
					<span className="font-mono text-xs text-muted-foreground">
						{i + 1} · {s.cmd}
					</span>
					<h3 className="m-0 font-medium">{s.title}</h3>
					<p className="m-0 text-sm text-muted-foreground">{s.text}</p>
					<code className="font-mono text-xs leading-relaxed text-muted-foreground [overflow-wrap:anywhere]">
						$ {s.code}
					</code>
					<SiteLink
						href={s.href}
						className="mt-auto inline-flex items-center gap-1 text-sm hover:underline hover:underline-offset-4"
					>
						Read more <ArrowRight className="size-3.5" />
					</SiteLink>
				</li>
			))}
		</ol>
	);
}

/* ── Trusted vs. refused ─────────────────────────────────────────────── */

function Outcome({
	name,
	kind,
	lines,
	note,
}: {
	name: string;
	kind: "ok" | "unreliable";
	lines: [string, string][];
	note: string;
}) {
	return (
		<div className="min-w-0 rounded-xl border p-6">
			<div className="flex items-center justify-between gap-3">
				<span className="min-w-0 truncate font-mono text-sm">{name}</span>
				<Verdict kind={kind} />
			</div>
			<dl className="mt-5 mb-0 grid gap-2 font-mono text-[0.8rem]">
				{lines.map(([label, value]) => (
					<div
						key={label}
						className="grid grid-cols-[8.5rem_minmax(0,1fr)] gap-3"
					>
						<dt className="text-muted-foreground">{label}</dt>
						<dd className="m-0">{value}</dd>
					</div>
				))}
			</dl>
			<p className="mt-5 mb-0 border-t pt-4 text-sm text-muted-foreground">
				{note}
			</p>
		</div>
	);
}

export function Compare() {
	return (
		<div className="grid grid-cols-1 gap-4 md:grid-cols-2">
			<Outcome
				name="lookup_when_order_number"
				kind="ok"
				lines={[
					["Target policy", "0.671 SNIPS (IPS 0.664)"],
					["Difference", "+0.088 · 95% CI [+0.041, +0.134]"],
					["Diagnostics", "ESS 337 (33% of n) · max weight 3"],
					["Support", "no violations"],
				]}
				note="Looking up the order whenever the customer gives an order number would have resolved more tickets."
			/>
			<Outcome
				name="escalate_pro"
				kind="unreliable"
				lines={[
					["Target policy", "no trustworthy estimate"],
					["Raw estimate", "SNIPS 0.702 · IPS 0.529 (diagnosis only)"],
					["Diagnostics", "ESS 251 (25% of n) · max weight 3"],
					["Support", "24.6% of target mass violated (limit 1%)"],
				]}
				note="Escalation was never explored. To evaluate it, add escalation to the safe candidates for pro customers, or accept Level 3's assumption."
			/>
		</div>
	);
}

/* ── Integrations ────────────────────────────────────────────────────── */

const integrations = [
	"OpenTelemetry GenAI (gen_ai.*)",
	"OpenInference",
	"Collector file exporter",
	"vLLM",
	"Ollama",
	"llama.cpp",
	"any OpenAI-compatible API",
	"Python callables",
	"CSV or JSONL outcomes",
];

export function Integrations() {
	return (
		<ul className="m-0 grid list-none gap-2 p-0 text-sm">
			{integrations.map((name) => (
				<li key={name} className="border-b pb-2 text-muted-foreground">
					{name}
				</li>
			))}
		</ul>
	);
}
