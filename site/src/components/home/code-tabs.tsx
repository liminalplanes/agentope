import { CodeBlock } from "#/components/docs/mdx-components";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "#/components/ui/tabs";
import Evaluate from "#/content/snippets/evaluate.mdx";
import Explore from "#/content/snippets/explore.mdx";
import TargetYaml from "#/content/snippets/target-yaml.mdx";

const code =
	"[&_.group]:rounded-xl [&_pre]:m-0 [&_pre]:overflow-x-auto [&_pre]:p-6 [&_pre]:font-mono [&_pre]:text-[0.82rem] [&_pre]:leading-relaxed";

const tabs = [
	{ value: "explore", label: "In your agent", Content: Explore },
	{ value: "evaluate", label: "Offline", Content: Evaluate },
	{ value: "yaml", label: "A prompt change", Content: TargetYaml },
];

export function CodeTabs() {
	return (
		<Tabs defaultValue="explore" className="min-w-0 gap-4">
			<TabsList>
				{tabs.map((t) => (
					<TabsTrigger key={t.value} value={t.value}>
						{t.label}
					</TabsTrigger>
				))}
			</TabsList>
			{tabs.map(({ value, Content }) => (
				<TabsContent key={value} value={value} className={code}>
					<Content components={{ pre: CodeBlock }} />
				</TabsContent>
			))}
		</Tabs>
	);
}
