import unicodedata


def search_key(text):
    return "".join(character for character in unicodedata.normalize("NFD", text.strip().casefold())
                   if unicodedata.category(character) != "Mn")


def rank_candidates(candidates, meal, latest_dates, category=None, query=""):
    query = search_key(query)
    candidates = [dish for dish in candidates if (not category or category in dish["categories"])
                  and query in search_key(dish["name"])]
    return sorted(candidates, key=lambda dish: (
        dish["special_occasion"], dish["meal_preference"] not in (meal, "both"),
        dish["id"] in latest_dates, latest_dates.get(dish["id"]), dish["id"]))
