import { createFileRoute, notFound } from "@tanstack/react-router";
import { DocPage } from "#/components/docs/doc-page";
import { getDoc } from "#/lib/docs";
import { seo, site } from "#/lib/site";

export const Route = createFileRoute("/docs/$slug")({
	loader: ({ params }) => {
		if (params.slug === "index" || !getDoc(params.slug)) throw notFound();
	},
	head: ({ params }) => {
		const doc = getDoc(params.slug);
		return seo({
			title: doc ? `${doc.title} · ${site.name}` : site.title,
			description: doc?.description,
			path: `/docs/${params.slug}`,
		});
	},
	component: DocRoute,
});

function DocRoute() {
	const { slug } = Route.useParams();
	const doc = getDoc(slug);
	return doc ? <DocPage doc={doc} /> : null;
}
