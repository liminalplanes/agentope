import { SiteLink } from "#/components/docs/doc-link";
import { docsBySection } from "#/lib/docs";

export function DocsNav() {
	return (
		<nav aria-label="Documentation" className="flex flex-col gap-7 text-sm">
			{docsBySection().map(({ section, items }) => (
				<div key={section} className="flex flex-col gap-1">
					<p className="mb-1 px-2.5 font-mono text-[0.7rem] uppercase tracking-[0.08em] text-muted-foreground">
						{section}
					</p>
					{items.map((doc) => (
						<SiteLink
							key={doc.slug}
							href={doc.href}
							activeOptions={{ exact: true, includeHash: false }}
							className="rounded-md px-2.5 py-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground data-[status=active]:bg-accent data-[status=active]:font-medium data-[status=active]:text-foreground"
						>
							{doc.title}
						</SiteLink>
					))}
				</div>
			))}
		</nav>
	);
}
