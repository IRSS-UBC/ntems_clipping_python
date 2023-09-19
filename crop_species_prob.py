# Standalone script to crop the species probability rasters to the study tile
# The species probability rasters are downloaded from the ntems website. And
# there are 37 rasters corresponding to 37 species, each pixel has values from
# 0 to 100, where 0 means no probability and 100 means 100% probability. The
# purpose of this script is to merge those 37 species into one raster after
# cropping them to the study tile. The raster should have 6 bands, where the
# first 5 bands are the probability of the top 5 species and the 6th band is
# the sum of the probabilities of the rest of the species. The values should be
# normalized to 1 - 255, where 0 is reserved for nodata if all bands are zeros.
# You should update the study_area_filepath, species_dir, and out_dir to use it.

import os
import numpy as np
import rasterio
import geopandas as gpd
from shapely.geometry import shape


def load_study_area(filepath):
    return gpd.read_file(filepath)


def get_filepaths(species_dir):
    return [
        os.path.join(species_dir, filename)
        for filename in os.listdir(species_dir)
        if filename.startswith("CA_forest") and filename.endswith(".tif")
    ]


def normalize_value(x):
    if x == 0:
        return 0
    return 1 + ((x - 1) * (255 - 1)) // (100 - 1)


vectorized_normalize = np.vectorize(normalize_value)


def crop_and_normalize_raster(filepath, shapely_geometry):
    with rasterio.open(filepath) as src:
        bounds = shapely_geometry.bounds
        win = rasterio.windows.from_bounds(*bounds, transform=src.transform)
        assert win.height == 5000 and win.width == 5000
        out_image = src.read(window=win)
        out_image = vectorized_normalize(out_image).astype(np.uint8)
        cropped_transform = src.window_transform(win)

        return out_image[0], cropped_transform


def compute_output_bands(data_stack, filepaths):
    channels, height, width = data_stack.shape
    assert channels == len(filepaths)

    mean_probs = np.nanmean(data_stack, axis=(1, 2))
    non_zero_indices = np.where(mean_probs > 0)[0]
    sorted_indices = np.argsort(mean_probs[non_zero_indices])[::-1]
    top_species_indices = non_zero_indices[
        sorted_indices[: min(5, len(sorted_indices))]
    ]
    top_species = [
        os.path.splitext(os.path.basename(filepaths[i]))[0] for i in top_species_indices
    ]

    output_bands = np.zeros((6, height, width), dtype=np.float32)
    for j in range(height):
        for i in range(width):
            for band, idx in enumerate(top_species_indices):
                output_bands[band, j, i] = data_stack[idx, j, i]

            rest_indices = [
                x for x in range(data_stack.shape[0]) if x not in top_species_indices
            ]
            output_bands[5, j, i] = np.sum(data_stack[rest_indices, j, i])
            assert (
                0 <= output_bands[5, j, i] <= 255
            ), f"Value out of range: {output_bands[5, j, i]}"

    return output_bands, top_species


def write_output_raster(
    output_bands, filepaths, top_species, tile_id, cropped_transform, out_dir
):
    profile = rasterio.open(filepaths[0]).profile
    profile.update(
        {
            "height": output_bands.shape[1],
            "width": output_bands.shape[2],
            "transform": cropped_transform,
            "count": 6,
        }
    )
    out_dir = out_dir + f"tile_{tile_id}/species/"
    os.makedirs(out_dir, exist_ok=True)
    out_ras = out_dir + f"species_tile-{tile_id}-norm.tif"

    with rasterio.open(out_ras, "w", **profile) as dest:
        dest.write(output_bands)
        dest.update_tags(top_species=top_species)

    print(f"Saved species raster at: {out_ras}")


def main():
    study_area_filepath = (
        "/home/yye/first_project/ntems_2019/on/on_thunder_bay_study_area.shp"
    )
    species_dir = "/mnt/e/cfs/2019_CA_forest_tree_species_probabilities/"
    out_dir = "/home/yye/first_project/ntems_2019/on/processed_tiles/"

    study_area = load_study_area(study_area_filepath)
    filepaths = get_filepaths(species_dir)

    for index, row in study_area.iterrows():
        shapely_geometry = shape(row["geometry"])
        tile_id = row["Id"]
        print("Processing tile: ", tile_id)

        arrays = []
        for filepath in filepaths:
            out_image, cropped_transform = crop_and_normalize_raster(
                filepath, shapely_geometry
            )
            arrays.append(out_image)
        data_stack = np.stack(arrays, axis=0)

        output_bands, top_species = compute_output_bands(data_stack, filepaths)
        write_output_raster(
            output_bands, filepaths, top_species, tile_id, cropped_transform, out_dir
        )


if __name__ == "__main__":
    main()
