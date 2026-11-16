# agentope site

The project page and documentation for agentope, built with TanStack Start, Tailwind CSS v4 and
shadcn/ui. Every page is prerendered to static HTML at build time.

```sh
npm install
npm run dev      # http://localhost:3000
npm run build    # static site in dist/client
npm run check    # Biome lint and format check
npx tsc --noEmit # type check
```

## Writing docs

Docs are MDX files in `src/content/docs/`. Each starts with frontmatter:

```yaml
---
title: Sampling the model
description: One sentence, shown under the title and in search results.
section: Guides          # Getting started · Concepts · Guides · Reference
order: 2                 # position within the section
---
```

The sidebar, previous/next links and page titles come from that frontmatter; a new file appears
automatically. `index.mdx` is the docs home at `/docs`. Code blocks are highlighted at build time
(Shiki, light and dark). In MDX you can use `<Callout kind="note|warning" title="…">` and
`<Verdict kind="ok|weak|unreliable" />`. Write `<` in prose as words ("below 50"), since MDX reads
it as the start of a component.

## Layout

- `src/routes/`: pages (`index.tsx` is the landing page, `docs/` the documentation)
- `src/components/home/`: landing page sections
- `src/components/docs/`: sidebar, contents list, code blocks, MDX components
- `src/components/ui/`: shadcn/ui components (`npx shadcn@latest add <name>`)
- `src/styles.css`: design tokens (light and dark) and docs typography
