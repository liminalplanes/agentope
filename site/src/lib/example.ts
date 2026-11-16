import data from "#/content/example/support-agent.json";
import sampledData from "#/content/example/support-agent-sampled.json";

/**
 * The support-agent example, as produced by examples/support_agent/run.py: the real
 * commands and output of the agentope CLI on simulated traces, plus the true answers
 * (known because the world is simulated). Rerun the script to refresh it.
 *
 * `example` is the scenario with exploration (Level 1, the docs walkthrough);
 * `sampled` is the agent left unchanged, with the model asked again (Level 2, the
 * landing page).
 */
export const example = data;
export const sampled = sampledData;

/** The parts of a saved report the site draws. */
export type SavedReport = {
	decision_point: string;
	target: string;
	verdict: string;
	level: { level: number; name: string; detail: string };
	estimates: {
		logging_mean: number;
		snips: number | null;
		difference: number | null;
		ci95: number[] | null;
	};
	diagnostics: {
		n: number;
		ess: number;
		ess_share: number;
		support_violation_mass: number;
	};
	assumptions: string[];
};

export const num = (x: number, digits = 3) => x.toFixed(digits);

export const signed = (x: number, digits = 3) =>
	`${x < 0 ? "−" : "+"}${Math.abs(x).toFixed(digits)}`;

export const percent = (x: number, digits = 0) =>
	`${(x * 100).toFixed(digits)}%`;

export const points = (x: number) => `${Math.abs(x * 100).toFixed(1)} points`;

export const count = (x: number) => x.toLocaleString("en-US");

/** The lines of a captured output that start with one of the given labels, in order. */
export function excerpt(output: string, labels: string[]): string {
	return output
		.split("\n")
		.filter((line) =>
			labels.some((label) => line.trimStart().startsWith(label)),
		)
		.join("\n");
}
