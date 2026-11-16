import { Info, TriangleAlert } from "lucide-react";
import type { MDXComponents } from "mdx/types";
import { type ComponentProps, useRef } from "react";
import { CopyButton } from "#/components/copy-button";
import { SiteLink } from "#/components/docs/doc-link";
import { Verdict } from "#/components/verdict";
import { cn } from "#/lib/utils";

/** Code blocks (already highlighted by Shiki at build time) with a copy button. */
export function CodeBlock({
	className,
	children,
	...props
}: ComponentProps<"pre">) {
	const ref = useRef<HTMLPreElement>(null);
	return (
		<div className="group relative overflow-hidden rounded-lg border bg-card">
			<pre ref={ref} className={cn("!bg-transparent", className)} {...props}>
				{children}
			</pre>
			<CopyButton
				text={() => ref.current?.textContent ?? ""}
				label="Copy code"
				className="absolute top-2 right-2 bg-card opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100"
			/>
		</div>
	);
}

function Anchor({ href = "", children, ...props }: ComponentProps<"a">) {
	if (href.startsWith("/")) {
		return (
			<SiteLink href={href} className={props.className}>
				{children}
			</SiteLink>
		);
	}
	if (href.startsWith("#")) {
		return (
			<a href={href} {...props}>
				{children}
			</a>
		);
	}
	return (
		<a href={href} target="_blank" rel="noreferrer" {...props}>
			{children}
		</a>
	);
}

function Table(props: ComponentProps<"table">) {
	return (
		<div className="overflow-x-auto rounded-lg border bg-card">
			<table {...props} />
		</div>
	);
}

export function Callout({
	kind = "note",
	title,
	children,
}: {
	kind?: "note" | "warning";
	title?: string;
	children: React.ReactNode;
}) {
	const Icon = kind === "warning" ? TriangleAlert : Info;
	return (
		<aside
			className={cn(
				"flex gap-3 rounded-lg border p-4 text-[0.95rem]",
				kind === "warning" ? "border-weak/30 bg-weak-bg" : "bg-card",
			)}
		>
			<Icon
				className={cn(
					"mt-0.5 size-4 shrink-0",
					kind === "warning" ? "text-weak" : "text-muted-foreground",
				)}
			/>
			<div className="min-w-0 [&>p]:m-0 [&>p+p]:mt-2">
				{title && <p className="mb-1 font-medium text-foreground">{title}</p>}
				{children}
			</div>
		</aside>
	);
}

export const mdxComponents: MDXComponents = {
	pre: CodeBlock,
	a: Anchor,
	table: Table,
	Callout,
	Verdict,
};
