import { Link } from "@tanstack/react-router";
import { Menu } from "lucide-react";
import { SiteLink } from "#/components/docs/doc-link";
import { DocsNav } from "#/components/docs/docs-nav";
import { LogoMark } from "#/components/logo";
import { ThemeToggle } from "#/components/theme-toggle";
import { Button } from "#/components/ui/button";
import {
	Sheet,
	SheetContent,
	SheetHeader,
	SheetTitle,
	SheetTrigger,
} from "#/components/ui/sheet";
import { site } from "#/lib/site";

const navLink =
	"rounded-md px-2.5 py-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground data-[status=active]:text-foreground";

export function SiteHeader() {
	return (
		<header className="sticky top-0 z-40 bg-background/80 backdrop-blur-md">
			<div className="mx-auto flex h-16 max-w-7xl items-center gap-4 px-5">
				<Link
					to="/"
					className="flex items-center gap-2 font-semibold tracking-tight"
				>
					<LogoMark />
					{site.name}
				</Link>
				<nav aria-label="Main" className="ml-auto hidden items-center sm:flex">
					<SiteLink href="/docs" className={navLink}>
						Docs
					</SiteLink>
					<a href={site.github} className={navLink}>
						GitHub
					</a>
				</nav>
				<div className="ml-auto flex items-center sm:ml-0">
					<ThemeToggle />
					<Sheet>
						<SheetTrigger asChild>
							<Button
								variant="ghost"
								size="icon"
								className="md:hidden"
								aria-label="Menu"
							>
								<Menu />
							</Button>
						</SheetTrigger>
						<SheetContent side="left" className="w-80 overflow-y-auto">
							<SheetHeader>
								<SheetTitle className="flex items-center gap-2">
									<LogoMark /> {site.name}
								</SheetTitle>
							</SheetHeader>
							<div className="px-4 pb-8">
								<DocsNav />
								<a
									href={site.github}
									className="mt-6 block text-sm text-muted-foreground hover:text-foreground"
								>
									GitHub
								</a>
							</div>
						</SheetContent>
					</Sheet>
				</div>
			</div>
		</header>
	);
}
