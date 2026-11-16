import { cn } from "#/lib/utils";

/** The Liminal Planes mark (from liminalplanes.com), without its fade-in animation. */
export function LiminalPlanesLogo({ className }: { className?: string }) {
	return (
		<svg
			viewBox="-48.5 -118.2 88.2 147.0"
			aria-hidden="true"
			className={cn("h-3.5 w-auto shrink-0", className)}
		>
			<rect
				x="-37.0"
				y="-70.0"
				width="74.0"
				height="140.0"
				rx="7.0"
				transform="translate(-4.4 -44.7) rotate(6)"
				fill="#3b4fb0"
			/>
			<rect
				x="-25.2"
				y="-47.6"
				width="50.3"
				height="95.2"
				rx="4.8"
				transform="translate(-6.6 -29.8) rotate(-3)"
				fill="#4278a5"
			/>
			<rect
				x="-17.0"
				y="-32.2"
				width="34.0"
				height="64.4"
				rx="3.2"
				transform="translate(-6.7 -19.4) rotate(-12)"
				fill="#48a09a"
			/>
			<rect
				x="-11.5"
				y="-21.7"
				width="22.9"
				height="43.4"
				rx="2.2"
				transform="translate(-5.6 -12.3) rotate(-21)"
				fill="#4fc98f"
			/>
			<rect
				x="-7.0"
				y="-13.3"
				width="14.1"
				height="26.6"
				rx="1.3"
				transform="translate(-4.8 -6.7) rotate(-30)"
				fill="#eafff4"
			/>
		</svg>
	);
}
