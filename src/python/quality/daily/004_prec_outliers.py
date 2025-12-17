import sqlalchemy as sqla

import pandas as pd
import quality

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_site_qry = 'select site_id, site_name from location.site'
_sites = {}

_outlier_qry = """
select ll.site_id, ms.ts, ms.location_id, ms.position, ms.variable, ms.value
from main.sensors ms
left join location.location ll on ms.location_id = ll.location_id
where ms.ts >= :start
  and ms.ts <  :start + interval '1 day'
order by ll.site_id, ms.ts, ms.location_id, ms.variable
"""


def precipitation(prec_rows: pd.DataFrame) -> pd.DataFrame:
    """
   Examines the provided DataFrame for outliers by comparing each location observation with
   the others. This is only suitable for sites where there are multiple locations.

   For example, if a site records 0.2, 0.4, 0.2, 0.0, 100.2, 0.2, 0.6, 0.4, 0.8 mm of
   precipitation for a day, the 100.2 value will be flagged as an outlier.

   The DataFrame must be in the format returned from reading the SCMN main.sensors table,
   only contain observations that are directly comparable across the site (eg only
   soil temperature at 15cm depth, only precipitation, etc).

   The returned DataFrame has the observation timestamps rounded down to the nearest 15-minutes
   to match the reporting period of the SCMN network, and extra columns added giving the row
   MAD and z-scores for each observation when compared to the others in that time slice.

   Translated from the Polars version, which was translated from the MatLab version!
   """
    # 1) Round timestamps down to 15-minute bins
    binned_df = prec_rows.copy()
    binned_df["ts"] = pd.to_datetime(binned_df["ts"], errors="coerce")
    binned_df["rounded_ts"] = binned_df["ts"].dt.floor("15min")

    # 2) Pivot so each 15-min window is one row, columns are locations, values are means
    #    (mean handles multiple observations for a location within the same window)
    pivot_df = binned_df.pivot_table(
        index="rounded_ts",
        columns="location_id",
        values="value",
        aggfunc="mean"
    )

    # Ensure numeric values (in case of mixed dtypes)
    pivot_df = pivot_df.apply(pd.to_numeric, errors="coerce")

    # List of observation columns (one per location_id)
    value_columns = list(pivot_df.columns)

    # 3) Row median across locations (skip NaNs)
    row_median = pivot_df.median(axis=1, skipna=True)

    # 4) Absolute deviations from the row median, per location
    abs_dev_df = (pivot_df.sub(row_median, axis=0)).abs()
    abs_dev_df.columns = [f"{col}_abs_dev" for col in value_columns]

    # 5) MAD = median of the absolute deviations across the row
    mad = abs_dev_df.median(axis=1, skipna=True)

    # Enforce a minimum MAD of 0.2 (equivalent to Polars max_horizontal(mad, 0.2))
    mad = mad.clip(lower=0.2)

    # 6) Z-scores per location: |value - row_median| / MAD
    #    abs_dev_df already has absolute deviations, so divide by MAD
    zscore_df = abs_dev_df.div(mad, axis=0)
    zscore_df.columns = [f"{col}_zscore" for col in value_columns]

    # 7) Keep only rows where any z-score > 15
    has_outlier = (zscore_df > 15).any(axis=1)

    # 8) Assemble result: original pivot values + row_median + mad + abs_dev + zscores
    out_df = pd.concat(
        [pivot_df, row_median.rename("row_median"), mad.rename("mad"), abs_dev_df, zscore_df],
        axis=1
    )

    # Filter and bring rounded_ts back as a column (not index), matching Polars-style output
    out_df = out_df.loc[has_outlier].reset_index()

    return out_df


def show_precipitation_outliers(parent: quality.ReportFragment, site_df: pd.DataFrame, outlier_df: pd.DataFrame) -> None:
    # The str() conversion is required here because the columns with numeric names are
    # given back from the iterator as ints rather than strings.
    zscore_cols = [col for col in outlier_df.columns if str(col).endswith('_zscore')]
    df_filtered = outlier_df[(outlier_df[zscore_cols] >= 30).any(axis=1)]
    if df_filtered.empty:
        return

    site_id = site_df['site_id'].unique()

    rf = quality.ReportFragment(parent, title=_sites[site_id[0]], always_emit=True)
    text = '\n> Tipping bucket precipitation outliers.\n\n'
    text += '| Local time | Location | Observed | Site median | Z-score |\n'
    text += '|---|---:|---:|---:|---:|\n'

    for idx, row in df_filtered.iterrows():
        for n in row.keys():
            if str(n).endswith('_zscore') and row[n] > 20.0:
                locn = int(n.split('_')[0])
                print(f"{row['rounded_ts']} {locn} observed {row[int(locn)]:.2f}mm vs site median value of {row['row_median']:.2f}mm (z score is {row[n]:.2f})")
                text += f'| {row['rounded_ts'].astimezone('Australia/Sydney').strftime('%H:%M')} | {locn} &mdash; {quality.devs[locn][0]} | {row[int(locn)]:.2f} | {row['row_median']:.2f} | {row[n]:.2f} |\n'
                quality.emit_report = True

    rf.text = text


def process_site(parent: quality.ReportFragment, site_df: pd.DataFrame) -> None:
    # This check only makes sense for sites with multiple locations,
    # so check the number of locations before calling those comparisons.
    locns = site_df['location_id'].unique()
    if len(locns) > 1:
        prec_df = site_df[(site_df["variable"] == "Precipitation") & (site_df["position"] == 0)]
        if not prec_df.empty:
            prec_outliers = precipitation(prec_df)
            if not prec_outliers.empty:
                show_precipitation_outliers(parent, site_df, prec_outliers)


def run_check() -> None:
    with quality.ts_engine.connect() as conn:
        site_results = conn.execute(sqla.text(_site_qry))
        for site_id, site_name in site_results:
            _sites[site_id] = site_name

    df = pd.read_sql_query(sqla.text(_outlier_qry), quality.ts_engine, params={"start": quality.report_date})

    for site_id in df['site_id'].unique():
        site_df = df[(df['site_id'] == site_id)]
        process_site(quality.report_root, site_df)
