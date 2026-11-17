#!/usr/bin/env python3
"""Extract first-24h point time series from Safe@Sea NetCDF/Zarr forecast files.

This script is the standalone version of the "Barents Sea point analysis" block from
SafeatSea_October_2026_wave_icing_loader.ipynb. It loops over forecast initialization
runs, keeps only the first 24 hours of each 2-day forecast, and writes one NetCDF file
per site (fishery1, fishery2, aquaculture, goliath, johan_castberg).

Usage:
    python safeatsea_point_extraction.py --start-date 2026-01-01 --end-date 2026-10-31
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
import zarr

BASE_URL = "https://safeatsea.s3.gra.io.cloud.ovh.net"
VARIABLES = ["swh", "icing", "ice"]


def safeatsea_filename(var: str, init_date: dt.date) -> str:
    end_date = init_date + dt.timedelta(days=2)
    return f"{var}_{init_date:%Y%m%d}T0000Z_{end_date:%Y%m%d}T0000Z_SafeAtSea.zarr"


def open_safeatsea_zarr(url: str) -> xr.Dataset:
    zarr_major = int(zarr.__version__.split(".")[0])
    if zarr_major >= 3:
        return xr.open_zarr(url, consolidated=True, zarr_format=2)
    return xr.open_zarr(url)


def nearest_point(ds: xr.Dataset, lat: float, lon: float, varname: str) -> xr.Dataset:
    lat_name = next((name for name in ds.coords if "lat" in name.lower()), None)
    lon_name = next((name for name in ds.coords if "lon" in name.lower()), None)
    if lat_name is None or lon_name is None:
        raise ValueError(
            f"Dataset does not expose a latitude/longitude pair. Available coords: {list(ds.coords)}"
        )

    ds = ds.rename({lat_name: "latitude", lon_name: "longitude"})
    return ds.sel(latitude=lat, longitude=lon, method="nearest")[[varname]]


def point_series(varnames, lat, lon, init_dates, base_url: str) -> pd.DataFrame:
    if isinstance(varnames, str):
        varnames = [varnames]

    frames = []
    for init_ts in init_dates:
        init_date = init_ts.date()
        start = pd.Timestamp(init_date)
        end = start + pd.Timedelta(hours=24)
        expected_times = pd.date_range(start=start, end=end - pd.Timedelta(hours=1), freq="h")

        series_by_var = {varname: pd.Series(np.nan, index=expected_times, dtype=float) for varname in varnames}

        for varname in varnames:
            fname = safeatsea_filename(varname, init_date)
            url = os.path.join(base_url, fname)
            try:
                ds = open_safeatsea_zarr(url)
                ds_point = nearest_point(ds, lat, lon, varname)
                ds_point = ds_point.sortby("time")
                first_24h = ds_point[varname].sel(time=slice(start, end)).reindex(time=expected_times)
                if first_24h.size > 0:
                    series_by_var[varname] = first_24h.to_series().reindex(expected_times)
            except Exception as exc:
                print(f"Skipped {init_date} [{varname}]: {exc}")

        frame = pd.DataFrame(series_by_var)
        frame = frame[~frame.index.duplicated(keep="first")]
        frames.append(frame)

    if not frames:
        raise ValueError("No valid first-24h forecast slices were found for the chosen point.")

    continuous = pd.concat(frames, axis=0).sort_index()
    continuous = continuous[~continuous.index.duplicated(keep="first")]
    return continuous


def extract_site_point_data(output_dir: str, start_date: dt.date, end_date: dt.date, base_url: str = BASE_URL):
    init_dates = pd.date_range(start_date, end_date, freq="D")
    data = {
        "fishery1": {"latlon": (75.3, 18.6)},
        "fishery2": {"latlon": (74.33, 30.4)},
        "aquaculture": {"latlon": (70.806, 25.818)},
        "goliath": {"latlon": (71.3, 22.3)},
        "johan_castberg": {"latlon": (72.5, 20.4)},
    }

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    for loc, info in data.items():
        print(f"Processing {loc}")
        point_lat, point_lon = info["latlon"]
        point_df = point_series(["icing", "swh", "ice"], point_lat, point_lon, init_dates, base_url)

        site_file = output_path / f"SafeAtSea_BarentsSea_{loc}_{start_date:%Y%m%d}_{end_date:%Y%m%d}.nc"
        point_df.to_xarray().to_netcdf(site_file)
        print(f"Wrote {site_file}")


def main():
    parser = argparse.ArgumentParser(description="Extract daily first-24h Safe@Sea point series for Barents Sea sites.")
    parser.add_argument("--start-date", type=str, default="2026-01-01", help="YYYY-MM-DD start date")
    parser.add_argument("--end-date", type=str, default="2026-10-31", help="YYYY-MM-DD end date")
    parser.add_argument("--output-dir", type=str, default="data/", help="Directory for the NetCDF output files")
    parser.add_argument("--base-url", type=str, default=BASE_URL, help="Base URL for Safe@Sea Zarr files")
    args = parser.parse_args()

    start_date = dt.date.fromisoformat(args.start_date)
    end_date = dt.date.fromisoformat(args.end_date)
    if end_date < start_date:
        raise ValueError("--end-date must be on or after --start-date")

    print(f"Safe@Sea point extraction: {start_date} to {end_date}")
    extract_site_point_data(args.output_dir, start_date, end_date, args.base_url)


if __name__ == "__main__":
    main()
