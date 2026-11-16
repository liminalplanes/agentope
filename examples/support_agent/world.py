"""The simulated world behind the support-agent example.

A customer-support agent runs a model that picks the first action for each new
conversation: search the knowledge base, look up the order, escalate to a human, or
answer directly. Whether the ticket gets resolved depends on the situation and on
that action. Every number here is made up, but because the world is known exactly,
so is the true effect of any policy.
"""

from __future__ import annotations

ACTIONS = ["search_kb", "lookup_order", "escalate_to_human", "__none__"]
SAFE = ["search_kb", "lookup_order", "__none__"]  # never escalate at random: people are expensive

INTENTS = {"refund": 0.30, "order_status": 0.35, "product_question": 0.25, "account": 0.10}
P_ORDER_NUMBER = {"refund": 0.65, "order_status": 0.75, "product_question": 0.10, "account": 0.05}
P_PRO = 0.25

# How the model in production chooses (before exploration), as relative weights.
_MODEL = {
    ("refund", True): {
        "lookup_order": 45,
        "search_kb": 20,
        "escalate_to_human": 25,
        "__none__": 10,
    },
    ("refund", False): {
        "lookup_order": 10,
        "search_kb": 40,
        "escalate_to_human": 30,
        "__none__": 20,
    },
    ("order_status", True): {
        "lookup_order": 55,
        "search_kb": 20,
        "escalate_to_human": 5,
        "__none__": 20,
    },
    ("order_status", False): {
        "lookup_order": 15,
        "search_kb": 35,
        "escalate_to_human": 10,
        "__none__": 40,
    },
    ("product_question", True): {
        "lookup_order": 5,
        "search_kb": 60,
        "escalate_to_human": 5,
        "__none__": 30,
    },
    ("product_question", False): {
        "lookup_order": 5,
        "search_kb": 60,
        "escalate_to_human": 5,
        "__none__": 30,
    },
    ("account", True): {
        "lookup_order": 5,
        "search_kb": 30,
        "escalate_to_human": 40,
        "__none__": 25,
    },
    ("account", False): {
        "lookup_order": 5,
        "search_kb": 30,
        "escalate_to_human": 40,
        "__none__": 25,
    },
}

# Probability that the ticket is resolved, by situation and first action.
_RESOLVED = {
    ("refund", True): {
        "lookup_order": 0.78,
        "escalate_to_human": 0.72,
        "search_kb": 0.40,
        "__none__": 0.25,
    },
    ("refund", False): {
        "lookup_order": 0.30,
        "escalate_to_human": 0.62,
        "search_kb": 0.45,
        "__none__": 0.35,
    },
    ("order_status", True): {
        "lookup_order": 0.90,
        "escalate_to_human": 0.60,
        "search_kb": 0.45,
        "__none__": 0.30,
    },
    ("order_status", False): {
        "lookup_order": 0.35,
        "escalate_to_human": 0.55,
        "search_kb": 0.48,
        "__none__": 0.50,
    },
    ("product_question", True): {
        "search_kb": 0.80,
        "__none__": 0.62,
        "escalate_to_human": 0.55,
        "lookup_order": 0.20,
    },
    ("product_question", False): {
        "search_kb": 0.80,
        "__none__": 0.62,
        "escalate_to_human": 0.55,
        "lookup_order": 0.20,
    },
    ("account", True): {
        "escalate_to_human": 0.82,
        "search_kb": 0.45,
        "__none__": 0.35,
        "lookup_order": 0.15,
    },
    ("account", False): {
        "escalate_to_human": 0.82,
        "search_kb": 0.45,
        "__none__": 0.35,
        "lookup_order": 0.15,
    },
}


def model_policy(ctx: dict) -> dict[str, float]:
    weights = dict(_MODEL[(ctx["intent"], ctx["has_order_number"])])
    if ctx["customer_tier"] == "pro":
        weights["escalate_to_human"] *= 2
    total = sum(weights.values())
    return {a: w / total for a, w in weights.items()}


def p_resolved(ctx: dict, action: str) -> float:
    p = _RESOLVED[(ctx["intent"], ctx["has_order_number"])][action]
    return min(0.98, p + (0.05 if ctx["customer_tier"] == "pro" else 0.0))


def contexts() -> list[tuple[dict, float]]:
    """Every situation with its probability."""
    out = []
    for intent, p_intent in INTENTS.items():
        for has_order in (True, False):
            p_order = P_ORDER_NUMBER[intent] if has_order else 1 - P_ORDER_NUMBER[intent]
            for tier, p_tier in (("pro", P_PRO), ("standard", 1 - P_PRO)):
                ctx = {"intent": intent, "has_order_number": has_order, "customer_tier": tier}
                out.append((ctx, p_intent * p_order * p_tier))
    return out


def value(policy) -> float:
    """The exact expected resolution rate of a policy(context, candidates) -> probs."""
    return sum(
        w * sum(p * p_resolved(ctx, a) for a, p in policy(ctx, ACTIONS).items())
        for ctx, w in contexts()
    )


def deployed(epsilon: float):
    """What actually ran: the model, with ε of decisions explored uniformly over SAFE."""

    def policy(ctx, candidates):
        model = model_policy(ctx)
        return {
            a: (1 - epsilon) * model[a] + (epsilon / len(SAFE) if a in SAFE else 0.0)
            for a in ACTIONS
        }

    return policy


# ── What the model sees ─────────────────────────────────────────────────────
# The traces carry the conversation itself, so a model server can read the situation
# back from the messages (see model_server.py).

SYSTEM_PROMPT = (
    "You are the support agent for Northwind. Choose the best first step: search the help "
    "articles, look up the customer's order, hand over to a person, or answer directly.\n"
    "Ticket: {ticket}. Customer tier: {tier}."
)

MESSAGES = {
    "refund": [
        "I'd like a refund{order}. The blender arrived cracked.",
        "Can I get my money back{order}? It's not what I ordered.",
    ],
    "order_status": [
        "Where is my package{order}? It was due on Monday.",
        "My delivery{order} still hasn't arrived.",
    ],
    "product_question": [
        "Does the X200 kettle work with a 120 V outlet{order}?",
        "Is the travel case waterproof{order}?",
    ],
    "account": [
        "I can't log in to my account{order}.",
        "How do I change the email on my account{order}?",
    ],
}

TOOLS = [
    {"type": "function", "name": "search_kb", "description": "Search the help articles."},
    {"type": "function", "name": "lookup_order", "description": "Look up an order by number."},
    {"type": "function", "name": "escalate_to_human", "description": "Hand over to a person."},
]


def customer_message(rng, ctx: dict, conversation: str) -> str:
    order = f" (order #NW-{conversation.split('-')[1]})" if ctx["has_order_number"] else ""
    return rng.choice(MESSAGES[ctx["intent"]]).format(order=order)


def situation(system: str, user: str) -> dict:
    """Read the situation back from the conversation, as the model would."""
    text = user.lower()
    if "refund" in text or "money back" in text:
        intent = "refund"
    elif "package" in text or "delivery" in text:
        intent = "order_status"
    elif "log in" in text or "account" in text:
        intent = "account"
    else:
        intent = "product_question"
    return {
        "intent": intent,
        "has_order_number": "#NW-" in user,
        "customer_tier": "pro" if "tier: pro" in system.lower() else "standard",
    }
