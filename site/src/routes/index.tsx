import { createFileRoute } from "@tanstack/react-router";
import { ArrowRight } from "lucide-react";
import { CopyButton } from "#/components/copy-button";
import { SiteLink } from "#/components/docs/doc-link";
import { CodeBlock } from "#/components/docs/mdx-components";
import { DecisionPicture } from "#/components/example/decision-picture";
import { Alternatives, Ingredients } from "#/components/example/positioning";
import { ReportCard } from "#/components/example/report-card";
import { Terminal } from "#/components/example/terminal";
import { Button } from "#/components/ui/button";
import Rule from "#/content/example/rule.mdx";
import {
	count,
	excerpt,
	percent,
	points,
	sampled,
	signed,
} from "#/lib/example";
import { site } from "#/lib/site";

export const Route = createFileRoute("/")({
	head: () => ({
		meta: [{ title: `${site.name} · evaluate agent changes before go-live` }],
	}),
	component: Home,
});

function Section({
	id,
	title,
	lede,
	children,
}: {
	id?: string;
	title: string;
	lede?: React.ReactNode;
	children: React.ReactNode;
}) {
	return (
		<section
			id={id}
			className="mx-auto max-w-7xl scroll-mt-16 px-5 pt-28 md:pt-36"
		>
			<h2 className="max-w-[22em] text-[clamp(1.6rem,2.8vw,2.2rem)] leading-[1.15] font-semibold tracking-[-0.03em]">
				{title}
			</h2>
			{lede && (
				<p className="mt-4 mb-0 max-w-[42em] text-muted-foreground">{lede}</p>
			)}
			<div className="mt-12">{children}</div>
		</section>
	);
}

function Step({
	n,
	title,
	children,
	aside,
}: {
	n: number;
	title: string;
	children: React.ReactNode;
	aside: React.ReactNode;
}) {
	return (
		<li className="grid grid-cols-1 gap-6 border-t pt-8 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)] lg:gap-14">
			<div>
				<p className="m-0 font-mono text-xs text-muted-foreground">Step {n}</p>
				<h3 className="mt-2 text-lg font-semibold tracking-tight">{title}</h3>
				<div className="mt-2 flex flex-col gap-3 text-muted-foreground">
					{children}
				</div>
			</div>
			<div className="flex min-w-0 flex-col gap-3">{aside}</div>
		</li>
	);
}

function Home() {
	const { meta, steps, report, truth } = sampled;
	const difference = report.estimates.difference as number;
	const [lo, hi] = report.estimates.ci95 as [number, number];
	const sampling = report.diagnostics.sampling as {
		n_median: number;
		reproduction_rate: number;
	};

	return (
		<main>
			<section className="mx-auto grid max-w-7xl grid-cols-1 items-start gap-14 px-5 pt-16 md:pt-24 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] lg:gap-14">
				<div className="lg:pt-4">
					<h1 className="text-[clamp(2.4rem,5vw,3.8rem)] leading-[1.04] font-semibold tracking-[-0.045em]">
						Evaluate agent changes before go-live.
					</h1>
					<p className="mt-6 max-w-[32em] text-lg text-muted-foreground">
						Find out whether a change to how your agent decides would actually
						help your users,{" "}
						<span className="text-foreground">
							using the conversations you already have
						</span>
						. No A/B test, no LLM judge.
					</p>
					<div className="mt-9 flex flex-wrap gap-2.5">
						<Button asChild size="lg">
							<SiteLink href="/docs/quickstart">
								Get started <ArrowRight />
							</SiteLink>
						</Button>
						<Button asChild size="lg" variant="ghost">
							<a href="#example">See an example</a>
						</Button>
					</div>
					<div className="mt-10 max-w-[36rem] border-t pt-4">
						<div className="flex items-center gap-2 text-sm">
							<code className="min-w-0 flex-1 overflow-x-auto whitespace-nowrap font-mono [scrollbar-width:none]">
								<span className="select-none text-muted-foreground">$ </span>
								{site.install}
							</code>
							<CopyButton text={site.install} label="Copy install command" />
						</div>
						<p className="mt-1 mb-0 text-xs text-muted-foreground">
							Python 3.14+. The llm extra is only needed to sample a model.
						</p>
					</div>
				</div>
				<div>
					<p className="mt-0 mb-3 text-sm text-muted-foreground">
						<span className="font-medium text-foreground">How it works.</span>{" "}
						Your agent has already made thousands of choices, and you know how
						each one turned out. The ones where it happened to do what the new
						version would do, weighed by how likely that choice was, show how
						the new version would fare.
					</p>
					<DecisionPicture />
				</div>
			</section>

			<Section
				title="You changed how your agent decides. Did it help?"
				lede="Most teams have two ways to find out, and neither answers quickly, safely and on the outcomes that matter."
			>
				<Alternatives />
			</Section>

			<Section
				title="Three things you probably already have"
				lede="agentope looks at one decision at a time, such as which tool the agent calls first or which model a request goes to."
			>
				<Ingredients />
			</Section>

			<Section
				id="example"
				title="Here's that on a support agent"
				lede={
					<>
						At the start of each conversation, a support agent picks one of four
						moves: search the help articles, look up the order, hand over to a
						person, or answer directly. The team thinks a plain rule would
						resolve more tickets:{" "}
						<span className="text-foreground">
							look up the order whenever the customer gives an order number.
						</span>{" "}
						Nothing about the agent changes. Its traces include the messages, as
						most tracing tools record them. Every output below is real; the
						conversations and the model are simulated, so the right answer is
						known too.
					</>
				}
			>
				<ol className="m-0 flex list-none flex-col gap-14 p-0">
					<Step
						n={1}
						title="See what your traces support"
						aside={
							<Terminal
								command="agentope check --traces traces.otlp.json.gz --n 64"
								output={excerpt(steps.check.output, [
									"tool_choice ·",
									"Level 1",
									"Level 2",
									"est. cost",
									"Best available",
								])}
							/>
						}
					>
						<p className="m-0">
							{count(meta.conversations)} conversations from the last{" "}
							{meta.days} days. Because the traces include the messages,
							agentope can find out how the model chooses by asking it again.
						</p>
					</Step>

					<Step
						n={2}
						title="Bring in what happened"
						aside={
							<Terminal
								command="agentope import --traces traces.otlp.json.gz -o decisions.jsonl"
								output={excerpt(steps.import.output, [
									"traces.otlp.json.gz",
									"chosen",
									"stored inputs",
								])}
							/>
						}
					>
						<p className="m-0">
							agentope reads the traces as they were exported: what the agent
							did, and the messages it saw. The helpdesk's export says which
							tickets were resolved.
						</p>
					</Step>

					<Step
						n={3}
						title="Ask the model again"
						aside={
							<Terminal
								command={steps.sample.command}
								output={steps.sample.output}
							/>
						}
					>
						<p className="m-0">
							For each conversation, agentope sends the same messages to the
							same model {sampling.n_median} times and counts what it chooses.
							That tells it how likely each logged choice was. It's the only
							step that calls the model, and it asks before it starts.
						</p>
					</Step>

					<Step
						n={4}
						title="Describe the change"
						aside={
							<>
								<div className="min-w-0">
									<Rule components={{ pre: CodeBlock }} />
								</div>
								<Terminal
									command={
										"agentope eval decisions.jsonl --samples samples.jsonl \\\n    --outcomes helpdesk.csv --horizon 3d \\\n    --target policies.py:lookup_when_order_number"
									}
									output={excerpt(steps.eval.output, [
										"Evidence level",
										"Logging policy",
										"Target policy",
										"Difference",
										"logged choice reproduced",
										"Verdict",
									])}
								/>
							</>
						}
					>
						<p className="m-0">
							The rule is a small Python function: given the situation, which
							move to make. agentope evaluates it against the outcomes, counting
							tickets resolved within three days.
						</p>
					</Step>

					<Step
						n={5}
						title="Get an answer you can check"
						aside={
							<div className="max-w-xl">
								<ReportCard report={report} truth={truth.lookup_difference} />
							</div>
						}
					>
						<p className="m-0">
							The rule would have resolved{" "}
							<span className="text-foreground">
								{points(difference)} more tickets
							</span>
							, somewhere between {points(lo)} and {points(hi)} with 95%
							confidence. The range is clear of zero, so the verdict is{" "}
							<span className="text-foreground">ok</span>.
						</p>
						<p className="m-0">
							Because the world is simulated, the true effect is known:{" "}
							{signed(truth.lookup_difference)}, the green line. It falls inside
							the range.
						</p>
						<p className="m-0">
							The answer leans on the model behaving today as it did when the
							conversations happened. The report checks that: the logged choice
							came up again in {percent(sampling.reproduction_rate)} of
							conversations.
						</p>
					</Step>
				</ol>

				<div className="mt-14 grid grid-cols-1 gap-8 border-t pt-8 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)] lg:gap-14">
					<div>
						<h3 className="m-0 text-lg font-semibold tracking-tight">
							No messages in your traces?
						</h3>
						<p className="mt-2 mb-0 text-muted-foreground">
							Then agentope can't ask the model again. It can still estimate
							from what you logged about each conversation, but only once you
							accept that nothing important is missing from it, and it says so
							rather than guessing:
						</p>
					</div>
					<Terminal
						command="agentope eval decisions.jsonl --outcomes helpdesk.csv --horizon 3d --target …"
						output={steps.refused.output.split("\n").slice(0, 3).join("\n")}
					/>
				</div>

				<div className="mt-14 grid grid-cols-1 gap-8 border-t pt-8 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)] lg:gap-14">
					<div>
						<h3 className="m-0 text-lg font-semibold tracking-tight">
							Want stronger evidence?
						</h3>
						<p className="mt-2 mb-0 text-muted-foreground">
							Let a small share of conversations try a random option you
							consider safe, and agentope no longer has to rely on the model
							behaving the same. The full walkthrough shows that path on the
							same agent.
						</p>
					</div>
					<div className="flex flex-wrap items-start gap-2.5">
						<Button asChild>
							<SiteLink href="/docs/quickstart">
								Try it on your agent <ArrowRight />
							</SiteLink>
						</Button>
						<Button asChild variant="ghost">
							<SiteLink href="/docs/worked-example">
								Walkthrough with exploration
							</SiteLink>
						</Button>
					</div>
				</div>
			</Section>
		</main>
	);
}
