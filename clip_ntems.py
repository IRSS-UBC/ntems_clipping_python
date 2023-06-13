import fiona
from shapely.geometry import shape
import rasterio
from shapely.geometry import shape
import numpy as np
import os
import subprocess

STRUCTURE_SHORTNAMES = {
    "loreys_height": "lh",
    "elev_p95": "p95",
    "elev_cv": "cv",
    "gross_stem_volume": "vol",
    "total_biomass": "bio",
}

# Set this to the tile ids you want to exclude
EXCLUDED_TILES = []

NON_FOREST_LULC = {
    20: "water",
    31: "snow/ice",
    32: "rock/rubble",
    33: "exposed/barren land",
    40: "bryoid",
    50: "shrubland",
    80: "wetland",
    100: "herbs",
}


def normalize_image(img, nodata):
    if nodata is not None:
        mask = img == nodata  # create a boolean mask of nodata values
        img = np.ma.masked_array(
            img, mask
        )  # create a masked array, excluding nodata values

    for i in range(img.shape[0]):
        X = img[i, :, :]
        low = np.min(X)
        high = np.max(X)
        # Normalize img to 1 - 255, leave 0 for nodata
        img[i, :, :] = (X - low) / (high - low) * 254 + 1
        assert np.amax(img[i, :, :]) == 255
        assert np.amin(img[i, :, :]) == 1
        # set nodata values to 0
        img[i, :, :][mask[i, :, :]] = 0

    # Convert back to regular numpy array
    img = np.ma.filled(img, fill_value=0)
    return img


def find_file(target_dir, extension):
    for file in os.listdir(target_dir):
        if file.endswith(extension):
            return os.path.join(target_dir, file)
    return None


def write_raster_to_file(image, filename, profile):
    print("Writing raster to file: ", filename)
    with rasterio.open(filename, "w", **profile) as dst:
        dst.write(image)


def change_interleave_with_gdal(input_file, output_file):
    cmd = ["gdal_translate", "-co", "INTERLEAVE=PIXEL", input_file, output_file]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()

    if process.returncode != 0:
        print(f"Error: {stderr.decode()}")
    else:
        print(f"Success: {stdout.decode()}")


def add_tmp_to_filename(path):
    # split the path into directory, base (file name), and extension
    dir_name, file_name = os.path.split(path)
    base, ext = os.path.splitext(file_name)

    # append '_tmp' to the base name, keep the extension the same
    new_base = base + "_tmp"

    # join all components back into a full path
    new_path = os.path.join(dir_name, new_base + ext)

    return new_path


def make_tile_dir_if_not_exist(out_dir, tile_id, rasin_name):
    if rasin_name in STRUCTURE_SHORTNAMES or rasin_name == "merged":
        tile_dir = out_dir + "tile_" + str(tile_id) + f"/structure/{rasin_name}/"
    else:
        tile_dir = out_dir + "tile_" + str(tile_id) + f"/{rasin_name}/"
    os.makedirs(tile_dir, exist_ok=True)
    return tile_dir


def prepare_mask_from_vlce(win_image):
    mask = np.zeros(win_image.shape)
    for row in range(win_image.shape[1]):
        for col in range(win_image.shape[2]):
            if win_image[0, row, col] in NON_FOREST_LULC:
                mask[0, row, col] = 0
            else:
                mask[0, row, col] = 1
    print(f"number of zeros: {mask.size - np.count_nonzero(mask)}")
    return mask


# Clip a single ntem to an AOI
def clip_ntems_to_aoi(rasin_name, rasin_path, aoi_path, out_dir):
    with fiona.open(aoi_path, "r") as shapefile:
        for feature in shapefile:
            tile_id = feature["properties"]["Id"]
            if tile_id in EXCLUDED_TILES:
                continue
            print("Processing tile: ", tile_id)
            tile_dir = make_tile_dir_if_not_exist(out_dir, tile_id, rasin_name)
            geometry = feature["geometry"]
            shapely_geometry = shape(geometry)
            bounds = shapely_geometry.bounds

            out_path = tile_dir + f"{rasin_name}-tile-{tile_id}.tif"
            # Path for normalized image
            out_norm_path = tile_dir + f"{rasin_name}-tile-{tile_id}-norm.tif"
            out_norm_path_tmp = add_tmp_to_filename(out_norm_path)

            with rasterio.open(rasin_path) as src:
                profile = src.profile
                nodata = src.nodatavals
                win = rasterio.windows.from_bounds(*bounds, transform=src.transform)
                win_image = src.read(window=win)
                # Assert nodata are either a tuple of all None or a tuple of equal values
                assert all(x is None for x in nodata) or len(set(nodata)) == 1
                nodata = nodata[0]
                print("win image shape: ", win_image.shape)
                win_transform = src.window_transform(win)
                profile.update(
                    width=win_image.shape[2],
                    height=win_image.shape[1],
                    count=win_image.shape[0],
                    crs=src.crs,
                    transform=win_transform,
                )
                write_raster_to_file(win_image, out_path, profile)
                updated_profile = profile.copy()
                # Two cases can share the same profile:
                # Case 1: for BAP, we should not have invalid data (represent the valid range from 1-255)
                # Case 2: for other rasters, we should have invalid data which we will set to 0
                updated_profile.update(dtype=rasterio.uint8, nodata=0)
                if rasin_name == "VLCE2.0":
                    mask = prepare_mask_from_vlce(win_image)
                    write_raster_to_file(mask, out_path, updated_profile)
                else:
                    norm_win_image = normalize_image(win_image, nodata)
                    write_raster_to_file(
                        norm_win_image, out_norm_path_tmp, updated_profile
                    )
                    change_interleave_with_gdal(out_norm_path_tmp, out_norm_path)


def stack_rasters_and_write_to_file(struct_paths, merged_path):
    merged_path_tmp = add_tmp_to_filename(merged_path)
    raster_datasets = []
    raster_data = []

    try:
        # Open each raster file, append to the datasets list, and read the data into the data list
        for raster_path in struct_paths:
            ds = rasterio.open(raster_path)
            raster_datasets.append(ds)
            raster_data.append(ds.read())

        out_meta = raster_datasets[0].meta.copy()

        out_meta.update(count=len(raster_datasets))

        # Write the stacked raster to disk
        with rasterio.open(merged_path_tmp, "w", **out_meta) as dest:
            for i, data in enumerate(raster_data, start=1):
                dest.write(np.squeeze(data), i)
        # TODO: Delete the tmp file afterwards
        change_interleave_with_gdal(merged_path_tmp, merged_path)
        print(f"Stacked structure raster saved at: {merged_path}")

    except Exception as e:
        print(f"An error occurred: {e}")

    finally:
        # Close all raster datasets
        for raster_dataset in raster_datasets:
            raster_dataset.close()


def merge_structure_rasters(config):
    struct_names = []
    for rasin_name in config["ntems"]:
        if rasin_name in STRUCTURE_SHORTNAMES:
            struct_names.append(rasin_name)

    aoi_path = config["aoi_path"]
    out_dir = config["out_dir"]
    with fiona.open(aoi_path, "r") as shapefile:
        for feature in shapefile:
            tile_id = feature["properties"]["Id"]
            if tile_id in EXCLUDED_TILES:
                continue
            print(f"Merging {len(struct_names)} structure layers for tile: {tile_id}")
            struct_paths = []
            for rasin_name in struct_names:
                tile_dir = make_tile_dir_if_not_exist(out_dir, tile_id, rasin_name)
                struct_paths.append(tile_dir + f"{rasin_name}-tile-{tile_id}-norm.tif")
            # Merge all structure layers into a single raster
            merged_path_prefix = "-".join(
                [STRUCTURE_SHORTNAMES[name] for name in struct_names]
            )
            tile_merged_path = make_tile_dir_if_not_exist(out_dir, tile_id, "merged")
            merged_path = (
                tile_merged_path + f"{merged_path_prefix}-tile-{tile_id}-norm.tif"
            )
            stack_rasters_and_write_to_file(struct_paths, merged_path)


def clip_multiple_ntems_to_aoi(config):
    out_dir = config["out_dir"]
    for rasin_name in config["ntems"]:
        if rasin_name in STRUCTURE_SHORTNAMES:
            rasin_dir = os.path.join(config["rasin_dir"], "structure", rasin_name)
        else:
            rasin_dir = os.path.join(config["rasin_dir"], rasin_name)
        rasin_path = find_file(rasin_dir, ".dat")
        print("Processing raster path: ", rasin_path)
        assert rasin_path is not None
        clip_ntems_to_aoi(rasin_name, rasin_path, config["aoi_path"], out_dir)

    if config["merge_structures"]:
        merge_structure_rasters(config)
