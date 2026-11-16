import { createFileRoute, notFound } from "@tanstack/react-router";
import { DocPage } from "#/components/docs/doc-page";
import { getDoc } from "#/lib/docs";
import { site } from "#/lib/site";

export const Route = createFileRoute("/docs/")({
	loader: () => {
		if (!getDoc("index")) throw notFound();
	},
	head: () => {
		const doc = getDoc("index");
		return {
			meta: [
				{ title: `${doc?.title ?? "Docs"} · ${site.name}` },
				{ name: "description", content: doc?.description ?? site.description },
			],
		};
	},
	component: () => {
		const doc = getDoc("index");
		return doc ? <DocPage doc={doc} /> : null;
	},
});
