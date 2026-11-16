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
