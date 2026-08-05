import json
import requests
import pandas as pd
from bs4 import BeautifulSoup


def extract_crypto_prices(num_pages=5) -> pd.DataFrame:
    """
    Scrape current price of cryptocurrencies from https://www.coinmarketcap.com/ and convert it to Euro.
    :param num_pages: Each page holds 100 cryptos with highest capitalization per default.
    :return: dataframe with Euro-price of cryptocurrency with name and symbol (ticker)
    """
    base_url = "https://www.coinmarketcap.com/"

    # website has several pages of 100 cryptos each
    for page in range(num_pages):
        url = base_url if page == 0 else base_url + "?page=" + str(page + 1)
        r = requests.get(url)
        assert r.status_code == requests.codes.ok, f"Bad request to {url}!"
        html = r.content.decode("utf-8")
        soup = BeautifulSoup(html, "html.parser")

        # Thx to  https://towardsdatascience.com/web-scraping-crypto-prices-with-python-41072ea5b5bf
        # for the tip of using the script part of the website:
        data = json.loads(
            soup.find(
                "script", id="__NEXT_DATA__", type="application/json"
            ).contents[0]
        )
        price_data = json.loads(data["props"]["initialState"])[
            "cryptocurrency"
        ]["listingLatest"]["data"]
        key_ordering = price_data[0]["keysArr"]
        price_array = price_data[1:]

        # Create a key-map used to parse the response-json
        key_map = {}
        keys_to_parse = {
            "name": "name",
            "symbol": "symbol",
            "quote.USD.price": "price",
            "quote.USD.volume24h": "volume_24h",
            "quote.USD.percentChange1h": "change_%_1h",
            "quote.USD.percentChange24h": "change_%_24h",
            "quote.USD.percentChange7d": "change_%_7d",
        }
        for idx, key in enumerate(key_ordering):
            # json structure: price_data = list({"keysArr":[holds key names], "id": str, "excludeProps": []},
            # [data coin 1], [data coin 2],...)
            # idx is the index for the key-name in the json
            if key in keys_to_parse.keys():
                key_map[idx] = key
        ## Parse coin data
        coin_data = {key_map[key]: [] for key, _ in key_map.items()}
        for coin_kpis in price_array:
            for idx, entry in enumerate(coin_kpis):
                if idx in key_map.keys():
                    coin_data[key_map[idx]].append(coin_kpis[idx])
        if page == 0:
            df_prices = pd.DataFrame(coin_data).rename(columns=keys_to_parse)
        else:
            df_coin = pd.DataFrame(coin_data).rename(columns=keys_to_parse)
            df_prices = df_prices.append(df_coin, ignore_index=True)
    ## rename IOTA symbol to get in line with exchange-namings
    df_prices["symbol"] = df_prices["symbol"].str.replace("MIOTA", "IOTA")
    return df_prices
