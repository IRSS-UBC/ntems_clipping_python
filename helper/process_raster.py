import numpy as np
import rasterio
from helper.constants import FOREST_LULC


def normalize_image(img, nodata):
    # Note: this funtion will fali if nodata is nan
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


def normalize_age_image(img, template_path, upper_age=150):
    with rasterio.open(template_path) as src:
        template = src.read()
        nodata_value = src.nodata
        print("nodata from template is ", nodata_value)
        tree_ages = 2019 - np.floor(img)
        assert np.nanmin(tree_ages) == 0
        # Cap the tree ages older than 150 years
        if upper_age == 150:
            tree_ages[tree_ages > upper_age] = upper_age
            assert np.nanmax(tree_ages) == upper_age

        else:
            # Because Jame's forest age layer is nosiy outside the NTEMS period, we might want to cap the upper age to 34 year old (since 1984).
            # Normalization is not neccessary in that case.
            tree_ages[tree_ages > upper_age] = upper_age + 1
            tree_ages = tree_ages + 1
            assert np.nanmax(tree_ages) == upper_age + 2
            assert np.nanmin(tree_ages) == 1
            tree_ages[template == nodata_value] = 0
            return tree_ages

        min_age, max_age = 0, upper_age
        normalized_tree_ages = (tree_ages - min_age) / (max_age - min_age) * 254 + 1
        assert len(normalized_tree_ages.shape) == 3
        normalized_tree_ages[template == nodata_value] = 0
    return normalized_tree_ages


def prepare_mask_from_vlce(win_image):
    mask = np.zeros(win_image.shape)
    for row in range(win_image.shape[1]):
        for col in range(win_image.shape[2]):
            if win_image[0, row, col] in FOREST_LULC:
                mask[0, row, col] = 1
    print(f"number of zeros: {mask.size - np.count_nonzero(mask)}")
    return mask
