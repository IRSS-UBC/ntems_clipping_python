# This script mosaicks each raster file across {UTM_zone} directory and saves the mosaicked file with EPSG:3978 projection.

import os
import rasterio
from rasterio.merge import merge
from rasterio.warp import calculate_default_transform, reproject, Resampling
import glob


def find_raster_groups(input_base):
    """
    Finds groups of raster files based on directory structure.
    """
    # Use glob to recursively find all .dat files. Update this accordingly.
    raster_files = glob.glob(f"{input_base}/[0-9]*/**/*/*.dat", recursive=True)
    print("All the raster files to be mosaicked are ", raster_files)

    # Group files by their directory structure (after the number, like 9S, 10S)
    file_groups = {}
    for file in raster_files:
        relative_path = os.path.relpath(file, input_base)
        directory_structure = os.path.join(*relative_path.split(os.sep)[1:-1])
        file_groups.setdefault(directory_structure, []).append(file)

    return file_groups


def reproject_raster(src_path, dst_path, dst_crs):
    with rasterio.open(src_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, dst_crs, src.width, src.height, *src.bounds, resolution=(30, 30)
        )
        kwargs = src.meta.copy()
        kwargs.update(
            {"crs": dst_crs, "transform": transform, "width": width, "height": height}
        )
        print("kwargs is ", kwargs)

        with rasterio.open(dst_path, "w", **kwargs) as dst:
            for i in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dst, i),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=dst_crs,
                    resampling=Resampling.nearest,
                )


def mosaic_rasters(file_groups, output_base, dst_crs="EPSG:3978"):
    """
    Reprojects and mosaics raster files from the given file groups.
    """
    # Process each group of files
    for dir_structure, files in file_groups.items():
        print(f"Processing group: {dir_structure}")

        reprojected_rasters = [
            f"{file.split('.')[0]}_reprojected.tif" for file in files
        ]

        # Reproject each raster to the target CRS
        for src, dst in zip(files, reprojected_rasters):
            print("reprojecting ", src, " to ", dst)
            reproject_raster(src, dst, dst_crs)

        # Mosaic reprojected rasters
        with rasterio.open(reprojected_rasters[0]) as src:
            mosaic, out_trans = merge(
                [rasterio.open(path) for path in reprojected_rasters], method="max"
            )

        # Create the output directory structure
        out_dir = os.path.join(output_base, dir_structure)
        os.makedirs(out_dir, exist_ok=True)

        # Save the result
        mosaiced_filename = dir_structure.replace("/", "_") + "_2019.dat"
        out_file = os.path.join(out_dir, mosaiced_filename)
        out_meta = src.meta.copy()
        out_meta.update(
            {
                "driver": "GTiff",
                "height": mosaic.shape[1],
                "width": mosaic.shape[2],
                "transform": out_trans,
            }
        )
        print("Mosaiced meta is ", out_meta)

        with rasterio.open(out_file, "w", **out_meta) as dst:
            dst.write(mosaic)


if __name__ == "__main__":
    # Base directories for input and output
    input_base = "/mnt/e/cfs/first_project/ntems_2019/nb"
    output_base = "/mnt/e/cfs/first_project/ntems_2019/nb/mosaiced"

    raster_groups = find_raster_groups(input_base)
    mosaic_rasters(raster_groups, output_base)
