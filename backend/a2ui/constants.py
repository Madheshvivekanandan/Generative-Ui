"""Protocol identity and the content limits the sanitizer enforces.

The MAX_* numbers also appear in the system prompt (which interpolates them);
change a limit here and the prompt updates with it.
"""

VERSION = "v0.9"

# Our custom catalog: the six financial components, layered on top of A2UI's
# basic catalog. The client registers the matching implementations under this
# same id; it is an identifier, not a URL that gets fetched.
CATALOG_ID = "https://acme.analytics/catalogs/finance/v1.json"

# The action name every generated button sends back. One name keeps the
# client-to-server contract small: the interesting part is the context.
REFINE_ACTION = "refine"

MAX_SERIES = 4
MAX_POINTS = 24
MAX_SLICES = 6
MAX_ROWS = 25
MAX_BLOCKS = 4
MAX_ACTIONS = 2

# Which block types render as a narrow tile. Consecutive tiles are packed into
# a Row so four KPIs read as one band instead of four stacked cards.
TILE_TYPES = {"stat_card"}
