"""Map exact canonical grocery names to the sections used by the reminder."""

from menus.domain.recipe import normalize_label


SECTIONS = (
    ("Fruita i verdura", "vegetables", (
        "albergínia", "albergínies", "all", "alls", "api", "aranja", "alvocat", "alvocats", "bledes", "bròquil",
        "carabassa", "carabassó", "carbassa", "carbassó", "ceba", "cebes", "ceba tendra", "cogombre", "col",
        "coliflor", "enciam", "endívia", "espàrrecs", "espinacs", "espinacs frescos", "llima", "llimona", "llimones",
        "maduixes", "mandarina", "mongeta tendra", "naps", "patata", "patates", "pastanaga", "pastanagues",
        "pebrot", "pebrot verd", "pebrot vermell", "pera", "poma", "porro", "porros", "rave", "tomàquet",
        "tomàquets", "tomàquet cirerol", "taronja", "xampinyons",
    )),
    ("Carn", "beef", (
        "botifarra", "cansalada", "carn picada", "carn picada de porc", "carn picada de vedella", "conill", "costella de porc",
        "cuixa de pollastre", "cuixes de pollastre", "filet de pollastre", "gall dindi", "llom de porc", "pernil cuit",
        "pernil salat", "pit de gall dindi", "pit de pollastre", "pollastre", "porc", "salsitxes", "vedella",
    )),
    ("Peix", "fish", (
        "bacallà", "cloïsses", "gambes", "lluç", "lloms de salmó", "lloms de bacallà", "llobarro", "musclos",
        "orada", "salmó", "salmó fumat", "sardines", "sèpia", "tonyina fresca",
    )),
    ("Lactis i ous", "eggs", (
        "formatge", "formatge feta", "formatge fresc", "formatge fresc per untar", "formatge ratllat", "iogurt",
        "iogurt natural", "llet", "llet sencera", "mantega", "mozzarella", "nata", "ou", "ous", "parmesà",
    )),
    ("Rebost", "cereals", (
        "aigua", "arròs", "arròs integral", "arròs basmati", "blat de moro en conserva", "brou de peix", "brou de pollastre",
        "brou vegetal", "canyella", "cigrons cuits", "cigrons secs", "comí", "cuscús", "curri", "espaguetis", "farina",
        "farina de blat", "farina de blat de moro", "fideus", "llenties cuites", "llenties seques", "macarrons", "mel",
        "mongetes cuites", "mongetes seques", "oli", "oli d’oliva", "oli de gira-sol", "orenga", "pa ratllat", "pasta",
        "pebre", "pebre negre", "pebre vermell", "pebre vermell dolç", "quinoa", "sal", "salsa de soja", "sucre",
        "tomàquet en conserva", "tonyina en conserva", "vinagre", "vinagre de vi",
    )),
    ("Altres", None, ()),
)


def section_key(name):
    return normalize_label(name).casefold().replace("'", "’")


SECTION_INDEX = {section_key(name): index for index, (_, _, names) in enumerate(SECTIONS) for name in names}


def reminder_sections(rows):
    grouped = [[] for _ in SECTIONS]
    for row in rows:
        grouped[SECTION_INDEX.get(section_key(row["key"][0]), len(SECTIONS) - 1)].append(row)
    return [(label, icon, items) for (label, icon, _), items in zip(SECTIONS, grouped) if items]
