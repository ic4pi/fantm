"""Neural Credit (NC) economy configuration — pure config, no DB/auth dependencies.
1 NC = 1 $NEUR (future token) at parity."""

TIERS = {
    "apprentice": {
        "name": "Apprentice",
        "price_usd": 0,
        "stipend": 3333,
        "lookup_key": None,
        "access": "Limited basic styles",
    },
    "wordsmith": {
        "name": "Wordsmith",
        "price_usd": 9,
        "stipend": 40000,
        "lookup_key": "wordsmith_monthly",
        "access": "Selected advanced writer styles",
    },
    "laureate": {
        "name": "Laureate",
        "price_usd": 33,
        "stipend": 150000,
        "lookup_key": "laureate_monthly",
        "access": "Full agency access, incl. Chimera Blend",
    },
}

_TIER_ORDER = ["apprentice", "wordsmith", "laureate"]


def tier_rank(tier: str) -> int:
    return _TIER_ORDER.index(tier) if tier in _TIER_ORDER else 0


# ── Model roster & cost-derived multipliers ─────────────────────────────
# Every writer style below is backed by a REAL model on a REAL provider —
# no more flat multipliers on an identical Groq call. Multiplier is derived
# from each model's actual $/M-token pricing (blended 30% input / 70% output,
# since generation is output-heavy). House runs on a free Groq account, so
# it can't be the cost reference (dividing by $0 is meaningless) — the
# reference is instead the cheapest model actually being paid for. House
# itself is hardcoded to 1.0 as a business rule, not a cost ratio.
# Pricing snapshot: Aug 2026 — verify against provider consoles periodically,
# this table is the one place to update when prices move.

# provider -> model -> (input $/M, output $/M)   [source: provider pricing pages]
MODEL_PRICING = {
    "groq": {
        "llama-3.3-70b-versatile": None,  # free-tier account — no per-token cost, hardcoded 1.0 in compute_multiplier
    },
    "openrouter": {
        "sao10k/l3-lunaris-8b": (0.04, 0.05),  # cheapest paid model — the reference point, see REFERENCE_BLENDED below
        "sao10k/l3-stheno-8b": (0.05, 0.05),
        "thedrummer/rocinante-12b": (0.25, 0.25),
        "thedrummer/unslopnemo-12b": (0.40, 0.40),
        "thedrummer/skyfall-36b-v2": (0.55, 0.80),
        "sao10k/l3.3-euryale-70b": (0.65, 0.75),
        "sao10k/l3.1-euryale-70b-v2.2": (0.85, 0.85),
        # Anubis doesn't publish clean per-token pricing on OpenRouter's listing.
        # Estimated from same-class comparables actually confirmed above —
        # it's a 70B Llama 3.3 finetune, same bracket as Euryale 70B v2.2
        # ($0.85/$0.85) and Euryale L3.3 70B ($0.65/$0.75) — split the
        # difference. Correct this the moment OpenRouter shows a real rate.
        "thedrummer/anubis-70b-v1.1": (0.75, 0.80),
    },
    "venice": {
        "gemma-4-uncensored": (0.1625, 0.50),
        "venice-uncensored-1-2": (0.20, 0.90),
        "dolphin-mistral-24b-venice-edition": (0.20, 0.90),
    },
    "anthropic": {
        "claude-sonnet-5": (2.00, 10.00),
    },
}

REFERENCE_BLENDED = None  # placeholder — real value is derived below, after WRITER_STYLES exists, from
                           # the cheapest model actually assigned to a style (not just sitting in the catalog)


def _blended_cost(provider: str, model: str) -> float:
    rate = MODEL_PRICING[provider][model]
    return rate[0] * 0.3 + rate[1] * 0.7


# "Agency Writers" — style presets, each backed by a real provider+model.
# Outline generation and continuity-state tracking (generate_outline,
# update_story_state) always stay on the free House model regardless of
# style — those are structured bookkeeping calls, not the voice the reader
# actually pays for, so there's no reason to burn a premium model on them.
WRITER_STYLES = {
    "house": {
        "name": "House Style",
        "provider": "groq", "model": "llama-3.3-70b-versatile",
        "tier_req": "apprentice",
        "prompt": "",
        "uncensored": False,
    },
    "gothic_romantic": {
        "name": "The Gothic Romantic",
        "provider": "openrouter", "model": "sao10k/l3.3-euryale-70b",
        "tier_req": "wordsmith",
        "prompt": "Write in an ornate, atmospheric gothic-romantic voice — lush description, brooding emotion, candlelit dread.",
        "uncensored": False,
    },
    "noir_detective": {
        "name": "The Noir Detective",
        "provider": "openrouter", "model": "thedrummer/rocinante-12b",
        "tier_req": "wordsmith",
        "prompt": "Write in a hardboiled noir-detective voice — terse punchy sentences, cynical narration, rain-soaked streets.",
        "uncensored": False,
    },
    "pulp_adventurer": {
        "name": "The Pulp Adventurer",
        "provider": "openrouter", "model": "thedrummer/unslopnemo-12b",
        "tier_req": "wordsmith",
        "prompt": "Write in a fast-paced pulp-adventure voice — vivid action, cliffhanger momentum, larger-than-life peril.",
        "uncensored": False,
    },
    "modern_literary": {
        "name": "The Modern Literary",
        "provider": "anthropic", "model": "claude-sonnet-5",
        "tier_req": "laureate",
        "prompt": "Write in a spare, introspective literary-fiction voice — precise imagery, restrained emotion, deep interiority.",
        "uncensored": False,
    },
    "transgressionist": {
        "name": "The Transgressionist",
        "provider": "openrouter", "model": "thedrummer/skyfall-36b-v2",
        "tier_req": "laureate",
        "prompt": "Write in a nihilist, transgressive-fiction voice — spare declarative sentences, an unreliable narrator, anti-consumerist rage, dark irony, sudden visceral violence treated matter-of-factly.",
        "uncensored": False,
    },
    "barfly_confessional": {
        "name": "The Barfly Confessional",
        "provider": "openrouter", "model": "sao10k/l3.1-euryale-70b-v2.2",
        "tier_req": "laureate",
        "prompt": "Write in a dirty-realist confessional voice — blunt first-person candor, working-class squalor, unromantic drinking and desire, dark wit, no sentimentality.",
        "uncensored": False,
    },
}

# ── Uncensored pool — separate axis from writing quality, gated to Laureate.
# Prompted with an explicit floor: dark and explicit is in scope, non-consent
# and sexual violence are not — enforced at the prompt level regardless of
# how permissive the underlying model is, since that boundary isn't optional.
_UNCENSORED_FLOOR = (
    " Mature, dark, and sexually explicit content is permitted. "
    "Content involving non-consent, coercion, or sexual violence is not — "
    "keep all sexual and romantic content between consenting adult characters."
)

WRITER_STYLES.update({
    "libertine_philosopher": {
        "name": "The Libertine Philosopher",
        "provider": "openrouter", "model": "thedrummer/anubis-70b-v1.1",
        "tier_req": "laureate",
        "prompt": "Write in a philosophical libertine voice — 18th-century salon wit, characters who argue their desires as principles, sensuous and unflinching prose." + _UNCENSORED_FLOOR,
        "uncensored": True,
    },
    "unbound": {
        "name": "Unbound",
        "provider": "venice", "model": "venice-uncensored-1-2",
        "tier_req": "laureate",
        "prompt": "Write with total creative freedom and no topical restrictions beyond the floor below." + _UNCENSORED_FLOOR,
        "uncensored": True,
    },
    "dolphin_unbound": {
        "name": "Dolphin Unbound",
        "provider": "venice", "model": "dolphin-mistral-24b-venice-edition",
        "tier_req": "laureate",
        "prompt": "Write with total creative freedom and no topical restrictions beyond the floor below." + _UNCENSORED_FLOOR,
        "uncensored": True,
    },
})

REFERENCE_BLENDED = min(
    _blended_cost(v["provider"], v["model"])
    for v in WRITER_STYLES.values()
    if v["provider"] != "groq"
)  # = cheapest ACTUALLY-ASSIGNED paid model's blended cost — not the cheapest
   # model sitting unused in the catalog. Recomputed here, after the roster
   # above, so adding/removing a style automatically keeps this honest.


def compute_multiplier(provider: str, model: str) -> float:
    """NC burn multiplier, derived from real cost relative to the cheapest
    paid model actually in use. House is hardcoded to 1.0 — it's a free-tier
    account, so there's no cost ratio to derive, only the business decision
    that it's the baseline. Rounded to the nearest 0.25 so displayed prices
    stay clean."""
    if provider == "groq":
        return 1.0
    raw = _blended_cost(provider, model) / REFERENCE_BLENDED
    rounded = round(raw * 4) / 4
    return max(1.0, rounded)


# Multiplier is computed once at import time from the real pricing table above —
# never hand-authored, so it can't drift back into being fake.
for _style in WRITER_STYLES.values():
    _style["multiplier"] = compute_multiplier(_style["provider"], _style["model"])

def chimera_multiplier_range():
    """Chimera's real cost depends on which two styles get blended, so there's
    no single multiplier until both are chosen — return the range instead of
    faking a fixed number."""
    candidates = [v["multiplier"] for k, v in WRITER_STYLES.items() if k != "house"]
    if not candidates:
        return (1.0, 1.0)
    lo = round((min(candidates) + 0.5) * 4) / 4
    hi = round((max(candidates) + 0.5) * 4) / 4
    return (lo, hi)


CHIMERA_KEY = "chimera"
CHIMERA_TIER_REQ = "laureate"
CHIMERA_NAME = "Chimera Blend"


def allowed_styles_for_tier(tier: str):
    keys = [k for k, v in WRITER_STYLES.items() if tier_rank(v["tier_req"]) <= tier_rank(tier)]
    if tier_rank(CHIMERA_TIER_REQ) <= tier_rank(tier):
        keys.append(CHIMERA_KEY)
    return keys


WORDS_PER_CHAPTER_ESTIMATE = 900


def style_multiplier(style: str, style_secondary_a: str = None, style_secondary_b: str = None) -> float:
    if style == CHIMERA_KEY:
        # Two models actually run in spirit (the prompt blends both voices),
        # so price it off the pricier of the two, plus a fixed blend premium —
        # not a flat constant disconnected from what's actually being blended.
        a = WRITER_STYLES.get(style_secondary_a or "gothic_romantic", WRITER_STYLES["house"])
        b = WRITER_STYLES.get(style_secondary_b or "noir_detective", WRITER_STYLES["house"])
        return round((max(a["multiplier"], b["multiplier"]) + 0.5) * 4) / 4
    return WRITER_STYLES.get(style, WRITER_STYLES["house"])["multiplier"]


def estimate_word_cost(total_chapters: int, multiplier: float) -> int:
    import math
    return math.ceil(total_chapters * WORDS_PER_CHAPTER_ESTIMATE * multiplier)


# Agency Store — one-time NC bundles purchased with real money via Stripe
STORE_ITEMS = {
    "writer_pack": {
        "name": "Professional Writer Pack",
        "nc": 10000, "usd": 5.00, "lookup_key": "store_writer_pack",
        "desc": "A bundle of Neural Credits sized for unlocking a curated writer style's worth of generation.",
    },
    "genre_expansion": {
        "name": "Genre Expansion",
        "nc": 15000, "usd": 7.50, "lookup_key": "store_genre_expansion",
        "desc": "Extra NC for non-fiction & research-heavy memoirs and biographies.",
    },
    "visual_prop": {
        "name": "Visual Prop / Book Cover",
        "nc": 2000, "usd": 1.00, "lookup_key": "store_visual_prop",
        "desc": "Enough NC to unlock illustrations (cover + chapter art) on one book.",
    },
    "full_layout": {
        "name": "Full Project Layout & Legal",
        "nc": 5000, "usd": 2.50, "lookup_key": "store_full_layout",
        "desc": "Enough NC to export a formatted A5 PDF with back matter.",
    },
    "full_library": {
        "name": "Full Library Unlock",
        "nc": 50000, "usd": 25.00, "lookup_key": "store_full_library",
        "desc": "A large NC bundle for power users generating many books.",
    },
}

REFILL_PACKS = {
    "small": {"name": "Small Stack", "nc": 10000, "usd": 5.00, "lookup_key": "refill_small"},
    "medium": {"name": "Medium Stack", "nc": 50000, "usd": 22.00, "lookup_key": "refill_medium"},
    "large": {"name": "Large Stack", "nc": 120000, "usd": 45.00, "lookup_key": "refill_large"},
}

ILLUSTRATION_UNLOCK_COST = STORE_ITEMS["visual_prop"]["nc"]
PDF_EXPORT_COST = STORE_ITEMS["full_layout"]["nc"]
STIPEND_INTERVAL_DAYS = 30
