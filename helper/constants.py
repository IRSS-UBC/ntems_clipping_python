STRUCTURE_SHORTNAMES = {
    "loreys_height": "lh",
    "elev_p95": "p95",
    "elev_cv": "cv",
    "gross_stem_volume": "vol",
    "total_biomass": "bio",
}

# Reference Tile IDs
BC_QUESNEL_MAP = [473, 474, 475, 434, 435, 436, 395, 396, 397]

ON_MAP = [
    258,
    259,
    260,
    219,
    220,
    221,
    180,
    181,
    182,
]  # From first shapefile where some tiles do not belong to ON

ON_RM_MAP = [258, 259, 219, 220]
ON_Thunder_MAP = [
    332,
    292,
    293,
    294,
    254,
]

AB_MAP = [399, 438, 439, 478, 517]

NB_Map = [266, 267, 268, 305, 306, 307, 308, 347]

# Set this to the tile ids you want to exclude
EXCLUDED_TILES = [229]

FOREST_LULC = {
    81: "wetland-treed",
    210: "coniferous",
    220: "broadleaf",
    230: "mixed-wood",
}
