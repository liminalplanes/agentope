import { useEffect, useState } from "react";
import { cn } from "#/lib/utils";

type Heading = { id: string; text: string; level: number };

/** "On this page": read from the rendered article, highlighted while scrolling. */
export function TableOfContents({
	articleId,
	deps,
	label = "On this page",
}: {
	articleId: string;
	deps: unknown;
	label?: string;
}) {
	const [headings, setHeadings] = useState<Heading[]>([]);
	const [active, setActive] = useState<string | null>(null);

	// biome-ignore lint/correctness/useExhaustiveDependencies: re-read when the page changes
	useEffect(() => {
		const article = document.getElementById(articleId);
		if (!article) return;
		setActive(null);
		const observer = new IntersectionObserver(
			(entries) => {
				const visible = entries.filter((e) => e.isIntersecting);
				if (visible.length) setActive(visible[0].target.id);
			},
			{ rootMargin: "-80px 0px -70% 0px" },
		);
		const read = () => {
			const nodes = Array.from(
				article.querySelectorAll<HTMLHeadingElement>("h2[id], h3[id]"),
			);
			setHeadings(
				nodes.map((n) => ({
					id: n.id,
					text: n.textContent ?? "",
					level: n.tagName === "H2" ? 2 : 3,
				})),
			);
			setActive((current) => current ?? nodes[0]?.id ?? null);
			observer.disconnect();
			for (const n of nodes) observer.observe(n);
		};
		read();
		// Page content loads lazily on client-side navigation; re-read when it arrives.
		const mutations = new MutationObserver(read);
		mutations.observe(article, { childList: true, subtree: true });
		return () => {
			mutations.disconnect();
			observer.disconnect();
		};
	}, [articleId, deps]);

	if (headings.length < 2) return null;
	return (
		<nav aria-label={label} className="text-sm">
			<p className="mb-3 font-mono text-[0.7rem] uppercase tracking-[0.08em] text-muted-foreground">
				{label}
			</p>
			<ul className="flex flex-col gap-1.5 border-l">
				{headings.map((h) => (
					<li key={h.id}>
						<a
							href={`#${h.id}`}
							className={cn(
								"-ml-px block border-l py-0.5 text-muted-foreground transition-colors hover:text-foreground",
								h.level === 3 ? "pl-6" : "pl-3",
								active === h.id
									? "border-foreground text-foreground"
									: "border-transparent",
							)}
						>
							{h.text}
						</a>
					</li>
				))}
			</ul>
		</nav>
	);
}
