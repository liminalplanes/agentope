import type { MDXContent } from "mdx/types";
import { type LazyExoticComponent, lazy } from "react";

export const sections = [
	"Getting started",
	"Concepts",
	"Guides",
	"Reference",
] as const;
export type Section = (typeof sections)[number];

export type Doc = {
	slug: string;
	href: string;
	title: string;
	description: string;
	section: Section;
	order: number;
};

// Docs are MDX files in src/content/docs; `index.mdx` is the docs home at /docs.
// The navigation only needs each file's frontmatter, read from the raw text, so the
// compiled pages (with their highlighted code) stay in per-page chunks.
const raw = import.meta.glob<string>("../content/docs/*.mdx", {
	eager: true,
	query: "?raw",
	import: "default",
});
const loaders = import.meta.glob<{ default: MDXContent }>(
	"../content/docs/*.mdx",
);

function slugOf(path: string): string {
	return (
		path
			.split("/")
			.pop()
			?.replace(/\.mdx$/, "") ?? ""
	);
}

function frontmatter(source: string, path: string): Record<string, string> {
	const match = /^---\r?\n([\s\S]*?)\r?\n---/.exec(source);
	if (!match) throw new Error(`${path}: missing frontmatter`);
	const fields: Record<string, string> = {};
	for (const line of match[1].split(/\r?\n/)) {
		const i = line.indexOf(":");
		if (i > 0) fields[line.slice(0, i).trim()] = line.slice(i + 1).trim();
	}
	return fields;
}

export const docs: Doc[] = Object.entries(raw)
	.map(([path, source]) => {
		const fm = frontmatter(source, path);
		const slug = slugOf(path);
		if (!sections.includes(fm.section as Section)) {
			throw new Error(`${path}: unknown section ${fm.section}`);
		}
		return {
			slug,
			href: slug === "index" ? "/docs" : `/docs/${slug}`,
			title: fm.title,
			description: fm.description,
			section: fm.section as Section,
			order: Number(fm.order ?? 0),
		};
	})
	.sort(
		(a, b) =>
			sections.indexOf(a.section) - sections.indexOf(b.section) ||
			a.order - b.order,
	);

const content = new Map<string, LazyExoticComponent<MDXContent>>(
	Object.entries(loaders).map(([path, load]) => [slugOf(path), lazy(load)]),
);

export function getDoc(slug: string): Doc | undefined {
	return docs.find((d) => d.slug === slug);
}

export function getContent(
	slug: string,
): LazyExoticComponent<MDXContent> | undefined {
	return content.get(slug);
}

export function docsBySection(): { section: Section; items: Doc[] }[] {
	return sections
		.map((section) => ({
			section,
			items: docs.filter((d) => d.section === section),
		}))
		.filter((group) => group.items.length > 0);
}

export function neighbours(slug: string): { prev?: Doc; next?: Doc } {
	const i = docs.findIndex((d) => d.slug === slug);
	return { prev: docs[i - 1], next: docs[i + 1] };
}
