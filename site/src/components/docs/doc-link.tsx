import { Link, type LinkComponentProps } from "@tanstack/react-router";

type Props = Omit<LinkComponentProps<"a">, "to" | "params"> & { href: string };

/** A typed router link for site paths ("/", "/docs", "/docs/<slug>[#hash]"); a plain link otherwise. */
export function SiteLink({ href, children, ...props }: Props) {
	const [path, hash] = href.split("#");
	if (path === "/") {
		return (
			<Link to="/" hash={hash} {...props}>
				{children}
			</Link>
		);
	}
	if (path === "/docs" || path === "/docs/") {
		return (
			<Link to="/docs" hash={hash} {...props}>
				{children}
			</Link>
		);
	}
	const match = /^\/docs\/([\w-]+)\/?$/.exec(path);
	if (match) {
		return (
			<Link to="/docs/$slug" params={{ slug: match[1] }} hash={hash} {...props}>
				{children}
			</Link>
		);
	}
	return (
		<a
			href={href}
			className={
				typeof props.className === "string" ? props.className : undefined
			}
		>
			{children as React.ReactNode}
		</a>
	);
}
