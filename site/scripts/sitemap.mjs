// Writes dist/client/sitemap.xml from the pages the build actually prerendered.
import { readdirSync, statSync, writeFileSync } from "node:fs";
import { join, relative } from "node:path";

const SITE = "https://www.agentope.dev";
const root = new URL("../dist/client", import.meta.url).pathname;

function pages(dir) {
	return readdirSync(dir).flatMap((name) => {
		const path = join(dir, name);
		if (statSync(path).isDirectory()) return name === "assets" ? [] : pages(path);
		return name === "index.html" ? [path] : [];
	});
}

const urls = pages(root)
	.map((file) => {
		const dir = relative(root, file).replace(/index\.html$/, "").replace(/\/$/, "");
		return dir ? `${SITE}/${dir}` : `${SITE}/`;
	})
	.sort();
const today = new Date().toISOString().slice(0, 10);
const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls.map((loc) => `  <url><loc>${loc}</loc><lastmod>${today}</lastmod></url>`).join("\n")}
</urlset>
`;
writeFileSync(join(root, "sitemap.xml"), xml);
console.log(`sitemap.xml: ${urls.length} pages`);
