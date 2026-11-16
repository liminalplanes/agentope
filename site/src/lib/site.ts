export const site = {
	name: "agentope",
	version: "0.3.0",
	description:
		"Offline evaluation of LLM agent decisions. Estimate how a different prompt, model or tool policy would have done, from the logs you already keep. No logprobs.",
	github: "https://github.com/liminalplanes/agentope",
	install:
		'uv add "agentope[llm] @ git+https://github.com/liminalplanes/agentope"',
	pipInstall:
		'pip install "agentope[llm] @ git+https://github.com/liminalplanes/agentope"',
} as const;
