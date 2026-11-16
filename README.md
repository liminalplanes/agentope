# agentope

Offline evaluation of LLM agent decisions, without logprobs.

> Would this agent decision have gone better under a different policy?

agentope estimates how a different policy would have done at one decision point (which tool to call, which model to route to, which prompt variant to use) from logs you already have. Every number comes with its evidence level, diagnostics, a verdict (`ok` / `weak` / `unreliable`) and the assumptions it rests on.

**Documentation:** [www.agentope.dev](https://www.agentope.dev)
