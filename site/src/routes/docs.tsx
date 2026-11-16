import { createFileRoute, Outlet } from "@tanstack/react-router";
import { DocsNav } from "#/components/docs/docs-nav";

export const Route = createFileRoute("/docs")({ component: DocsLayout });

function DocsLayout() {
	return (
		<div className="mx-auto grid max-w-7xl grid-cols-1 gap-10 px-5 md:grid-cols-[14rem_minmax(0,1fr)]">
			<aside className="hidden md:block">
				<div className="sticky top-15 max-h-[calc(100svh-3.75rem)] overflow-y-auto py-10 pr-2">
					<DocsNav />
				</div>
			</aside>
			<main className="min-w-0 py-10">
				<Outlet />
			</main>
		</div>
	);
}
