import pandas as pd
from ..utilities.utils import save_data
from ..datahub_stocks.extract_stocks_data import (
    extract_conversion_rate_usDollar_euro,
)


def transform_crypto_prices(
    df_prices: pd.DataFrame, out_path: str, currency="EUR"
):
    if currency == "EUR":
        conversion_rate = extract_conversion_rate_usDollar_euro(
            dollar_to_euro=True
        )
        df_prices["price"] = df_prices["price"] * conversion_rate
        df_prices["volume_24h"] = df_prices["volume_24h"] * conversion_rate
    save_data(df_prices, out_path)
