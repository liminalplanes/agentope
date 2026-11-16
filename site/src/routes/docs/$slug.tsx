import { createFileRoute, notFound } from "@tanstack/react-router";
import { DocPage } from "#/components/docs/doc-page";
import { getDoc } from "#/lib/docs";
import { site } from "#/lib/site";

export const Route = createFileRoute("/docs/$slug")({
	loader: ({ params }) => {
		if (params.slug === "index" || !getDoc(params.slug)) throw notFound();
	},
	head: ({ params }) => {
		const doc = getDoc(params.slug);
		return {
			meta: [
				{ title: doc ? `${doc.title} · ${site.name}` : site.name },
				{ name: "description", content: doc?.description ?? site.description },
			],
		};
	},
	component: DocRoute,
});

function DocRoute() {
	const { slug } = Route.useParams();
	const doc = getDoc(slug);
	return doc ? <DocPage doc={doc} /> : null;
}
