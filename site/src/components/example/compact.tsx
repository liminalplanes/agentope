import {
	ArrowRight,
	Calculator,
	Dices,
	type LucideIcon,
	MessageSquareText,
	RefreshCw,
	Split,
	UserRound,
	Wrench,
} from "lucide-react";
import { SiteLink } from "#/components/docs/doc-link";
import {
	type Integration,
	IntegrationLogo,
	modelTools,
	traceTools,
} from "#/components/example/landing";
import { Verdict } from "#/components/verdict";
import { cn } from "#/lib/utils";

/* ── What you can evaluate ───────────────────────────────────────────── */

type Change = {
	icon: LucideIcon;
	title: string;
	file: string;
	before: string;
	after: string;
	when: string;
};

/** Each kind of change, as the diff a developer would write for it. */
const changes: Change[] = [
	{
		icon: Wrench,
		title: "Which tool the agent calls first",
		file: "first_move",
		before: "search_kb",
		after: "lookup_order",
		when: "when there's an order number",
	},
	{
		icon: Split,
		title: "Which model a request goes to",
		file: "router",
		before: "large-model",
		after: "small-model",
		when: "for short questions",
	},
	{
		icon: UserRound,
		title: "When to hand over to a person",
		file: "handover",
		before: "answer_directly",
		after: "escalate_to_human",
		when: "for pro customers",
	},
	{
		icon: MessageSquareText,
		title: "A new prompt or model at that step",
		file: "system_prompt",
		before: "prompts/v1.txt",
		after: "prompts/v2.txt",
		when: "same model, new instructions",
	},
];

const misfits = [
	"A whole new agent",
	"Several changes at once",
	"Free-text answer quality",
];

function DiffCard({ change }: { change: Change }) {
	const Icon = change.icon;
	return (
		<li className="group flex min-w-0 flex-col overflow-hidden rounded-md border bg-card transition-colors hover:border-foreground/25">
			<div className="flex items-start gap-3 p-4 pb-3">
				<Icon className="mt-0.5 size-4 shrink-0 text-muted-foreground transition-colors group-hover:text-foreground" />
				<p className="m-0 text-[0.95rem] leading-snug font-medium">
					{change.title}
				</p>
			</div>
			<div className="mt-auto border-t bg-muted/40 font-mono text-[0.72rem] leading-relaxed">
				<p className="m-0 border-b px-3 py-1 text-muted-foreground">
					{change.file}
				</p>
				<p className="m-0 flex gap-2 bg-bad-bg/70 px-3 py-0.5 text-bad">
					<span className="select-none">-</span>
					<span className="truncate">{change.before}</span>
				</p>
				<p className="m-0 flex gap-2 bg-ok-bg/80 px-3 py-0.5 text-ok">
					<span className="select-none">+</span>
					<span className="truncate">{change.after}</span>
				</p>
				<p className="m-0 px-3 pt-1 pb-2 text-muted-foreground">
					<span className="select-none"># </span>
					{change.when}
				</p>
			</div>
		</li>
	);
}

export function EvaluableCompact() {
	return (
		<div>
			<ul className="m-0 grid list-none grid-cols-1 gap-3 p-0 sm:grid-cols-2 lg:grid-cols-4">
				{changes.map((c) => (
					<DiffCard key={c.title} change={c} />
				))}
			</ul>
			<p className="mt-5 mb-0 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
				<span>
					Not a fit… <em>yet</em>:
				</span>
				{misfits.map((m) => (
					<span
						key={m}
						className="rounded-full border border-dashed px-2.5 py-0.5 text-xs text-muted-foreground"
					>
						{m}
					</span>
				))}
			</p>
		</div>
	);
}

/* ── Evidence levels ─────────────────────────────────────────────────── */

type Rung = {
	n: number;
	name: string;
	label: string;
	height: string;
	icon: LucideIcon;
	have: string;
	assumes: string;
};

/** Weakest to strongest, left to right: a staircase you climb by recording more. */
const rungs: Rung[] = [
	{
		n: 3,
		name: "Estimated",
		label: "Weakest",
		height: "h-14",
		icon: Calculator,
		have: "Only what your traces recorded",
		assumes: "Nothing important is missing. Can't be checked, so you opt in.",
	},
	{
		n: 2,
		name: "Sampled",
		label: "Strong",
		height: "h-24",
		icon: RefreshCw,
		have: "Traces that include the messages",
		assumes: "The model behaves as it did then. agentope checks.",
	},
	{
		n: 1,
		name: "Logged",
		label: "Strongest",
		height: "h-34",
		icon: Dices,
		have: "A little exploration, recorded on the trace",
		assumes: "Only that the coin flips were recorded.",
	},
];

const verdicts = [
	{ kind: "ok" as const, text: "trust it" },
	{ kind: "weak" as const, text: "use with care" },
	{
		kind: "unreliable" as const,
		text: "no answer, and what to record to get one",
	},
];

export function LevelsCompact() {
	return (
		<div>
			<ol className="m-0 grid list-none grid-cols-1 items-end gap-x-4 gap-y-8 p-0 md:grid-cols-3">
				{rungs.map((r, i) => {
					const Icon = r.icon;
					return (
						<li key={r.n} className="flex min-w-0 flex-col">
							<div className="mb-3 flex items-center justify-between gap-3">
								<p className="m-0 flex items-baseline gap-2">
									<span className="font-mono text-xs text-muted-foreground">
										L{r.n}
									</span>
									<span className="font-medium">{r.name}</span>
								</p>
								<span className="font-mono text-[0.7rem] text-muted-foreground">
									{r.label}
								</span>
							</div>
							<div
								className={cn(
									"relative flex items-end rounded-t-md border border-b-0 p-3",
									r.height,
								)}
								style={{
									background: `linear-gradient(135deg, color-mix(in srgb, var(--logo-from) ${18 + i * 14}%, transparent), color-mix(in srgb, var(--logo-to) ${18 + i * 14}%, transparent))`,
								}}
							>
								<Icon className="size-5 text-foreground/70" />
							</div>
							<div className="flex flex-1 flex-col gap-2 rounded-b-md border bg-card p-4">
								<p className="m-0 text-sm">{r.have}</p>
								<p className="m-0 text-xs text-muted-foreground">
									Assumes: {r.assumes}
								</p>
							</div>
						</li>
					);
				})}
			</ol>
			<div className="mt-6 flex flex-wrap items-center justify-between gap-4">
				<ul className="m-0 flex list-none flex-wrap items-center gap-x-5 gap-y-2 p-0 text-sm text-muted-foreground">
					{verdicts.map((v) => (
						<li key={v.kind} className="flex items-center gap-2">
							<Verdict kind={v.kind} />
							{v.text}
						</li>
					))}
				</ul>
				<SiteLink
					href="/docs/evidence-levels"
					className="inline-flex items-center gap-1 text-sm underline-offset-4 hover:underline"
				>
					Evidence levels in detail <ArrowRight className="size-3.5" />
				</SiteLink>
			</div>
		</div>
	);
}

/* ── Works with ──────────────────────────────────────────────────────── */

function CloudItem({ item }: { item: Integration }) {
	const body = (
		<>
			<IntegrationLogo logo={item.logo} large />
			<span className="text-[1.05rem] font-medium tracking-tight">
				{item.name}
			</span>
		</>
	);
	const className =
		"group inline-flex items-center gap-3 text-muted-foreground/80 transition-colors hover:text-foreground";
	return item.href.startsWith("http") ? (
		<a href={item.href} target="_blank" rel="noreferrer" className={className}>
			{body}
		</a>
	) : (
		<SiteLink href={item.href} className={className}>
			{body}
		</SiteLink>
	);
}

function Cloud({ label, items }: { label: string; items: Integration[] }) {
	return (
		<div className="flex flex-col items-center gap-5">
			<p className="m-0 font-mono text-xs text-muted-foreground">{label}</p>
			<ul className="m-0 flex list-none flex-wrap items-center justify-center gap-x-12 gap-y-6 p-0">
				{items.map((item) => (
					<li key={item.name}>
						<CloudItem item={item} />
					</li>
				))}
			</ul>
		</div>
	);
}

/** A centered logo cloud: where traces come from, and which model servers it talks to. */
export function LogoCloud() {
	const traces = traceTools
		.filter((item) => item.name !== "OpenTelemetry Collector")
		.map((item) =>
			item.name === "OpenTelemetry GenAI"
				? { ...item, name: "OpenTelemetry" }
				: item,
		);
	const models = modelTools
		.filter((item) => item.name === "Any OpenAI-compatible API")
		.map((item) => ({ ...item, name: "OpenAI-compatible APIs" }));
	return (
		<div className="flex flex-col items-center gap-12">
			<Cloud label="reads traces from" items={traces} />
			<Cloud label="asks models through" items={models} />
		</div>
	);
}
