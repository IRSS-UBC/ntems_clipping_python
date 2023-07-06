import fiona
from shapely.geometry import shape
import rasterio
import geopandas as gpd
import numpy as np
import os
from osgeo import gdal
from rasterio.windows import from_bounds
from rasterio.transform import xy
from shapely.geometry import Polygon
from helper.constants import EXCLUDED_TILES, STRUCTURE_SHORTNAMES
from helper.io_handler import (
    find_file,
    write_raster_to_file,
    change_interleave_with_gdal,
    add_tmp_to_filename,
    make_tile_dir_if_not_exist,
    make_rasout_names,
    append_bbox_to_filename_if_exists,
)
from helper.process_raster import normalize_image, prepare_mask_from_vlce


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
                    print("Current window shape: ", win.width, win.height)
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
                out_norm_path_tmp = add_tmp_to_filename(out_norm_path)
                # write_raster_to_file(win_image, out_path, profile)
                updated_profile = profile.copy()
                # Two cases can share the same profile:
                # Case 1: for BAP, we should not have invalid data (represent the valid range from 1-255)
                # Case 2: for other rasters, we should have invalid data which we will set to 0
                updated_profile.update(dtype=rasterio.uint8, nodata=0)
                if rasin_name == "VLCE2.0":
                    mask = prepare_mask_from_vlce(win_image)
                    mask_path = tile_dir + f"{rasin_name}-tile-{tile_id}-mask.tif"
                    write_raster_to_file(mask, mask_path, updated_profile)
                else:
                    norm_win_image = normalize_image(win_image, nodata)
                    write_raster_to_file(
                        norm_win_image, out_norm_path_tmp, updated_profile
                    )
                    change_interleave_with_gdal(out_norm_path_tmp, out_norm_path)
                    os.remove(out_norm_path_tmp)


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
        change_interleave_with_gdal(merged_path_tmp, merged_path)
        os.remove(merged_path_tmp)
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
    vri_path = config["vri_path"]
    bbox = config["bbox"]

    print("Reading vri and aoi shapefiles")
    vri = gpd.read_file(vri_path)
    aoi = gpd.read_file(aoi_path)
    print("Finished reading shapefiles")

    with rasterio.open(vri_path) as src:  # open the raster file to get the transform
        transform = src.transform
        for _, tile in aoi.iterrows():
            tile_id = tile["Id"]
            if tile_id in EXCLUDED_TILES:
                continue
            tile_dir = make_tile_dir_if_not_exist(out_dir, tile_id, "VRI")
            out_ras_path = append_bbox_to_filename_if_exists(
                tile_dir + f"ras-VRI-tile-{tile_id}.tif", bbox
            )
            out_shp_path = append_bbox_to_filename_if_exists(
                tile_dir + f"VRI-tile-{tile_id}.shp", bbox
            )

            if bbox is not None:
                column_offset, row_offset, width, height = bbox
                with rasterio.open(
                    vri_path
                ) as src:  # open the raster file to get the transform
                    transform = src.transform
                    left, top = xy(transform, column_offset, row_offset)
                    right, bottom = xy(
                        transform, column_offset + width, row_offset + height
                    )
                bbox = Polygon(
                    [
                        (left, bottom),
                        (left, top),
                        (right, top),
                        (right, bottom),
                        (left, bottom),
                    ]
                )
            else:
                bbox = tile.geometry

            minx, miny, maxx, maxy = bbox.bounds  # get the bounds
            width = maxx - minx
            height = maxy - miny
            print(
                f"Cropping VRI with bbox width {width} and height {height} to tile: {tile_id}"
            )

            # crop the vector data with the created bounding box
            cropped_vri = gpd.clip(vri, bbox)
            # cropped_vri = gpd.clip(vri, tile.geometry)
            print("Tile VRI count: ", len(cropped_vri))
            cropped_vri["Id"] = range(1, len(cropped_vri) + 1)

            cropped_vri.to_file(out_shp_path)
            print("Saved cropped VRI to: ", out_shp_path)

            options = gdal.RasterizeOptions(
                format="GTiff",
                outputType=gdal.GDT_Float32,
                noData=-1,
                creationOptions=["COMPRESS=DEFLATE"],
                width=width,
                height=height,
                attribute="Id",
            )
            ds = gdal.Rasterize(
                out_ras_path,
                out_shp_path,
                options=options,
            )
            ds = None  # Close the file

            print(f"Saved cropped rasterized VRI to: {out_ras_path}")


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
