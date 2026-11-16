import { ArrowRight } from "lucide-react";
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

const changes = [
	"Which tool the agent calls first",
	"Which model a request goes to",
	"When to hand over to a person",
	"A new prompt or model at that step",
];

export function EvaluableCompact() {
	return (
		<div>
			<ul className="m-0 grid list-none grid-cols-1 gap-x-8 gap-y-0 border-t p-0 sm:grid-cols-2 lg:grid-cols-4">
				{changes.map((c) => (
					<li key={c} className="border-b py-4 lg:border-b-0">
						{c}
					</li>
				))}
			</ul>
			<p className="mt-5 mb-0 text-sm text-muted-foreground">
				Not a fit: a whole new agent, several changes at once, or the quality of
				free-text answers.
			</p>
		</div>
	);
}

/* ── Evidence levels ─────────────────────────────────────────────────── */

const levels = [
	{
		n: 1,
		name: "Logged",
		strength: 3,
		need: "A little exploration, recorded on the trace",
	},
	{
		n: 2,
		name: "Sampled",
		strength: 2,
		need: "Traces that include the messages",
	},
	{
		n: 3,
		name: "Estimated",
		strength: 1,
		need: "Only what the traces recorded; runs once you agree to its assumption",
	},
];

function Dots({ value }: { value: number }) {
	return (
		<span className="inline-flex gap-1" role="img" aria-label={`${value} of 3`}>
			{[1, 2, 3].map((i) => (
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

export function LevelsCompact() {
	return (
		<div>
			<ol className="m-0 grid list-none grid-cols-1 gap-x-8 border-t p-0 md:grid-cols-3">
				{levels.map((l) => (
					<li key={l.n} className="border-b py-4 md:border-b-0">
						<p className="m-0 flex items-center gap-2.5">
							<Dots value={l.strength} />
							<span className="font-medium">
								Level {l.n} · {l.name}
							</span>
						</p>
						<p className="mt-1.5 mb-0 text-sm text-muted-foreground">
							{l.need}
						</p>
					</li>
				))}
			</ol>
			<p className="mt-5 mb-0 flex flex-wrap items-center gap-x-2 gap-y-2 text-sm text-muted-foreground">
				Every answer ends with a verdict:
				<Verdict kind="ok" />
				<Verdict kind="weak" />
				<Verdict kind="unreliable" />
				<SiteLink
					href="/docs/evidence-levels"
					className="ml-2 inline-flex items-center gap-1 text-foreground underline-offset-4 hover:underline"
				>
					Evidence levels in detail <ArrowRight className="size-3.5" />
				</SiteLink>
			</p>
		</div>
	);
}

/* ── Works with ──────────────────────────────────────────────────────── */

function LogoLink({ item }: { item: Integration }) {
	const body = (
		<>
			<IntegrationLogo logo={item.logo} />
			<span>{item.name}</span>
		</>
	);
	const className =
		"group inline-flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground";
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

export function LogosRow() {
	const items = [...traceTools, ...modelTools].filter(
		(item) => item.name !== "OpenTelemetry Collector",
	);
	return (
		<div>
			<ul className="m-0 flex list-none flex-wrap gap-x-8 gap-y-5 p-0">
				{items.map((item) => (
					<li key={item.name}>
						<LogoLink item={item} />
					</li>
				))}
			</ul>
			<p className="mt-6 mb-0 text-sm text-muted-foreground">
				Tested with OpenTelemetry GenAI, Collector exports, OpenInference and
				the OpenAI chat API. The others use the same formats.
			</p>
		</div>
	);
}
