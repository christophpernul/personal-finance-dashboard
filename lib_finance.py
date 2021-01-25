import requests
import os
from bs4 import BeautifulSoup
from datetime import date

def update_cashflow_data():
    """
    Loads all existing raw files of cashflow per month, appends them and saves them in a single csv.
    :return:
    """
    import pandas as pd
    base_path = "/home/chris/Dropbox/Finance/data/data_cashflow/"
    raw_data_path = os.path.join(base_path, "raw/")
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
        value = box.find_all("div", {"class": "val"})[0].text.replace(" ", "").replace("\n", "")
        label = box.find_all("div", {"class": "vallabel"})[0].text.replace(" ", "").replace("\n", "")
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