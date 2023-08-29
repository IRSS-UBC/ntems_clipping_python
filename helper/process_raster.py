import numpy as np
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


def normalize_age_image(img):
    tree_ages = 2019 - np.floor(img)
    assert np.nanmin(tree_ages) == 0
    # Cap the tree ages older than 150 years
    tree_ages[tree_ages > 150] = 150
    assert np.nanmax(tree_ages) == 150
    # Normalize the tree ages to range [1, 255]
    min_age, max_age = 0, 150  # as we capped at 150
    normalized_tree_ages = (tree_ages - min_age) / (max_age - min_age) * 254 + 1
    assert len(normalized_tree_ages.shape) == 3
    return normalized_tree_ages


def prepare_mask_from_vlce(win_image):
    mask = np.zeros(win_image.shape)
    for row in range(win_image.shape[1]):
        for col in range(win_image.shape[2]):
            if win_image[0, row, col] in FOREST_LULC:
                mask[0, row, col] = 1
    print(f"number of zeros: {mask.size - np.count_nonzero(mask)}")
    return mask
