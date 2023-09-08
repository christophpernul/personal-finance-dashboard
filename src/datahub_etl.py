from datahub.datahub_crypto.extract_crypto_data import extract_crypto_prices
from datahub.datahub_crypto.transform_crypto_data import (
    transform_crypto_prices,
)
from datahub.datahub_stocks.extract_stocks_data import (
    extract_etf_master_data,
    extract_etf_price_data,
)
from datahub.datahub_stocks.transform_stocks_data import (
    transform_etf_master,
    transform_historization_etf_prices,
)
from datahub.utilities.utils import load_json, load_data

file_path_config = "datahub/meta_datahub.json"
DATAHUB_CONFIG = load_json(file_path_config)
DATAHUB_SOURCE_PATH = "/".join(
    [
        DATAHUB_CONFIG["datahubMeta"]["datahubBasePath"],
        DATAHUB_CONFIG["datahubMeta"]["sourceStageName"],
    ]
)
DATAHUB_INGEST_PATH = "/".join(
    [
        DATAHUB_CONFIG["datahubMeta"]["datahubBasePath"],
        DATAHUB_CONFIG["datahubMeta"]["ingestStageName"],
    ]
)
ETF_SOURCE_URL = DATAHUB_CONFIG["webTools"]["stockMasterSourceUrl"]

# Set source-data paths
filepath_etf_list = "/".join(
    [
        DATAHUB_SOURCE_PATH,
        DATAHUB_CONFIG["datahubMeta"]["datahubStocksName"],
        DATAHUB_CONFIG["fileMap"]["source"]["etfList"],
    ]
)
filepath_portfolio = "/".join(
    [
        DATAHUB_SOURCE_PATH,
        DATAHUB_CONFIG["datahubMeta"]["datahubStocksName"],
        DATAHUB_CONFIG["fileMap"]["source"]["etfTrades"],
    ]
)
filepath_etf_regionMap = "/".join(
    [
        DATAHUB_SOURCE_PATH,
        DATAHUB_CONFIG["datahubMeta"]["datahubStocksName"],
        DATAHUB_CONFIG["fileMap"]["source"]["etfRegionMap"],
    ]
)

# Set ingest-data paths
filepath_etf_master = "/".join(
    [
        DATAHUB_INGEST_PATH,
        DATAHUB_CONFIG["datahubMeta"]["datahubStocksName"],
        DATAHUB_CONFIG["datahubMeta"]["transformLayerName"],
        DATAHUB_CONFIG["fileMap"]["ingest"]["etfMaster"],
    ]
)
filepath_etf_prices = "/".join(
    [
        DATAHUB_INGEST_PATH,
        DATAHUB_CONFIG["datahubMeta"]["datahubStocksName"],
        DATAHUB_CONFIG["datahubMeta"]["transformLayerName"],
        DATAHUB_CONFIG["fileMap"]["ingest"]["etfPrices"],
    ]
)
filepath_crypto_prices = "/".join(
    [
        DATAHUB_INGEST_PATH,
        DATAHUB_CONFIG["datahubMeta"]["datahubCryptoName"],
        DATAHUB_CONFIG["datahubMeta"]["transformLayerName"],
        DATAHUB_CONFIG["fileMap"]["ingest"]["cryptoPrices"],
    ]
)

# Load source-data
df_etf_portfolio = load_data(filepath_portfolio, sheet_name="Buys")
df_etf_regionMap = load_data(filepath_etf_regionMap)
list_etf_isin = list(
    load_data(filepath_etf_list)["ISIN"].dropna().drop_duplicates()
)
list_etf_isin_valid = list(df_etf_portfolio["ISIN"].dropna().drop_duplicates())

# Extract: Stocks Datahub
df_etf_master = extract_etf_master_data(
    list_etf_isin,
    source_url=ETF_SOURCE_URL,
)
df_etf_prices = extract_etf_price_data(
    list_etf_isin_valid,
    source_url=ETF_SOURCE_URL,
)

# TRANSFORM: Stocks Datahub
transform_etf_master(
    df_etf_master,
    df_etf_regionMap,
    out_path=filepath_etf_master,
)
transform_historization_etf_prices(
    df_etf_prices,
    out_path=filepath_etf_prices,
)

# Extract & Transform: Crypto Datahub
df_crypto_prices = extract_crypto_prices()
transform_crypto_prices(
    df_prices=df_crypto_prices,
    out_path=filepath_crypto_prices,
)
