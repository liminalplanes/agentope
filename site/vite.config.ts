import mdx from "@mdx-js/rollup";
import rehypeShiki from "@shikijs/rehype";
import tailwindcss from "@tailwindcss/vite";
import { devtools } from "@tanstack/devtools-vite";
import { tanstackStart } from "@tanstack/react-start/plugin/vite";
import viteReact from "@vitejs/plugin-react";
import rehypeSlug from "rehype-slug";
import remarkFrontmatter from "remark-frontmatter";
import remarkGfm from "remark-gfm";
import remarkMdxFrontmatter from "remark-mdx-frontmatter";
import { defineConfig, type Plugin } from "vite";

/**
 * MDX for docs pages and snippets. Imports with a query (such as `?raw`, used to read
 * frontmatter for the navigation) are left to Vite, so they get the source text.
 */
function mdxPlugin(): Plugin {
	const plugin = mdx({
		remarkPlugins: [
			remarkGfm,
			remarkFrontmatter,
			[remarkMdxFrontmatter, { name: "frontmatter" }],
		],
		rehypePlugins: [
			rehypeSlug,
			[
				rehypeShiki,
				{
					themes: { light: "github-light", dark: "github-dark-dimmed" },
					defaultColor: false,
				},
			],
		],
	});
	const transform = plugin.transform as (
		this: unknown,
		code: string,
		id: string,
	) => Promise<unknown>;
	return {
		name: "agentope-mdx",
		enforce: "pre",
		async transform(code, id) {
			if (id.includes("?")) return null;
			return (await transform.call(this, code, id)) as { code: string } | null;
		},
	};
}

export default defineConfig({
	resolve: { tsconfigPaths: true },
	plugins: [
		devtools(),
		mdxPlugin(),
		tailwindcss(),
		// Every page is prerendered to static HTML, so the site can live on any static host.
		tanstackStart({ prerender: { enabled: true, crawlLinks: true } }),
		viteReact({ include: /\.(mdx|jsx|tsx|ts|js)$/ }),
	],
});
