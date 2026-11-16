import { example } from "#/lib/example";

/** One conversation's spans, from the simulated export. */
export function TraceTree() {
	const [root, ...children] = example.trace.tree;
	return (
		<div className="min-w-0 overflow-x-auto rounded-md border bg-card p-5">
			<pre className="m-0 font-mono text-[0.78rem] leading-[1.8]">
				<span className="block font-medium">{root.name}</span>
				{root.notes.map((note) => (
					<span key={note} className="block text-muted-foreground">
						{"│   "}
						{note}
					</span>
				))}
				{children.map((span, i) => {
					const last = i === children.length - 1;
					return (
						<span key={`${span.name} ${span.role}`} className="block">
							<span className="block">
								<span className="text-muted-foreground">
									{last ? "└─ " : "├─ "}
								</span>
								<span className="font-medium">{span.name}</span>
								{span.role && (
									<span className="text-muted-foreground">
										{"   ← "}
										{span.role}
									</span>
								)}
							</span>
							{span.notes.map((note) => (
								<span key={note} className="block text-muted-foreground">
									{last ? "      " : "│     "}
									{note}
								</span>
							))}
						</span>
					);
				})}
			</pre>
		</div>
	);
}

export function SpanJson() {
	return (
		<details className="group mt-3 text-sm">
			<summary className="cursor-pointer list-none text-muted-foreground hover:text-foreground [&::-webkit-details-marker]:hidden">
				<span className="underline underline-offset-4">
					Show the decision span as exported
				</span>
			</summary>
			<pre className="mt-3 mb-0 max-h-96 overflow-auto rounded-md border bg-card p-5 font-mono text-[0.75rem] leading-relaxed text-muted-foreground">
				{JSON.stringify(example.trace.span, null, 2)}
			</pre>
		</details>
	);
}
