import { cn } from "#/lib/utils";

/** π, the usual symbol for a policy. */
export function LogoMark({ className }: { className?: string }) {
	return (
		<svg
			viewBox="0 0 22 22"
			aria-hidden="true"
			className={cn("size-5.5 shrink-0", className)}
		>
			<path
				d="M3.5 7.2H18.5M8.6 7.2L7.6 17.4M14.2 7.2V15.1Q14.2 17.4 16.6 17.4"
				fill="none"
				strokeWidth="2.3"
				strokeLinecap="round"
				strokeLinejoin="round"
				className="stroke-foreground"
			/>
		</svg>
	);
}
