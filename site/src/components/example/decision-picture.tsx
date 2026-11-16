import { Check, X } from "lucide-react";
import { count, percent, sampled } from "#/lib/example";
import { cn } from "#/lib/utils";

export const ACTION: Record<string, string> = {
	search_kb: "search articles",
	lookup_order: "look up order",
	escalate_to_human: "hand to person",
	__none__: "answer directly",
};

const INTENT: Record<string, string> = {
	refund: "Refund",
	order_status: "Order status",
	product_question: "Product question",
	account: "Account",
};

/**
 * How the evaluation works, on real rows from the example: logged conversations, how
 * often the model makes the same choice when asked again, and the ones where the agent
 * happened to do what the new rule would.
 */
export function DecisionPicture() {
	const { rows, total, matched } = sampled.picture;
	const r = sampled.report.estimates;
	return (
		<figure className="m-0 min-w-0 overflow-hidden rounded-md border bg-card">
			<div className="border-b bg-muted/60 px-4 py-2.5 font-mono text-[0.7rem] text-muted-foreground">
				logged conversations, from the traces
			</div>
			<div className="overflow-x-auto">
				<table className="w-full min-w-[30rem] border-collapse text-sm">
					<thead>
						<tr className="border-b text-left text-xs text-muted-foreground">
							<th className="py-2 pr-2 pl-4 font-normal">Customer asked</th>
							<th className="px-2 py-2 font-normal">Agent did</th>
							<th className="px-2 py-2 font-normal">Rule would</th>
							<th className="px-2 py-2 text-right font-normal">Model</th>
							<th className="py-2 pr-4 pl-2 text-right font-normal">Solved</th>
						</tr>
					</thead>
					<tbody>
						{rows.map((row) => {
							const same = row.agent_did === row.rule_would;
							return (
								<tr
									key={row.conversation}
									className={cn(
										"border-b last:border-b-0",
										same ? "bg-muted/50" : "text-muted-foreground/60",
									)}
								>
									<td className="py-2 pr-2 pl-4 whitespace-nowrap">
										{INTENT[row.intent]}
										<span className="text-muted-foreground">
											{row.has_order_number ? ", order no." : ""}
										</span>
									</td>
									<td className="px-2 py-2 whitespace-nowrap">
										{ACTION[row.agent_did]}
									</td>
									<td className="px-2 py-2 whitespace-nowrap">
										{ACTION[row.rule_would]}
									</td>
									<td className="px-2 py-2 text-right font-mono text-xs whitespace-nowrap tabular-nums">
										{row.model_picks} of {row.n}
									</td>
									<td className="py-2 pr-4 pl-2 text-right">
										{row.resolved ? (
											<Check
												aria-label="resolved"
												className={cn("ml-auto size-4", same && "text-ok")}
											/>
										) : (
											<X
												aria-label="not resolved"
												className={cn("ml-auto size-4", same && "text-bad")}
											/>
										)}
									</td>
								</tr>
							);
						})}
					</tbody>
				</table>
			</div>
			<figcaption className="border-t px-4 py-3 text-sm text-muted-foreground">
				"Model" is how often the model makes the agent's choice when agentope
				asks it again. In {count(matched)} of {count(total)} conversations the
				agent happened to do what the new rule would (highlighted). Their
				outcomes, weighted up where the model rarely makes that choice, estimate
				the rule:{" "}
				<span className="text-foreground">
					{percent(r.snips as number, 1)} resolved, against{" "}
					{percent(r.logging_mean, 1)} today
				</span>
				.
			</figcaption>
		</figure>
	);
}
