export const site = {
	name: "agentope",
	url: "https://www.agentope.dev",
	title: "agentope - evaluate agent decisions before go-live.",
	ogImage: "/og.png",
	version: "0.3.1",
	description:
		"Find out whether a change to how your LLM agent decides would actually help your users, using the conversations you already have. Offline evaluation with evidence levels and verdicts, no logprobs.",
	github: "https://github.com/liminalplanes/agentope",
	install:
		'uv add "agentope[llm] @ git+https://github.com/liminalplanes/agentope"',
	pipInstall:
		'pip install "agentope[llm] @ git+https://github.com/liminalplanes/agentope"',
} as const;

/**
 * Title, description, canonical URL and link-preview tags for one page. Every route
 * calls this, so each page has its own canonical URL on www.agentope.dev.
 */
export function seo({
	title,
	description = site.description,
	path,
}: {
	title: string;
	description?: string;
	path: string;
}) {
	const url = `${site.url}${path === "/" ? "/" : path.replace(/\/$/, "")}`;
	const image = `${site.url}${site.ogImage}`;
	return {
		meta: [
			{ title },
			{ name: "description", content: description },
			{ property: "og:type", content: "website" },
			{ property: "og:site_name", content: site.name },
			{ property: "og:title", content: title },
			{ property: "og:description", content: description },
			{ property: "og:url", content: url },
			{ property: "og:image", content: image },
			{ property: "og:image:width", content: "1200" },
			{ property: "og:image:height", content: "630" },
			{ property: "og:image:alt", content: site.title },
			{ name: "twitter:card", content: "summary_large_image" },
			{ name: "twitter:title", content: title },
			{ name: "twitter:description", content: description },
			{ name: "twitter:image", content: image },
		],
		links: [{ rel: "canonical", href: url }],
	};
}
