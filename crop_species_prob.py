import os
import numpy as np
import rasterio
import rasterio.mask
import geopandas as gpd
from shapely.geometry import shape

# Load the study area geometry
study_area = gpd.read_file(
    "/home/yye/first_project/ntems_2019/bc/bc_quesnel_study_area.shp"
)
geometry = study_area.geometry[0]
shapely_geometry = shape(geometry)
tile_id = study_area.Id[0]

species_dir = "/mnt/e/cfs/2019_CA_forest_tree_species_probabilities"

filepaths = [
    os.path.join(species_dir, filename)
    for filename in os.listdir(species_dir)
    if filename.startswith("CA_forest") and filename.endswith(".tif")
]


def normalize_value(x):
    if x == 0:
        return 0
    return 1 + ((x - 1) * (255 - 1)) // (100 - 1)


vectorized_normalize = np.vectorize(normalize_value)


for index, row in study_area.iterrows():
    shapely_geometry = shape(row["geometry"])
    tile_id = row["Id"]
    if tile_id == 395:
        print("skip 395")
        continue
    print("Processing tile: ", tile_id)
    arrays = []

    for filepath in filepaths:
        with rasterio.open(filepath) as src:
            bounds = shapely_geometry.bounds
            win = rasterio.windows.from_bounds(*bounds, transform=src.transform)
            assert win.height == 5000 and win.width == 5000
            out_image = src.read(window=win)
            out_image = vectorized_normalize(out_image).astype(np.uint8)

            arrays.append(out_image[0])
            cropped_transform = src.window_transform(win)

    # Stack all cropped arrays for easier computation
    data_stack = np.stack(arrays, axis=0)

    # Get the dimensions of the cropped data
    channels, height, width = data_stack.shape
    assert channels == len(filepaths)

    # Compute the top 5 species
    mean_probs = np.nanmean(
        data_stack, axis=(1, 2)
    )  # using nanmean to ignore NaN values

    # Get indices of species with non-zero probabilities
    non_zero_indices = np.where(mean_probs > 0)[0]

    # Sort the non-zero probabilities
    sorted_indices = np.argsort(mean_probs[non_zero_indices])[::-1]

    # Get indices of the top species (up to 5)
    top_species_indices = non_zero_indices[
        sorted_indices[: min(5, len(sorted_indices))]
    ]
    top_species = [
        os.path.splitext(os.path.basename(filepaths[i]))[0] for i in top_species_indices
    ]

    # Update metadata
    metadata = {
        "top_species": top_species,
    }
    print("meta data: ", metadata)

    # Initialize a new array for the output bands
    output_bands = np.zeros((6, height, width), dtype=np.float32)

    # Compute the top 5 species probabilities and the 6th band for each pixel
    for j in range(height):
        for i in range(width):
            # Assign the probabilities of top species to the first bands
            for band, idx in enumerate(top_species_indices):
                output_bands[band, j, i] = data_stack[idx, j, i]

            # 6th band: sum of the probabilities of the rest of the species
            rest_indices = [
                x for x in range(data_stack.shape[0]) if x not in top_species_indices
            ]
            output_bands[5, j, i] = np.sum(data_stack[rest_indices, j, i])

            # Ensure the values are between 0 and 255
            assert (
                0 <= output_bands[5, j, i] <= 255
            ), f"Value out of range: {output_bands[5, j, i]}"

    # Modify the raster profile to write the output
    profile = rasterio.open(filepaths[0]).profile
    profile.update(
        {
            "height": height,
            "width": width,
            "transform": cropped_transform,
            "count": 6,
        }
    )
    out_dir = (
        f"/home/yye/first_project/ntems_2019/bc/processed_tiles/tile_{tile_id}/species/"
    )
    os.makedirs(out_dir, exist_ok=True)
    out_ras = out_dir + f"species_tile-{tile_id}-norm.tif"

    with rasterio.open(out_ras, "w", **profile) as dest:
        dest.write(output_bands)
        dest.update_tags(**metadata)

    print(f"Saved species raster at: {out_ras}")
