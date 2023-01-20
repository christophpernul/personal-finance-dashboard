import json
import logging
import requests
import pandas as pd
from datetime import date
from ..datahub_stocks.stocks_lib import parse_etf_prices, parse_etf_master_data

logger = logging.getLogger(__name__)


def extract_conversion_rate_usDollar_euro(dollar_to_euro=True) -> float:
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

    return conversion


def extract_etf_master_data(isin_list: list, source_url: str):
    """
    Extracts all masterdata for all stocks in isin_list from justetf.com.
    :param isin_list: List of ISINs for which master data should be extracted.
    :return: list of dictionaries of master data
    """
    stock_list = []
    for isin in isin_list:
        url = source_url + f"?query={isin}&groupField=index&from=search&isin={isin}#overview"
        r = requests.get(url)
        assert r.status_code == 200, "EXTRACT: JUST-ETF: HTTP Error, {}".format(r.status_code)

        html = r.content.decode("utf-8")
        stock_dict = parse_etf_master_data(html)
        stock_dict["ISIN"] = isin
        stock_list.append(stock_dict)
    assert len(stock_list) == len(
        isin_list), "EXTRACT: Extract stock master data from justetf was not possible for all stocks!"
    return pd.DataFrame(stock_list)


def extract_etf_price_data(isin_list: list, source_url: str):
    """
    Iterate through list of ISINs and call justetf.com overview page for each stock and extract price informations.
    :param isin_list: list of ISINs for all stocks, for which price should be extracted
    :param source_url:
    :return: list of price dictionaries
    """
    stock_list = []
    for isin in isin_list:
        url = source_url + f"?query={isin}&groupField=index&from=search&isin={isin}#overview"
        r = requests.get(url)
        assert r.status_code == 200, "HTTP Error, {}".format(r.status_code)

        html = r.content.decode("utf-8")
        stock_dict = parse_etf_prices(html)
        stock_dict["ISIN"] = isin
        stock_list.append(stock_dict)
    assert len(stock_list) == len(isin_list), "EXTRACT: Extract stock price data from justetf was not possible for all stocks!"
    return pd.DataFrame(stock_list)