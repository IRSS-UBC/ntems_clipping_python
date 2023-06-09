from clip_ntems import clip_multiple_ntems_to_aoi
import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--merge_structures",
        action="store_true",
        default=False,
        help="Merge the clipped structure ntems into one file",
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
        default="/home/yye/first_project/elaine_study_area/study_grid/elaine_study_area.shp",
        help="Path to the shapefile containing the AOI",
    )
    args = parser.parse_args()
    # Get the arguments if not empty
    merge_structures = args.merge_structures
    out_dir = args.out_dir
    rasin_dir = args.rasin_dir
    aoi_path = args.aoi_path

    config = {
        "merge_structures": merge_structures,
        "out_dir": out_dir,
        "rasin_dir": rasin_dir,
        "aoi_path": aoi_path,
        "ntems": ["proxies", "elev_p95", "elev_cv"],
    }
    clip_multiple_ntems_to_aoi(config)


if __name__ == "__main__":
    main()
