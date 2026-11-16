import {
	createRootRoute,
	HeadContent,
	Link,
	Scripts,
} from "@tanstack/react-router";
import { SiteFooter } from "#/components/site-footer";
import { SiteHeader } from "#/components/site-header";
import { Button } from "#/components/ui/button";
import { TooltipProvider } from "#/components/ui/tooltip";
import { site } from "#/lib/site";
import { ThemeProvider, themeInitScript } from "#/lib/theme";
import appCss from "../styles.css?url";

export const Route = createRootRoute({
	head: () => ({
		meta: [
			{ charSet: "utf-8" },
			{
				name: "viewport",
				content: "width=device-width, initial-scale=1, viewport-fit=cover",
			},
			{ title: site.name },
			{ name: "description", content: site.description },
			{
				name: "theme-color",
				content: "#f6f7f9",
				media: "(prefers-color-scheme: light)",
			},
			{
				name: "theme-color",
				content: "#0c0e11",
				media: "(prefers-color-scheme: dark)",
			},
		],
		links: [
			{ rel: "stylesheet", href: appCss },
			{ rel: "icon", type: "image/svg+xml", href: "/favicon.svg" },
		],
	}),
	shellComponent: RootDocument,
	notFoundComponent: NotFound,
});

function RootDocument({ children }: { children: React.ReactNode }) {
	return (
		<html lang="en" suppressHydrationWarning>
			<head>
				{/* biome-ignore lint/security/noDangerouslySetInnerHtml: static theme bootstrap */}
				<script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
				<HeadContent />
			</head>
			<body>
				<ThemeProvider>
					<TooltipProvider delayDuration={200}>
						<div className="flex min-h-svh flex-col">
							<SiteHeader />
							<div className="flex-1">{children}</div>
							<SiteFooter />
						</div>
					</TooltipProvider>
				</ThemeProvider>
				<Scripts />
			</body>
		</html>
	);
}

function NotFound() {
	return (
		<main className="mx-auto flex max-w-xl flex-col items-start gap-4 px-5 py-24">
			<p className="font-mono text-sm text-muted-foreground">404</p>
			<h1 className="text-3xl font-semibold tracking-tight">
				This page doesn't exist
			</h1>
			<p className="text-muted-foreground">
				The link may be out of date. The docs list every page in the sidebar.
			</p>
			<div className="flex gap-2">
				<Button asChild>
					<Link to="/docs">Open the docs</Link>
				</Button>
				<Button asChild variant="outline">
					<Link to="/">Home</Link>
				</Button>
			</div>
		</main>
	);
}
