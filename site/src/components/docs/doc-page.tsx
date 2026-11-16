import { ArrowLeft, ArrowRight } from "lucide-react";
import { Suspense } from "react";
import { SiteLink } from "#/components/docs/doc-link";
import { mdxComponents } from "#/components/docs/mdx-components";
import { TableOfContents } from "#/components/docs/toc";
import { type Doc, getContent, neighbours } from "#/lib/docs";
import { site } from "#/lib/site";

export function DocPage({ doc }: { doc: Doc }) {
	const { prev, next } = neighbours(doc.slug);
	const Content = getContent(doc.slug);
	return (
		<div className="grid grid-cols-1 gap-10 xl:grid-cols-[minmax(0,1fr)_13rem]">
			<div className="min-w-0">
				<p className="mb-3 font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">
					{doc.section}
				</p>
				<article id="doc-article" className="prose-docs max-w-[46rem]">
					<h1>{doc.title}</h1>
					<p className="!mt-3 text-lg !text-muted-foreground">
						{doc.description}
					</p>
					<Suspense fallback={null}>
						{Content && <Content components={mdxComponents} />}
					</Suspense>
				</article>
				<nav
					aria-label="Previous and next page"
					className="mt-16 grid max-w-[46rem] grid-cols-2 gap-3 border-t pt-6"
				>
					{prev ? (
						<SiteLink
							href={prev.href}
							className="group flex flex-col gap-1 rounded-md border p-4 text-sm transition-colors hover:bg-accent"
						>
							<span className="flex items-center gap-1 text-muted-foreground">
								<ArrowLeft className="size-3.5" /> Previous
							</span>
							<span className="font-medium">{prev.title}</span>
						</SiteLink>
					) : (
						<span />
					)}
					{next ? (
						<SiteLink
							href={next.href}
							className="group flex flex-col items-end gap-1 rounded-md border p-4 text-right text-sm transition-colors hover:bg-accent"
						>
							<span className="flex items-center gap-1 text-muted-foreground">
								Next <ArrowRight className="size-3.5" />
							</span>
							<span className="font-medium">{next.title}</span>
						</SiteLink>
					) : (
						<span />
					)}
				</nav>
				<p className="mt-6 text-sm text-muted-foreground">
					Something wrong or missing?{" "}
					<a
						href={`${site.github}/issues`}
						className="underline underline-offset-3 hover:text-foreground"
					>
						Open an issue
					</a>
					.
				</p>
			</div>
			<aside className="hidden xl:block">
				<div className="sticky top-24">
					<TableOfContents articleId="doc-article" deps={doc.slug} />
				</div>
			</aside>
		</div>
	);
}
