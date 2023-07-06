import os
import subprocess
import rasterio
import helper.constants as constants


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
    if rasin_name in constants.STRUCTURE_SHORTNAMES or rasin_name == "merged":
        tile_dir = out_dir + "tile_" + str(tile_id) + f"/structure/{rasin_name}/"
    else:
        tile_dir = out_dir + "tile_" + str(tile_id) + f"/{rasin_name}/"
    os.makedirs(tile_dir, exist_ok=True)
    return tile_dir


def make_rasout_names(tile_dir, rasin_name, tile_id, bbox=None):
    out_path = append_bbox_to_filename_if_exists(
        tile_dir + f"{rasin_name}-tile-{tile_id}.tif", bbox
    )
    # Path for normalized image
    out_norm_path = append_bbox_to_filename_if_exists(
        tile_dir + f"{rasin_name}-tile-{tile_id}-norm.tif", bbox
    )
    return out_path, out_norm_path


def append_bbox_to_filename_if_exists(filename, bbox=None):
    base, ext = os.path.splitext(filename)

    # Check if bbox is provided and if it has the correct length
    if bbox is not None:
        assert len(bbox) == 4
        # Format the bbox into a string and append it to the filename
        bbox_string = "-{}-{}-{}-{}".format(*bbox)
        base += bbox_string

    return base + ext
