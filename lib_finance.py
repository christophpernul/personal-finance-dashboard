import requests
import os
from bs4 import BeautifulSoup
from datetime import date
import json
import pandas as pd

def update_cashflow_data():
    """
    Loads all existing raw files of cashflow per month, appends them and saves them in a single csv.
    :return:
    """
    base_path = "/home/chris/Dropbox/Finance/data/data_cashflow/"
    raw_data_path = os.path.join(baget_current_cryptocurrency_pricese_path, "raw/")
    out_filename = "bilanz_full"

    all_data_filenames = sorted(os.listdir(path=raw_data_path))
    for count, filename in enumerate(all_data_filenames):
        df = pd.read_csv(raw_data_path + filename)
        if count == 0:
            df_all = df.copy()
        elif count > 0:
            df_all = df_all.append(df)
        print("Bilanz " + filename[7:14] + ": Number of transactions = ", df.count()[0])
    df_all.to_csv(base_path + out_filename + ".csv", index=False)

def url_justetf(isin):
    """
    Creates the URL for justetf, that displays the overview page of a given stock according to ISIN.
    :param isin: ISIN of a stock or ETF (identifier)
    :return:
    """
    return ("https://www.justetf.com/de/etf-profile.html?query={0}&groupField=index&from=search&isin={0}#overview" \
            .format(isin))


def get_price_stock(soup_base):
    """
    Extracts price information from BeautifulSoup object created from HTML of justetf.com overview page.
    :param soup_base: BeautifulSoup from HTML of justetf.com overview page
    :return: dictionary with price, currency, Datum keys
    """
    assert isinstance(soup_base, type(BeautifulSoup())), "Input is no BeautifulSoup object!"
    price_dict = {}

    price_obj = soup_base.find_all("div", {"class": "infobox"})[0].find_all("div", {"class": "val"})[0].find_all("span")
    currency = price_obj[0].text
    price = float(price_obj[1].text.replace(".", "").replace(",", "."))

    price_dict["Currency"] = currency
    price_dict["Price"] = price
    price_dict["Date"] = date.today().strftime("%d.%m.%Y")

    return (price_dict)


def get_prices(isin_list):
    """
    Iterate through list of ISINs and call justetf.com overview page for each stock and extract price informations.
    :param isin_list: list of ISINs for all stocks, for which price should be extracted
    :return: list of price dictionaries
    """
    stock_list = []
    for isin in isin_list:
        r = requests.get(url_justetf(isin))
        assert r.status_code == 200, "HTTP Error, {}".format(r.status_code)

        html = r.content.decode("utf-8")
        soup = BeautifulSoup(html, 'html.parser')
        stock_dict = get_price_stock(soup)
        stock_dict["ISIN"] = isin
        stock_list.append(stock_dict)
    return (stock_list)


def get_master_data_stock(soup_base):
    """
    Extracts masterdata for each stock given by the BeautifulSoup object from justetf.com overpage.
    :param soup_base: BeautifulSoup object from justetf.com overview page
    :return: dictionary of masterdata key:value pairs
    """
    assert isinstance(soup_base, type(BeautifulSoup())), "Input is no BeautifulSoup object!"
    metadata = {}
    ### Get name of stock
    stock_name = soup_base.find_all("h1")[0].find_all("span", {"class": "h1"})[0].text
    metadata["Name"] = stock_name
    ### Get metadata from infoboxes: Fondssize, TER
    infoboxes = soup_base.find_all("div", {"class": "infobox"})
    for box in infoboxes:
        try:
            value = box.find_all("div", {"class": "val"})[0].text.replace(" ", "").replace("\n", "")
            label = box.find_all("div", {"class": "vallabel"})[0].text.replace(" ", "").replace("\n", "")
        except IndexError:
            # IndexError: Box contains no div objects with classes val or label --> skip these boxes
            continue
        if label == "Fondsgröße":
            assert value[:3] == "EUR", "Fondsgröße not given in EUR!"
            assert value[-4:] == "Mio.", "Fondsgröße not given in Mio EUR!"
            metadata["Fondssize"] = int(float(value[3:-4]) * 10 ** 6)
        elif label == "Gesamtkostenquote(TER)":
            assert value[-4:] == "p.a.", "TER not given per year!"
            metadata["TER%"] = float(value[:-5].replace(".", "").replace(",", "."))
    ### Get metadata from tables
    tables = soup_base.find_all("table")
    needed_labels = ["Replikationsmethode", "RechtlicheStruktur", "Fondswährung", "Auflagedatum/Handelsbeginn",
                     "Ausschüttung", "Ausschüttungsintervall", "Fondsdomizil", "Fondsstruktur", "Anbieter",
                     "Depotbank", "Wirtschaftsprüfer"]
    for table in tables:
        bodies = table.find_all("tbody")
        for body in bodies:
            rows = body.find_all("tr")
            for row in rows:
                if len(row.find_all("td")) == 2:
                    label = row.find_all("td")[0].text.replace(" ", "").replace("\n", "")
                    value = row.find_all("td")[1].text.replace(" ", "").replace("\n", "")
                    if label in needed_labels:
                        metadata[label] = value
    return (metadata)


def get_master_data(isin_list):
    """
    Extracts all masterdata for all stocks in isin_list from justetf.com.
    :param isin_list: List of ISINs for which master data should be extracted.
    :return: list of dictionaries of master data
    """
    stock_list = []
    for isin in isin_list:
        r = requests.get(url_justetf(isin))
        assert r.status_code == 200, "HTTP Error, {}".format(r.status_code)

        html = r.content.decode("utf-8")
        soup = BeautifulSoup(html, 'html.parser')
        stock_dict = get_master_data_stock(soup)
        stock_dict["ISIN"] = isin
        stock_list.append(stock_dict)
    return (stock_list)

def get_current_cryptocurrency_price(num_pages=5, currency="EUR") -> pd.DataFrame:
    """
    Scrape current price of cryptocurrencies from https://www.coinmarketcap.com/ and convert it to Euro.
    :param num_pages: Each page holds 100 cryptos with highest capitalization per default.
    :return: dataframe with Euro-price of cryptocurrency with name and symbol (ticker)
    """
    base_url = "https://www.coinmarketcap.com/"

    # website has several pages of 100 cryptos each
    for page in range(num_pages):
        url = base_url if page == 0 else base_url + "?page=" + str(page+1)
        r = requests.get(url)
        assert r.status_code == requests.codes.ok, f"Bad request to {url}!"
        html = r.content.decode("utf-8")
        soup = BeautifulSoup(html, 'html.parser')

        # Thx to  https://towardsdatascience.com/web-scraping-crypto-prices-with-python-41072ea5b5bf
        # for the tip of using the script part of the website:
        data = json.loads(soup.find("script", id="__NEXT_DATA__", type="application/json").contents[0])
        price_data = json.loads(data["props"]["initialState"])["cryptocurrency"]["listingLatest"]["data"]
        key_ordering = price_data[0]["keysArr"]
        price_array = price_data[1:]

        # Create a key-map used to parse the response-json
        key_map = {}
        keys_to_parse = {"name": "name",
                         "symbol": "symbol",
                         "quote.USD.price": "price",
                         "quote.USD.volume24h": "volume_24h",
                         "quote.USD.percentChange1h": "change_%_1h",
                         "quote.USD.percentChange24h": "change_%_24h",
                         "quote.USD.percentChange7d": "change_%_7d"
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
    if currency == "EUR":
        conversion_rate = conversion_rate_usDollar_euro(dollar_to_euro=True)
        df_prices["price"] = df_prices["price"]*conversion_rate
        df_prices["volume_24h"] = df_prices["volume_24h"] * conversion_rate
    return(df_prices)

def conversion_rate_usDollar_euro(dollar_to_euro=True) -> float:
    """
    Uses https://www.finanzen.net to convert US-dollars $ to Euro € and vice versa.
    :param dollar_to_euro: boolean flag, whether to convert dollars to euro
    :return: conversion rate
    """
    date_today = date.today().strftime(format="%Y-%m-%d")
    if dollar_to_euro == True:
        url = f"https://www.finanzen.net/ajax/currencyConverter_Exchangerate/USD/EUR/{date_today}"
    else:
        url = f"https://www.finanzen.net/ajax/currencyConverter_Exchangerate/EUR/USD/{date_today}"

    r = requests.post(url)
    assert r.status_code == requests.codes.ok, "Could not convert $ to €!"
    conversion = float(json.loads(r.content)[0])

    return(conversion)
