"""The fixed category vocabulary and membership rules."""

CATEGORIES = (
    ("legumes", "Llegums"), ("vegetables", "Verdures"), ("cereals", "Cereals"),
    ("salads", "Amanides"), ("creams", "Cremes"), ("soups", "Sopes"),
    ("chicken", "Pollastre"), ("beef", "Vedella"), ("pork", "Porc"),
    ("pasta", "Pasta"), ("pizza", "Pizza"), ("eggs", "Ous"), ("fish", "Peix"), ("fried", "Fregits"),
)
CATEGORY_KEYS_BY_NAME = {name: key for key, name in CATEGORIES}


def canonical_category_name(name):
    return "Amanides" if name == "Ensalades" else name


def pizza_membership_is_valid(primary, secondary):
    return "pizza" not in secondary and (primary != "pizza" or not secondary)
