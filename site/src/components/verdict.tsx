import { cn } from "#/lib/utils";

export type VerdictKind = "ok" | "weak" | "unreliable";

const styles: Record<VerdictKind, string> = {
	ok: "text-ok bg-ok-bg",
	weak: "text-weak bg-weak-bg",
	unreliable: "text-bad bg-bad-bg",
};

export function Verdict({
	kind,
	className,
}: {
	kind: VerdictKind;
	className?: string;
}) {
	return (
		<span
			className={cn(
				"inline-flex items-center rounded-md px-2 py-0.5 font-mono text-xs font-semibold tracking-wide",
				styles[kind],
				className,
			)}
		>
			{kind}
		</span>
	);
}

export function MonoPill({
	children,
	className,
}: {
	children: React.ReactNode;
	className?: string;
}) {
	return (
		<span
			className={cn(
				"inline-flex items-center gap-1.5 whitespace-nowrap rounded-md border bg-background px-2 py-0.5 font-mono text-xs",
				className,
			)}
		>
			{children}
		</span>
	);
}
