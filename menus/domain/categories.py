"""The fixed V1 category vocabulary."""

CATEGORIES = (
    ("legumes", "Llegums"), ("vegetables", "Verdures"), ("cereals", "Cereals"),
    ("salads", "Amanides"), ("creams", "Cremes"), ("soups", "Sopes"),
    ("chicken", "Pollastre"), ("beef", "Vedella"), ("pork", "Porc"),
    ("pasta", "Pasta"), ("eggs", "Ous"), ("fish", "Peix"), ("fried", "Fregits"),
)
CATEGORY_KEYS_BY_NAME = {name: key for key, name in CATEGORIES}


def canonical_category_name(name):
    return "Amanides" if name == "Ensalades" else name
