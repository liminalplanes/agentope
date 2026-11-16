import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { Button } from "#/components/ui/button";
import {
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "#/components/ui/tooltip";
import { cn } from "#/lib/utils";

export function CopyButton({
	text,
	className,
	label = "Copy",
}: {
	text: string | (() => string);
	className?: string;
	label?: string;
}) {
	const [state, setState] = useState<"idle" | "copied" | "failed">("idle");

	async function copy() {
		try {
			await navigator.clipboard.writeText(
				typeof text === "function" ? text() : text,
			);
			setState("copied");
		} catch {
			setState("failed");
		}
		setTimeout(() => setState("idle"), 1600);
	}

	return (
		<Tooltip>
			<TooltipTrigger asChild>
				<Button
					type="button"
					variant="ghost"
					size="icon"
					onClick={copy}
					aria-label={label}
					className={cn(
						"size-8 text-muted-foreground hover:text-foreground",
						className,
					)}
				>
					{state === "copied" ? <Check className="text-ok" /> : <Copy />}
				</Button>
			</TooltipTrigger>
			<TooltipContent>
				{state === "copied"
					? "Copied"
					: state === "failed"
						? "Select and copy manually"
						: label}
			</TooltipContent>
		</Tooltip>
	);
}
