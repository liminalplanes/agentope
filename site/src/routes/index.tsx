import { createFileRoute } from "@tanstack/react-router";
import { ArrowRight } from "lucide-react";
import { CopyButton } from "#/components/copy-button";
import { SiteLink } from "#/components/docs/doc-link";
import { AnimatedTerminal } from "#/components/example/animated-terminal";
import {
	EvaluableCompact,
	LevelsCompact,
	LogoCloud,
} from "#/components/example/compact";
import { Button } from "#/components/ui/button";
import { site } from "#/lib/site";

export const Route = createFileRoute("/")({
	head: () => ({
		meta: [{ title: `${site.name} · evaluate agent decisions before go-live` }],
	}),
	component: Home,
});

function Section({
	title,
	lede,
	children,
}: {
	title: string;
	lede?: string;
	children: React.ReactNode;
}) {
	return (
		<section className="mx-auto max-w-7xl px-5 pt-24 md:pt-32">
			<h2 className="text-[clamp(1.4rem,2.4vw,1.85rem)] leading-tight font-semibold tracking-[-0.03em]">
				{title}
			</h2>
			{lede && (
				<p className="mt-3 mb-0 max-w-[40em] text-muted-foreground">{lede}</p>
			)}
			<div className="mt-8">{children}</div>
		</section>
	);
}

function Home() {
	return (
		<main>
			<section className="mx-auto max-w-7xl px-5 pt-16 md:pt-24">
				<h1 className="max-w-[14em] text-[clamp(2.4rem,5vw,3.8rem)] leading-[1.04] font-semibold tracking-[-0.045em]">
					Evaluate agent decisions before go-live.
				</h1>
				<p className="mt-6 max-w-[36em] text-lg text-muted-foreground">
					Find out whether a change to how your agent decides would actually
					help your users,{" "}
					<span className="text-foreground">
						using the conversations you already have
					</span>
					. Add exploration for the strongest evidence.
				</p>
				<div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-4">
					<Button asChild size="lg">
						<SiteLink href="/docs/quickstart">
							Get started <ArrowRight />
						</SiteLink>
					</Button>
					<div className="flex min-w-0 items-center gap-1 text-sm">
						<code className="min-w-0 overflow-x-auto whitespace-nowrap font-mono text-muted-foreground [scrollbar-width:none]">
							$ {site.install}
						</code>
						<CopyButton text={site.install} label="Copy install command" />
					</div>
				</div>

				<div className="mt-16">
					<AnimatedTerminal />
				</div>
			</section>

			<Section
				title="What you can evaluate"
				lede="A change to one decision your agent makes, with everything after it held as it was."
			>
				<EvaluableCompact />
			</Section>

			<Section
				title="How much you can trust the answer"
				lede="It depends on what your traces contain. agentope uses the strongest evidence you have, says which, and lists what the estimate assumes."
			>
				<LevelsCompact />
			</Section>

			<section className="mx-auto max-w-7xl px-5 pt-24 md:pt-32">
				<h2 className="text-center text-[clamp(1.4rem,2.4vw,1.85rem)] leading-tight font-semibold tracking-[-0.03em]">
					Works with your stack
				</h2>
				<div className="mt-10">
					<LogoCloud />
				</div>
			</section>

			<section className="mx-auto max-w-7xl px-5 pt-24 md:pt-32">
				<div className="flex flex-wrap items-center justify-between gap-6 border-t pt-8">
					<p className="m-0 max-w-[32em] text-muted-foreground">
						The docs walk through the example step by step, with exploration,
						and compare what each evidence level gives on the same agent.
					</p>
					<div className="flex flex-wrap gap-2.5">
						<Button asChild>
							<SiteLink href="/docs/quickstart">
								Try it on your agent <ArrowRight />
							</SiteLink>
						</Button>
						<Button asChild variant="ghost">
							<SiteLink href="/docs/worked-example">
								Full worked example
							</SiteLink>
						</Button>
					</div>
				</div>
			</section>
		</main>
	);
}
