from src.datahub.datahub_crypto.crypto_lib import get_current_cryptocurrency_price
from src.datahub.datahub_stocks.extract_stocks_data import extract_stock_master_data, extract_stock_price_data

# Extract: Stocks Datahub
# TODO: This is already updating data
extract_stock_master_data()
extract_stock_price_data()

# Extract: Crypto Datahub
# TODO: This is only loading data, make consistent --> save and do historization (10 batches)
# crypto_prices = get_current_cryptocurrency_price(currency="EUR")