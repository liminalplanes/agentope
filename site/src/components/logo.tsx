import { useId } from "react";
import { cn } from "#/lib/utils";

/** π, the usual symbol for a policy, in the Liminal Planes blue-to-green. */
export function LogoMark({ className }: { className?: string }) {
	const gradient = useId();
	return (
		<svg
			viewBox="0 0 22 22"
			aria-hidden="true"
			className={cn("size-5.5 shrink-0", className)}
		>
			<defs>
				<linearGradient
					id={gradient}
					x1="3"
					y1="5"
					x2="19"
					y2="19"
					gradientUnits="userSpaceOnUse"
				>
					<stop offset="0" stopColor="var(--logo-from)" />
					<stop offset="1" stopColor="var(--logo-to)" />
				</linearGradient>
			</defs>
			<path
				d="M3.5 7.2H18.5M8.6 7.2L7.6 17.4M14.2 7.2V15.1Q14.2 17.4 16.6 17.4"
				fill="none"
				stroke={`url(#${gradient})`}
				strokeWidth="2.3"
				strokeLinecap="round"
				strokeLinejoin="round"
			/>
		</svg>
	);
}
