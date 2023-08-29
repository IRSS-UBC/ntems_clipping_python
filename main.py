# Prepare ntems products and inventory data such as VRI for the area of interest (AOI) in Canada.
# The raw ntems can be obtained from running ntems_clipping_terra R scripts from the IRSS github repo.
# This python script provides a way to break down the ntems into smaller tiles -- we have around 300 tiles
# covering the forested areas in Canada. If you want to clip a smaller area inside each tile, you can do so
# by specifying the bounding box (bbox) in the format of (column_offset, row_offset, width, height), same
# as the Window instance from rasterio. If bbox is not specified, the entire tile will be clipped.

# Example usage: python3 main.py --bbox='(0,0,500,500)' --merge_structures
# The above command will clip the ntems to a 500x500 window starting from the top left corner of the tile, and
# also merge lidar-derived structure ntems into one file.

import ast
from clip_ntems import clip_multiple_ntems_to_aoi
import argparse


def tuple_type(s):
    try:
        return tuple(ast.literal_eval(s))
    except:
        raise argparse.ArgumentTypeError("Tuple arguments must be a tuple")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--merge_structures",
        action="store_true",
        default=False,
        help="Merge the clipped structure ntems into one file",
    )
    parser.add_argument(
        "--vri_path",
        type=str,
        default="",
        help="path to the VRI shapefile",
    )
    parser.add_argument(
        "--out_dir",
        type=str,
        default="/home/yye/first_project/ntems_2019/bc/processed_tiles/",
        help="Output directory for the clipped ntems",
    )
    parser.add_argument(
        "--rasin_dir",
        type=str,
        default="/home/yye/first_project/ntems_2019/bc/mosaiced/",
        help="Directory containing the ntems to be clipped",
    )
    parser.add_argument(
        "--aoi_path",
        type=str,
        default="/home/yye/first_project/ntems_2019/bc/bc_quesnel_study_area.shp",
        help="Path to the shapefile containing the AOI",
    )
    parser.add_argument(
        "--bbox",
        type=tuple_type,
        default=None,
        help="Bounding box (column_offset, row_offset, width, height)",
    )
    args = parser.parse_args()
    # Get the arguments if not empty
    merge_structures = args.merge_structures
    out_dir = args.out_dir
    rasin_dir = args.rasin_dir
    aoi_path = args.aoi_path
    vri_path = args.vri_path
    bbox = args.bbox
    assert bbox is None or len(bbox) == 4
    print("bbox: ", bbox)

    config = {
        "merge_structures": merge_structures,
        "vri_path": vri_path,
        "out_dir": out_dir,
        "rasin_dir": rasin_dir,
        "aoi_path": aoi_path,
        "bbox": bbox,
        "ntems": ["age"],
    }
    clip_multiple_ntems_to_aoi(config)


if __name__ == "__main__":
    main()
