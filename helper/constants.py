STRUCTURE_SHORTNAMES = {
    "loreys_height": "lh",
    "elev_p95": "p95",
    "elev_cv": "cv",
    "gross_stem_volume": "vol",
    "total_biomass": "bio",
}

# Reference Tile IDs
BC_QUESNEL_MAP = [435, 436, 396, 397]

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
ON_Thunder_MAP = [292, 293, 294, 254]

AB_MAP = [399, 438, 439, 478]

NB_Map = [305, 306, 266, 267, 268]

STUDY_AREA_TILES = {
    "bc": [435, 436, 396, 397],
    "ab": [399, 438, 439, 478],
    "on": [292, 293, 294, 254, 258, 259, 219, 220],
    "nb": [305, 306, 266, 267, 268],
}

FOREST_LULC = {
    81: "wetland-treed",
    210: "coniferous",
    220: "broadleaf",
    230: "mixed-wood",
}

# Inventory database contains non-forested stand such as wetland, shrubland, etc. We want to filter them before
# computing the summary statistics.
# Note: we already got the forested polygons for New Brunswick.
FORESTED_POLYGON_CODE = {
    "bc": {"BCLCS_LE_1": ["T"]},
    "ab": {"DENSITY": ["A", "B", "C", "D"]},
    "on": {"POLYTYPE": ["FOR"]},
}
