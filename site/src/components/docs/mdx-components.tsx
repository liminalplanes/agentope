import { Info, TriangleAlert } from "lucide-react";
import type { MDXComponents } from "mdx/types";
import { type ComponentProps, useRef } from "react";
import { CopyButton } from "#/components/copy-button";
import { SiteLink } from "#/components/docs/doc-link";
import { Verdict } from "#/components/verdict";
import { cn } from "#/lib/utils";

const LANGUAGE_LABELS: Record<string, string> = {
	sh: "shell",
	bash: "shell",
	shell: "shell",
	text: "output",
	txt: "output",
	py: "python",
};

/** The frame shared by code and terminal blocks: a header with a label, then the code. */
export function CodeFrame({
	label,
	copyText,
	copyLabel = "Copy",
	children,
	className,
}: {
	label: string;
	copyText: string | (() => string);
	copyLabel?: string;
	children: React.ReactNode;
	className?: string;
}) {
	return (
		<div
			className={cn(
				"min-w-0 overflow-hidden rounded-[4px] border bg-card",
				className,
			)}
		>
			<div className="flex h-8 items-center justify-between border-b bg-muted/60 pr-1 pl-3">
				<span className="font-mono text-[0.7rem] tracking-wide text-muted-foreground">
					{label}
				</span>
				<CopyButton
					text={copyText}
					label={copyLabel}
					className="size-6 [&_svg]:size-3.5"
				/>
			</div>
			{children}
		</div>
	);
}

/** Code blocks, highlighted by Shiki at build time; labelled with the file or language. */
export function CodeBlock({
	className,
	children,
	...props
}: ComponentProps<"pre">) {
	const ref = useRef<HTMLPreElement>(null);
	const data = props as Record<string, unknown>;
	const language = String(data["data-language"] ?? "");
	const label =
		(data["data-title"] as string | undefined) ??
		LANGUAGE_LABELS[language] ??
		(language || "code");
	return (
		<CodeFrame
			label={label}
			copyText={() => ref.current?.textContent ?? ""}
			copyLabel="Copy code"
		>
			<pre
				ref={ref}
				className={cn(
					"!m-0 overflow-x-auto !bg-transparent px-4 py-3.5 font-mono text-[0.8rem] leading-relaxed",
					className,
				)}
				{...props}
			>
				{children}
			</pre>
		</CodeFrame>
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
		<div className="overflow-x-auto rounded-md border bg-card">
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
				"flex gap-3 rounded-md border p-4 text-[0.95rem]",
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
