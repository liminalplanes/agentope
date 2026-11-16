import { createFileRoute, notFound } from "@tanstack/react-router";
import { DocPage } from "#/components/docs/doc-page";
import { getDoc } from "#/lib/docs";
import { seo, site } from "#/lib/site";

export const Route = createFileRoute("/docs/")({
	loader: () => {
		if (!getDoc("index")) throw notFound();
	},
	head: () => {
		const doc = getDoc("index");
		return seo({
			title: `${doc?.title ?? "Docs"} · ${site.name}`,
			description: doc?.description,
			path: "/docs",
		});
	},
	component: () => {
		const doc = getDoc("index");
		return doc ? <DocPage doc={doc} /> : null;
	},
});
