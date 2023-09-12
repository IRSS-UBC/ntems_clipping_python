import fiona
from shapely.geometry import shape
import rasterio
import geopandas as gpd
import numpy as np
import os
from shapely.geometry import Polygon
from helper.constants import EXCLUDED_TILES, STRUCTURE_SHORTNAMES
from helper.io_handler import (
    find_file,
    write_raster_to_file,
    change_interleave_with_gdal,
    make_tile_dir_if_not_exist,
    make_rasout_names,
    append_bbox_to_filename_if_exists,
)
from helper.process_raster import (
    normalize_image,
    normalize_age_image,
    prepare_mask_from_vlce,
)


# Clip a single ntem to an AOI. Optially we can specify a bbox in the format of (column_offset, row_offset, width, height)
def clip_ntems_to_aoi(rasin_name, rasin_path, aoi_path, out_dir, bbox=None):
    with fiona.open(aoi_path, "r") as shapefile:
        for feature in shapefile:
            tile_id = feature["properties"]["Id"]
            if tile_id in EXCLUDED_TILES:
                continue
            print("Processing tile: ", tile_id)
            tile_dir = make_tile_dir_if_not_exist(out_dir, tile_id, rasin_name)
            geometry = feature["geometry"]
            shapely_geometry = shape(geometry)

            with rasterio.open(rasin_path) as src:
                profile = src.profile
                nodata = src.nodatavals
                bounds = shapely_geometry.bounds
                win = rasterio.windows.from_bounds(*bounds, transform=src.transform)

                if bbox is not None:
                    # Compute a new window based on the bbox
                    # The bbox should be relative to the top left of the first window
                    win = rasterio.windows.Window(
                        win.col_off + bbox[0],
                        win.row_off + bbox[1],
                        bbox[2] - bbox[0],
                        bbox[3] - bbox[1],
                    )
                    print("New window shape: ", win.width, win.height)

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
                out_path, out_norm_path = make_rasout_names(
                    tile_dir, rasin_name, tile_id, bbox
                )
                write_raster_to_file(win_image, out_path, profile)
                updated_profile = profile.copy()
                # Two cases can share the same profile:
                # Case 1: for BAP, we should not have invalid data (represent the valid range from 1-255)
                # Case 2: for other rasters, we should have invalid data which we will set to 0
                updated_profile.update(dtype=rasterio.uint8, nodata=0)
                # Note: you must have a structure layer to as template to mask out the invalid pixels in age. For some reason,
                # using VLCE does not produce the same number of invalid pixels as using the structure layer.
                if rasin_name == "age":
                    print("Preprocessing age raster")
                    struct_path = os.path.join(
                        out_dir,
                        f"tile_{tile_id}",
                        "structure",
                        "gross_stem_volume",
                        f"gross_stem_volume-tile-{tile_id}-norm.tif",
                    )
                    print("template path: ", struct_path)
                    norm_win_image = normalize_age_image(
                        win_image,
                        struct_path,
                    )
                else:
                    norm_win_image = normalize_image(win_image, nodata)
                write_raster_to_file(norm_win_image, out_norm_path, updated_profile)
                # Elaine: you can comment out the line below if you don't need to change the interleave of the raster
                change_interleave_with_gdal(out_norm_path)


def stack_rasters_and_write_to_file(struct_paths, merged_path):
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
        with rasterio.open(merged_path, "w", **out_meta) as dest:
            for i, data in enumerate(raster_data, start=1):
                dest.write(np.squeeze(data), i)
        change_interleave_with_gdal(merged_path)
        print(f"Stacked structure raster saved at: {merged_path}")

    except Exception as e:
        print(f"An error occurred: {e}")

    finally:
        # Close all raster datasets
        for raster_dataset in raster_datasets:
            raster_dataset.close()


def merge_structure_rasters(config):
    struct_names = []
    bbox = config["bbox"]
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
            print(f"Merging the following structure layers: {struct_names}")
            struct_paths = []
            for rasin_name in struct_names:
                tile_dir = make_tile_dir_if_not_exist(out_dir, tile_id, rasin_name)
                struct_path = tile_dir + f"{rasin_name}-tile-{tile_id}-norm.tif"
                struct_paths.append(
                    append_bbox_to_filename_if_exists(struct_path, bbox)
                )
            # Merge all structure layers into a single raster
            merged_path_prefix = "-".join(
                [STRUCTURE_SHORTNAMES[name] for name in struct_names]
            )
            tile_merged_path = make_tile_dir_if_not_exist(out_dir, tile_id, "merged")
            merged_path = append_bbox_to_filename_if_exists(
                tile_merged_path + f"{merged_path_prefix}-tile-{tile_id}-norm.tif", bbox
            )
            stack_rasters_and_write_to_file(struct_paths, merged_path)


def crop_vri_shapefile(config):
    aoi_path = config["aoi_path"]
    out_dir = config["out_dir"]
    bbox_config = config["bbox"]
    vri_path = config["vri_path"]
    print("Reading vri shp path: ", vri_path)
    vri = gpd.read_file(vri_path)
    print("Original VRI data has {} rows".format(len(vri)))
    vri = vri[
        vri["INVENTORY_"] == "V"
    ]  # This is nessary because the VRI shapefile contains other types of data (e.g. grids)
    print("VRI data has {} rows after filtering".format(len(vri)))
    aoi = gpd.read_file(aoi_path)

    if bbox_config is not None:
        bbox = gpd.GeoDataFrame(
            {
                "geometry": [
                    Polygon(
                        [
                            (bbox_config[0], bbox_config[1]),
                            (bbox_config[2], bbox_config[1]),
                            (bbox_config[2], bbox_config[3]),
                            (bbox_config[0], bbox_config[3]),
                        ]
                    )
                ]
            }
        )
        bbox.crs = aoi.crs

    for _, tile in aoi.iterrows():
        tile_id = tile["Id"]
        if tile_id in EXCLUDED_TILES:
            continue
        tile_dir = make_tile_dir_if_not_exist(out_dir, tile_id, "VRI")
        out_shp_path = append_bbox_to_filename_if_exists(
            tile_dir + f"VRI-tile-{tile_id}.shp", bbox_config
        )

        tile_gdf = gpd.GeoDataFrame([tile.geometry], columns=["geometry"], crs=aoi.crs)
        vri_cropped = gpd.overlay(vri, tile_gdf, how="intersection")

        if bbox_config is not None:
            vri_cropped = gpd.overlay(vri_cropped, bbox, how="intersection")

        vri_cropped.to_file(out_shp_path)
        print("Saved cropped VRI to: ", out_shp_path)


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
        clip_ntems_to_aoi(
            rasin_name, rasin_path, config["aoi_path"], out_dir, config["bbox"]
        )

    if config["merge_structures"]:
        merge_structure_rasters(config)

    if config["vri_path"]:
        crop_vri_shapefile(config)
