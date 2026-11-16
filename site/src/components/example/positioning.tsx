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

const ingredients = [
	{
		title: "A record of what your agent did",
		text: "Traces from your tracing tool. If they include the messages, as most tools record them, agentope can ask the model again.",
	},
	{
		title: "A record of how it turned out",
		text: "Resolved tickets, purchases, ratings: whatever you already measure, linked by conversation.",
	},
	{
		title: "The change you want to test",
		text: "A rule written as a Python function, or a new prompt or model.",
	},
];

/** The three inputs agentope needs. */
export function Ingredients() {
	return (
		<ol className="m-0 grid list-none grid-cols-1 gap-x-10 gap-y-8 p-0 md:grid-cols-3">
			{ingredients.map((item, i) => (
				<li key={item.title} className="border-t pt-5">
					<p className="m-0 font-mono text-xs text-muted-foreground">{i + 1}</p>
					<h3 className="mt-2 font-medium">{item.title}</h3>
					<p className="mt-1.5 mb-0 text-sm text-muted-foreground">
						{item.text}
					</p>
				</li>
			))}
		</ol>
	);
}
