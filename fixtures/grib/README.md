# GRIB test vectors

Single messages cut byte for byte from GRIB files that Expedition downloaded for the Flinders Islet Race
(25–26 Sep 2026, a small area off Sydney). They cover every packing and template Day After meets in
Expedition's `grib` folder (FILE_FORMATS §9). `expected.json` holds what eccodes decodes from the same bytes
(shape, valid time, min/max/mean and three sample points), so the tests need no eccodes.

| File | Model | Templates | Licence |
|---|---|---|---|
| `gfs_025_prmsl_t53.grb2` | NOAA GFS 0.25° | grid 3.0, product 4.0, data 5.3 (spatial differencing) | public domain (NOAA) |
| `gfs_025_wave_t52.grb2` | NOAA GFS-Wave | grid 3.0, product 4.0, data 5.2 (complex packing) | public domain (NOAA) |
| `gfs_011_wind_gaussian.grb2` | NOAA GFS (Expedition 0.11°) | grid 3.40 (Gaussian), two fields in one message | public domain (NOAA) |
| `gfs_011_prate_gaussian_pdt8.grb2` | NOAA GFS (Expedition 0.11°) | grid 3.40, product 4.8 (average) | public domain (NOAA) |
| `icon_gust_pdt8_minutes.grb2` | DWD ICON | product 4.8 (maximum), time unit minutes | © DWD, CC BY 4.0 |
| `ecmwf_tp_pdt8.grb2` | ECMWF IFS open data | product 4.8 (accumulation, metres) | © ECMWF, CC BY 4.0 |

GRIB1 (Saildocs) and GRIB2 simple packing (5.0) are tested with messages the tests build themselves.
