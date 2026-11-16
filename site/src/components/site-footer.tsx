import { SiteLink } from "#/components/docs/doc-link";
import { LogoMark } from "#/components/logo";
import { site } from "#/lib/site";

export function SiteFooter() {
	return (
		<footer className="mt-32">
			<div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 border-t px-5 py-8 text-sm text-muted-foreground">
				<span className="flex items-center gap-2">
					<LogoMark className="size-4" />
					{site.name} {site.version}
				</span>
				<nav aria-label="Footer" className="flex gap-5">
					<SiteLink href="/docs" className="hover:text-foreground">
						Docs
					</SiteLink>
					<a href={site.github} className="hover:text-foreground">
						GitHub
					</a>
				</nav>
			</div>
		</footer>
	);
}
