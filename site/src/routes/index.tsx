import { createFileRoute } from "@tanstack/react-router";
import { ArrowRight } from "lucide-react";
import { CopyButton } from "#/components/copy-button";
import { SiteLink } from "#/components/docs/doc-link";
import { CodeTabs } from "#/components/home/code-tabs";
import { ExampleReport } from "#/components/home/example-report";
import { Faq } from "#/components/home/faq";
import {
	Compare,
	EvidenceLevels,
	Integrations,
	Pipeline,
	Section,
} from "#/components/home/sections";
import { Button } from "#/components/ui/button";
import { site } from "#/lib/site";

export const Route = createFileRoute("/")({
	head: () => ({
		meta: [
			{ title: `${site.name} · offline evaluation of LLM agent decisions` },
		],
	}),
	component: Home,
});

function Home() {
	return (
		<main>
			<section className="mx-auto grid max-w-7xl grid-cols-1 items-start gap-14 px-5 pt-16 md:pt-24 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)] lg:gap-20">
				<div className="lg:pt-6">
					<h1 className="text-[clamp(2.4rem,5vw,3.8rem)] leading-[1.04] font-semibold tracking-[-0.045em]">
						Evaluate agent changes before go-live.
					</h1>
					<p className="mt-6 max-w-[34em] text-lg text-muted-foreground">
						agentope estimates how a different prompt, model or tool policy
						would have done,{" "}
						<span className="text-foreground">
							from the agent logs you already keep
						</span>
						. It needs no logprobs, and every number comes with the evidence
						behind it and the assumptions it rests on.
					</p>
					<div className="mt-9 flex flex-wrap gap-2.5">
						<Button asChild size="lg">
							<SiteLink href="/docs/quickstart">
								Get started <ArrowRight />
							</SiteLink>
						</Button>
						<Button asChild size="lg" variant="ghost">
							<SiteLink href="/docs">Documentation</SiteLink>
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
							Python 3.14+. The llm extra is only needed to sample a model
							(Level 2).
						</p>
					</div>
				</div>
				<ExampleReport />
			</section>

			<Section
				id="levels"
				title="Every estimate says how much evidence is behind it"
				lede="Off-policy evaluation needs to know how likely each logged choice was. agentope gets those probabilities without logprobs, picks the strongest source your data supports, and never mixes them. Each level states what it assumes."
			>
				<EvidenceLevels />
			</Section>

			<Section
				id="how"
				title="From traces to a verdict in four commands"
				lede="Evaluation looks at one decision point at a time: which tool to call, which model to route to, which prompt to use. Only sampling calls an LLM, so evaluating the same files always gives the same report."
			>
				<Pipeline />
			</Section>

			<Section
				title="When the data can't answer, it says so"
				lede="Both policies were evaluated on the same logs. The second escalates every pro customer, but escalation was never explored, so nothing in the data says how it would have gone."
			>
				<Compare />
			</Section>

			<Section
				id="start"
				title="Works with what you already run"
				lede="An OTLP export from your tracing, a model server that speaks the OpenAI chat API, and a CSV of outcomes such as resolved tickets or purchases."
				className="grid grid-cols-1 items-start gap-12 lg:grid-cols-[minmax(0,16rem)_minmax(0,1fr)] lg:gap-16"
			>
				<Integrations />
				<CodeTabs />
			</Section>

			<Section title="Questions">
				<Faq />
			</Section>
		</main>
	);
}
