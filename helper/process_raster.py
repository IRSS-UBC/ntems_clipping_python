import numpy as np
import rasterio
from helper.constants import FOREST_LULC


def normalize_image(img, nodata):
    # Note: this funtion will fali if nodata is nan
    if nodata is not None:
        mask = img == nodata  # create a boolean mask of nodata values
        img = np.ma.masked_array(img, mask)

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

    img = np.ma.filled(img, fill_value=0)
    return img


# This is the current version of normalizing age image
def normalize_age_image(img, template_path):
    upper_age = 150
    with rasterio.open(template_path) as src:
        template = src.read()
        nodata_value = src.nodata
        print("nodata from template is ", nodata_value)
        tree_ages = 2019 - np.floor(img)
        assert np.nanmin(tree_ages) == 0
        # Cap the tree ages older than 150 years

        tree_ages[tree_ages > upper_age] = upper_age

        min_age, max_age = 0, upper_age
        normalized_tree_ages = (tree_ages - min_age) / (max_age - min_age) * 254 + 1
        assert len(normalized_tree_ages.shape) == 3
        normalized_tree_ages[template == nodata_value] = 0
    return normalized_tree_ages


def normalize_age_image_z_score(img, template_path, new_nodata):
    upper_age = 150

    with rasterio.open(template_path) as src:
        template = src.read()
        nodata_value = src.nodata
        print("nodata from template is ", nodata_value)

        tree_ages = 2019 - np.floor(img)
        assert np.nanmin(tree_ages) == 0

        # Cap the tree ages older than 150 years
        tree_ages[tree_ages > upper_age] = upper_age

        # Store the original nodata locations
        nodata_mask = template == nodata_value

        # Replace nodata with NaN for normalization
        tree_ages[nodata_mask] = np.nan

        mean_tree_ages = np.nanmean(tree_ages)

        # Normalize to mean 0 and standard deviation 1
        normalized_tree_ages = (tree_ages - mean_tree_ages) / np.nanstd(tree_ages)

        assert np.all(normalized_tree_ages) != 0

        # Handle nodata: Set NaN values back to NEW_NODATA_VALUE
        normalized_tree_ages[np.isnan(normalized_tree_ages)] = new_nodata

    return normalized_tree_ages


def create_mask(raster_path):
    """Create a binary mask with 1 for valid data and 0 for nodata"""
    with rasterio.open(raster_path) as src:
        band = src.read()
        nodata_value = src.nodata
        print("nodata value in raster_path ", raster_path, " is ", nodata_value)

        # Use numpy to create a mask where change is 1 and no change is -1
        mask = np.where((band == nodata_value) | (band == 2020), -1, 1)

    return mask


# This function is for experiment when I combined fire and harvest layer with the age layer. Safely ignore it.
def process_age_image(img, template_path, new_nodata, fire_path, harvest_path):
    normalized_age = normalize_age_image_z_score(img, template_path, new_nodata)

    fire_mask = create_mask(fire_path)
    harvest_mask = create_mask(harvest_path)

    fire_mask[normalized_age == 0] = 0
    harvest_mask[normalized_age == 0] = 0

    masks_float32 = [fire_mask.astype(np.float32), harvest_mask.astype(np.float32)]
    combined_data = np.vstack([normalized_age] + masks_float32)

    return combined_data


def prepare_mask_from_vlce(win_image):
    mask = np.zeros(win_image.shape)
    for row in range(win_image.shape[1]):
        for col in range(win_image.shape[2]):
            if win_image[0, row, col] in FOREST_LULC:
                mask[0, row, col] = 1
    print(f"number of zeros: {mask.size - np.count_nonzero(mask)}")
    return mask
