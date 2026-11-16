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

const card =
	"rounded-md border bg-card p-5 transition-colors hover:border-foreground/20";

function IconTile({ icon: Icon }: { icon: LucideIcon }) {
	return (
		<span className="flex size-9 items-center justify-center rounded-md border bg-muted/60">
			<Icon className="size-4.5 text-foreground/80" />
		</span>
	);
}

/* ── What you can evaluate ───────────────────────────────────────────── */

const changes: { icon: LucideIcon; title: string; example: string }[] = [
	{
		icon: Wrench,
		title: "Which tool the agent calls first",
		example: "lookup_order before search_kb",
	},
	{
		icon: Split,
		title: "Which model a request goes to",
		example: "short questions → small model",
	},
	{
		icon: UserRound,
		title: "When to hand over to a person",
		example: "escalate every pro customer",
	},
	{
		icon: MessageSquareText,
		title: "A new prompt or model at that step",
		example: "system prompt v1 → v2",
	},
];

const misfits = [
	"A whole new agent",
	"Several changes at once",
	"Free-text answer quality",
];

export function EvaluableCompact() {
	return (
		<div>
			<ul className="m-0 grid list-none grid-cols-1 gap-3 p-0 sm:grid-cols-2 lg:grid-cols-4">
				{changes.map((c) => (
					<li key={c.title} className={cn(card, "flex flex-col gap-4")}>
						<IconTile icon={c.icon} />
						<div>
							<p className="m-0 font-medium leading-snug">{c.title}</p>
							<p className="mt-2 mb-0 font-mono text-xs text-muted-foreground">
								{c.example}
							</p>
						</div>
					</li>
				))}
			</ul>
			<p className="mt-5 mb-0 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
				<span>
					Not a fit… <em>yet</em>:
				</span>
				{misfits.map((m) => (
					<span
						key={m}
						className="rounded-full border px-2.5 py-0.5 text-xs text-muted-foreground"
					>
						{m}
					</span>
				))}
			</p>
		</div>
	);
}

/* ── Evidence levels ─────────────────────────────────────────────────── */

const levels: {
	n: number;
	name: string;
	label: string;
	strength: number;
	icon: LucideIcon;
	need: string;
}[] = [
	{
		n: 1,
		name: "Logged",
		label: "Strongest",
		strength: 3,
		icon: Dices,
		need: "A little exploration, recorded on the trace",
	},
	{
		n: 2,
		name: "Sampled",
		label: "Strong",
		strength: 2,
		icon: RefreshCw,
		need: "Traces that include the messages",
	},
	{
		n: 3,
		name: "Estimated",
		label: "Weakest",
		strength: 1,
		icon: Calculator,
		need: "Only what the traces recorded, once you agree to its assumption",
	},
];

function Meter({ value }: { value: number }) {
	return (
		<span className="flex gap-1" role="img" aria-label={`${value} of 3`}>
			{[1, 2, 3].map((i) => (
				<i
					key={i}
					className={cn(
						"h-1.5 w-6 rounded-full",
						i <= value ? "bg-foreground/80" : "bg-border",
					)}
				/>
			))}
		</span>
	);
}

export function LevelsCompact() {
	return (
		<div>
			<ol className="m-0 grid list-none grid-cols-1 gap-3 p-0 md:grid-cols-3">
				{levels.map((l) => (
					<li key={l.n} className={cn(card, "flex flex-col gap-4")}>
						<div className="flex items-center justify-between gap-3">
							<IconTile icon={l.icon} />
							<span className="flex flex-col items-end gap-1.5">
								<Meter value={l.strength} />
								<span className="font-mono text-[0.7rem] text-muted-foreground">
									{l.label}
								</span>
							</span>
						</div>
						<div>
							<p className="m-0 font-medium">
								<span className="mr-1.5 font-mono text-xs text-muted-foreground">
									L{l.n}
								</span>
								{l.name}
							</p>
							<p className="mt-1.5 mb-0 text-sm text-muted-foreground">
								{l.need}
							</p>
						</div>
					</li>
				))}
			</ol>
			<div className="mt-5 flex flex-wrap items-center justify-between gap-4">
				<p className="m-0 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
					Every answer ends with a verdict:
					<Verdict kind="ok" />
					<Verdict kind="weak" />
					<Verdict kind="unreliable" />
				</p>
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
