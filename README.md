# ntems_clipping_python

### Python script to clip multiple raster images with a shapefile and normalize the files (0-255).

#### Steps: 
1. Modify the config["ntems"] in `main.py` to include the ntems you want to clip. Possible ntems values are `proxies`, `elev_p95`, `elev_cv`, `gross_stem_volume`, `total_biomass`, and `loreys_height`. 

2. Ensure your data directory structure is as follows:
```
rasin_dir/
    proxies/ # directory name is fixed
        SRef_2019_proxy_v2.dat
    structure/
        elev_p95/
            elev_p95_2019.dat # can be any name as long as it ends with .dat
        elev_cv/
            elev_p95_2019.dat
```

3. Invoke the python script by running `python main.py --out_dir={your_path} --rasin_dir={your_path} --aoi_path={your_path}`. Optionally, `vri_path` 
of the inventory shapefile can be passed in to clip the inventory as well.

4. if pass in the `--merge_structures` flag, the normalized structure layers will be merged into a single file under merged/ directory.

5. For the usage of defining an extra bounding box to clip, refer to the top comments in `main.py`.

#### Notes:
It is assumed that your raster files are in the same CRS as the your AOI shapefile.
