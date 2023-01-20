import os
import logging
import pandas as pd
from src.utilities.utils import load_data
from src.datahub.datahub_stocks.stocks_lib import get_prices, get_master_data

logger = logging.getLogger(__name__)

base_path = "/home/chris/Dropbox/Finance/data/"
base_path_out = "/home/chris/Dropbox/Finance/data/generated/"
fname_isin_full = "ETF_investing.ods"
fname_regionMapping = "ETF_regionTypes.ods"
fname_isin_needed = "portfolio_trades.ods"
fname_master_data = "master_data_stocks.ods"
fname_price_data = "stock_prices.ods"


logger.info("Loading ISIN list.")
df_etfs = load_data(base_path+fname_isin_full, sheet_name="ETF list")
isin_list_full = list(df_etfs["ISIN"].drop_duplicates())

dfn = load_data(base_path+fname_isin_needed, sheet_name="Buys")
isin_list = list(dfn["ISIN"].dropna().drop_duplicates())

logger.info("Loading additional stock master-data.")
if fname_master_data in os.listdir(base_path_out):
    # TODO: Check why loading as odf won't work
    df_master = load_data(base_path_out+fname_master_data, force_csv=True)
else:
    df_master = None
if fname_regionMapping in os.listdir(base_path_out):
    df_regions = load_data(base_path_out+fname_regionMapping)
else:
    df_regions = None
if fname_price_data in os.listdir(base_path_out):
    # TODO: Check why loading as odf won't work
    df_price = load_data(base_path_out+fname_price_data, force_csv=True)
else:
    df_price = None

def extract_stock_master_data():
    logger.info("Extract stock masterdata from justetf.com!")
    stock_dict = get_master_data(isin_list_full)
    master = pd.DataFrame(stock_dict)
    assert master.count()[0] == len(isin_list_full), "Too less rows!"
    if ~isinstance(df_regions, type(None)):
        logger.debug("Join region types to ETF master data!")
        master = master.merge(df_regions, how="left", left_on="ISIN", right_on="ISIN").drop("Name_y", axis=1)\
                        .rename(columns={"Name_x": "Name"})
    # master.to_csv(base_path_out+fname_master_data, index=False)


def extract_stock_price_data():
    logger.info("Extract stock prices from justetf.com!")
    price_dict = get_prices(isin_list)
    prices = pd.DataFrame(price_dict)
    assert prices.count()[0] == len(isin_list), "Too less rows!"
    logger.debug("Write price data to file!")
    if isinstance(df_price, type(None)):
        prices.to_csv(base_path_out+fname_price_data, index=False)
    else:
        logger.debug("Price data already exists!")
        overlap = df_price.merge(prices, left_on="Date", right_on="Date", how="inner")
        assert overlap.count()[0] == 0, "Price data for this date already exists!"
        df_price_new = df_price.append(prices, ignore_index=True)
        assert df_price_new.count()[0] == df_price.count()[0] + prices.count()[0], "Appending prices failed!"
        # df_price_new.to_csv(base_path_out+fname_price_data, index=False)
