import {
	Accordion,
	AccordionContent,
	AccordionItem,
	AccordionTrigger,
} from "#/components/ui/accordion";

const questions = [
	{
		q: "Why not use token logprobs?",
		a: "Many models and APIs don't expose them, they shift when a provider silently updates a model, top-p truncation distorts them, and multiplied over a whole response they become meaningless. agentope never reads them.",
	},
	{
		q: "Do my traces need prompts and message text?",
		a: "No. Levels 1 and 3 work from span attributes and tool spans alone. Message content is only needed for Level 2 and for testing prompt or model changes, because those replay the model on what it saw.",
	},
	{
		q: "What is a decision point?",
		a: "One place where the agent picks from a few options, such as which tool to call or which model to route to. agentope evaluates one at a time and holds everything else fixed, which keeps the variance usable.",
	},
	{
		q: "I can't randomize anything in production. Can I still use it?",
		a: "Yes, at Level 2 if you capture content and can still run the model, or at Level 3 from logged context. The report labels the weaker evidence and lists what it assumes.",
	},
	{
		q: "How is this different from LLM-as-judge?",
		a: "It estimates effects on real outcomes you record, such as resolved tickets, not on a judge's score. Judge scores can only enter at Level 4, labeled as such.",
	},
	{
		q: "Is it on PyPI?",
		a: "Not yet. Install from GitHub with the command at the top; the first release will go to PyPI as agentope.",
	},
];

export function Faq() {
	const half = Math.ceil(questions.length / 2);
	return (
		<div className="grid grid-cols-1 gap-x-16 md:grid-cols-2">
			{[questions.slice(0, half), questions.slice(half)].map((column) => (
				<Accordion key={column[0].q} type="multiple" className="border-t">
					{column.map(({ q, a }) => (
						<AccordionItem key={q} value={q}>
							<AccordionTrigger className="text-base font-normal">
								{q}
							</AccordionTrigger>
							<AccordionContent className="max-w-[36em] text-[0.95rem] text-muted-foreground">
								{a}
							</AccordionContent>
						</AccordionItem>
					))}
				</Accordion>
			))}
		</div>
	);
}
