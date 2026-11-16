import { Verdict } from "#/components/verdict";
import { cn } from "#/lib/utils";

const rows = [
	{
		name: "LLM-as-judge",
		outcomes: "No, it scores the text",
		time: "Minutes",
		risk: "None",
		honest: "No",
	},
	{
		name: "A/B test",
		outcomes: "Yes",
		time: "Weeks of live traffic",
		risk: "Some users get the worse version",
		honest: "Not applicable",
	},
	{
		name: "agentope",
		outcomes: "Yes, the ones you already record",
		time: "Minutes, from your logs",
		risk: "None",
		honest: "Yes, it refuses to guess",
		ours: true,
	},
];

const th = "px-4 py-3 text-left text-xs font-normal text-muted-foreground";
const td = "px-4 py-3.5 align-top";

/** agentope next to the two usual ways of judging an agent change. */
export function Alternatives() {
	return (
		<div>
			<div className="overflow-x-auto rounded-md border bg-card">
				<table className="w-full min-w-[44rem] border-collapse text-[0.95rem]">
					<thead>
						<tr className="border-b">
							<th className={th} />
							<th className={th}>Measures real outcomes</th>
							<th className={th}>Time to an answer</th>
							<th className={th}>Risk to users</th>
							<th className={th}>Says when it can't answer</th>
						</tr>
					</thead>
					<tbody>
						{rows.map((row) => (
							<tr
								key={row.name}
								className={cn(
									"border-b last:border-b-0",
									row.ours ? "bg-muted/50" : "text-muted-foreground",
								)}
							>
								<td
									className={cn(
										td,
										"font-medium",
										row.ours ? "text-foreground" : "",
									)}
								>
									{row.name}
								</td>
								<td className={td}>{row.outcomes}</td>
								<td className={td}>{row.time}</td>
								<td className={td}>{row.risk}</td>
								<td className={td}>{row.honest}</td>
							</tr>
						))}
					</tbody>
				</table>
			</div>
			<p className="mt-3 mb-0 max-w-[48em] text-sm text-muted-foreground">
				agentope works from conversations that already happened, so nothing
				changes for your users while you find out.
			</p>
		</div>
	);
}

const levels = [
	{
		strength: 3,
		label: "Strongest",
		name: "Level 1 · Logged",
		need: "A small share of conversations try a random option you consider safe, recorded on the trace.",
		how: "agentope knows exactly how likely each choice was.",
		assumes: "Only that the recording is right.",
	},
	{
		strength: 2,
		label: "Strong",
		name: "Level 2 · Sampled",
		need: "Traces that include the messages, and the same model still available.",
		how: "agentope asks the model again on each conversation and counts its choices.",
		assumes:
			"The messages are complete and the model hasn't changed since. agentope checks both.",
	},
	{
		strength: 1,
		label: "Weakest",
		name: "Level 3 · Estimated",
		need: "Traces that record something about each situation, such as what the customer asked about.",
		how: "agentope models how the agent chose from what was logged.",
		assumes:
			"Nothing important is missing from what you logged. That can't be checked, so it only runs once you agree, and never rates the result better than weak.",
	},
];

function Strength({ value }: { value: number }) {
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

/** The three evidence levels, by what you have. */
export function EvidenceLevels() {
	return (
		<div>
			<ol className="m-0 grid list-none grid-cols-1 gap-x-10 gap-y-10 p-0 md:grid-cols-3">
				{levels.map((level) => (
					<li key={level.name} className="flex flex-col gap-3 border-t pt-5">
						<span className="flex items-center gap-2.5 font-mono text-xs text-muted-foreground">
							<Strength value={level.strength} />
							{level.label}
						</span>
						<h3 className="m-0 font-medium">{level.name}</h3>
						<dl className="m-0 grid gap-3 text-sm">
							<div>
								<dt className="text-xs text-muted-foreground">You need</dt>
								<dd className="m-0 mt-0.5">{level.need}</dd>
							</div>
							<div>
								<dt className="text-xs text-muted-foreground">How it works</dt>
								<dd className="m-0 mt-0.5 text-muted-foreground">
									{level.how}
								</dd>
							</div>
							<div>
								<dt className="text-xs text-muted-foreground">It assumes</dt>
								<dd className="m-0 mt-0.5 text-muted-foreground">
									{level.assumes}
								</dd>
							</div>
						</dl>
					</li>
				))}
			</ol>
			<p className="mt-6 mb-0 text-sm text-muted-foreground">
				A fourth level, from an outcome model alone, is planned.
			</p>
		</div>
	);
}

const verdicts = [
	{
		kind: "ok" as const,
		text: "Enough comparable conversations, and no warning signs.",
	},
	{
		kind: "weak" as const,
		text: "Usable with care: Level 3, few comparable conversations, or many missing outcomes.",
	},
	{
		kind: "unreliable" as const,
		text: "No trustworthy answer. agentope says why, and what to record to get one.",
	},
];

/** What each verdict means. */
export function Verdicts() {
	return (
		<div className="mt-14">
			<h3 className="m-0 font-medium">Every answer ends with a verdict</h3>
			<ul className="m-0 mt-4 grid list-none gap-0 divide-y border-y p-0">
				{verdicts.map((v) => (
					<li
						key={v.kind}
						className="grid grid-cols-[7rem_minmax(0,1fr)] items-baseline gap-4 py-3.5 text-sm"
					>
						<span>
							<Verdict kind={v.kind} />
						</span>
						<span className="text-muted-foreground">{v.text}</span>
					</li>
				))}
			</ul>
		</div>
	);
}
