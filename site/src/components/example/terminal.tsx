import { CodeFrame } from "#/components/docs/mdx-components";

/** A command and what it printed, exactly as captured from a real run. */
export function Terminal({
	command,
	output,
	label = "terminal",
	className,
}: {
	command: string;
	output?: string;
	label?: string;
	className?: string;
}) {
	return (
		<CodeFrame
			label={label}
			copyText={command}
			copyLabel="Copy command"
			className={className}
		>
			<pre className="m-0 overflow-x-auto px-4 py-3.5 font-mono text-[0.78rem] leading-relaxed">
				<span className="block text-foreground">
					<span className="select-none text-muted-foreground">$ </span>
					{command}
				</span>
				{output && (
					<span className="mt-3 block text-muted-foreground">{output}</span>
				)}
			</pre>
		</CodeFrame>
	);
}
