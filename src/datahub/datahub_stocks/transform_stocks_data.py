import pandas as pd
import logging
from ..utilities.utils import load_data, save_data

logger = logging.getLogger(__name__)

def transform_etf_master(df_master: pd.DataFrame, df_region: pd.DataFrame, out_path: str):
    df_master = df_master.merge(df_region,
                                how="left",
                                left_on="ISIN",
                                right_on="ISIN",
                                ).drop("Name_y",
                                       axis=1,
                                       ).rename(columns={"Name_x": "Name"}
                                                )
    save_data(df_master, out_path)


def transform_historization_etf_prices(df_prices_batch: pd.DataFrame, out_path: str):
    df_prices_full = load_data(out_path)

    logger.debug("QUALITY: Check if extracted price-data already exists!")
    overlap = df_prices_full.merge(df_prices_batch,
                                   left_on="Date",
                                   right_on="Date",
                                   how="inner"
                                   )
    if overlap.count()[0] == 0:
        df_prices_updated = df_prices_full.append(df_prices_batch,
                                             ignore_index=True,
                                             )
        assert df_prices_updated.count()[0] == df_prices_full.count()[0] + df_prices_batch.count()[0], "Appending prices failed!"
        save_data(df_prices_updated, out_path)
    else:
        logger.warning("INGEST: STOCKS: Price data for this date already exists! No update done!")