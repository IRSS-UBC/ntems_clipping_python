import os
import rasterio
from helper.constants import EXCLUDED_TILES, BC_QUESNEL_MAP
from helper.process_raster import normalize_image
from clip_ntems import stack_rasters_and_write_to_file

input_dir = "/home/yye/first_project/ntems_2019/bc/processed_tiles/"
candidate_layers = ["proxies", "gross_stem_volume", "total_biomass"]


def crop_layer_into_smaller_blocks(src_path, bbox_width, bbox_height):
    with rasterio.open(src_path) as src:
        img = src.read()
        img_width = img.shape[2]
        img_height = img.shape[1]
        assert img_width % bbox_width == 0
        assert img_height % bbox_height == 0

        # Example src_path is /home/yye/first_project/ntems_2019/bc/processed_tiles/tile_435/proxies/proxies-tile-435.tif
        # I want to create a new file that looks like /home/yye/first_project/ntems_2019/bc/processed_tiles/tile_435/proxies/cropped/win1-500-500.tif
        # where win1 is the first window, 500 is the width, 500 is the height
        # The new file will be created in the same directory as the src_path
        src_dir = os.path.dirname(src_path)
        filename, _ = os.path.splitext(os.path.basename(src_path))
        new_dir = f"cropped-{bbox_width}-{bbox_height}"
        os.makedirs(os.path.join(src_dir, new_dir), exist_ok=True)
        win_counter = 1
        for i in range(0, img_width, bbox_width):
            for j in range(0, img_height, bbox_height):
                window = rasterio.windows.Window(i, j, bbox_width, bbox_height)
                win_transform = rasterio.windows.transform(window, src.transform)
                win_image = src.read(window=window)
                win_profile = src.profile
                win_profile.update(
                    width=bbox_width,
                    height=bbox_height,
                    transform=win_transform,
                    driver="GTiff",
                )
                nodata = src.nodatavals[0]
                win_profile.pop("blockxsize", None)
                win_profile.pop("blockysize", None)
                win_profile.pop("tiled", None)
                win_profile.update(dtype=rasterio.uint8, nodata=0)
                norm_win_image = normalize_image(win_image, nodata)
                win_path = os.path.join(
                    src_dir,
                    new_dir,
                    filename + f"-win-{win_counter}.tif",
                )
                print("Writing raster to ", win_path)
                with rasterio.open(win_path, "w", **win_profile) as dst:
                    dst.write(norm_win_image)
                win_counter += 1


# input_dir = "/home/yye/first_project/ntems_2019/bc/processed_tiles/"
def crop_layers(input_dir, bbox_width, bbox_height):
    # Loop through the input directory and each tile
    for tile_id in BC_QUESNEL_MAP:
        if tile_id != 435:
            continue
        tile_dir = os.path.join(input_dir, f"tile_{tile_id}")
        proxies_path = os.path.join(tile_dir, "proxies", f"proxies-tile-{tile_id}.tif")
        merged_path = os.path.join(
            tile_dir, "structure/merged", f"vol-bio-tile-{tile_id}.tif"
        )
        struct_paths = [
            os.path.join(
                tile_dir,
                "structure/gross_stem_volume",
                f"gross_stem_volume-tile-{tile_id}.tif",
            ),
            os.path.join(
                tile_dir, "structure/total_biomass", f"total_biomass-tile-{tile_id}.tif"
            ),
        ]
        # Take the raw volume and biomass layers and merge them into a single layer
        stack_rasters_and_write_to_file(struct_paths, merged_path)

        crop_layer_into_smaller_blocks(proxies_path, bbox_width, bbox_height)
        crop_layer_into_smaller_blocks(merged_path, bbox_width, bbox_height)
        break


crop_layers(
    "/home/yye/first_project/ntems_2019/bc/processed_tiles/",
    1000,
    1000,
)
