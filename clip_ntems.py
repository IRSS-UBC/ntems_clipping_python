import fiona
from shapely.geometry import shape
import rasterio
from shapely.geometry import shape
import numpy as np
import os

STRUCTURES = [
    "loreys_height",
    "elev_p95",
    "elev_cv",
    "gross_stem_volume",
    "total_biomass",
]


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


def make_tile_dir(out_dir, tile_id, rasin_name):
    if rasin_name in ["elev_p95", "elev_cv", "gross_stem_volume", "total_biomass"]:
        tile_dir = out_dir + "tile_" + str(tile_id) + f"/structure/{rasin_name}/"
    else:
        tile_dir = out_dir + "tile_" + str(tile_id) + f"/{rasin_name}/"
    os.makedirs(tile_dir, exist_ok=True)
    return tile_dir


def clip_ntems_to_aoi(rasin_name, rasin_path, aoi_path, out_dir):
    with fiona.open(aoi_path, "r") as shapefile:
        for feature in shapefile:
            tile_id = feature["properties"]["Id"]
            print("Processing tile: ", tile_id)
            tile_dir = make_tile_dir(out_dir, tile_id, rasin_name)
            geometry = feature["geometry"]
            shapely_geometry = shape(geometry)
            bounds = shapely_geometry.bounds

            out_path = tile_dir + f"{rasin_name}-tile-{tile_id}.tif"
            # Path for normalized image
            out_norm_path = tile_dir + f"{rasin_name}-tile-{tile_id}-norm.tif"

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
                norm_win_image = normalize_image(win_image, nodata)
                norm_profile = profile.copy()
                # Ideally should be two cases:
                # Case 1: for BAP, we should not have invalid data (represent the valid range from 1-255)
                # Case 2: for other rasters, we should have invalid data which we will set to 0
                norm_profile.update(dtype=rasterio.uint8, nodata=0)
                write_raster_to_file(norm_win_image, out_norm_path, norm_profile)


def clip_multiple_ntems_to_aoi(config):
    out_dir = config["out_dir"]
    for rasin_name in config["ntems"]:
        if rasin_name in STRUCTURES:
            rasin_dir = os.path.join(config["rasin_dir"], "structure", rasin_name)
        else:
            rasin_dir = os.path.join(config["rasin_dir"], rasin_name)
        rasin_path = find_file(rasin_dir, ".dat")
        print("Processing raster path: ", rasin_path)
        assert rasin_path is not None
        clip_ntems_to_aoi(rasin_name, rasin_path, config["aoi_path"], out_dir)
