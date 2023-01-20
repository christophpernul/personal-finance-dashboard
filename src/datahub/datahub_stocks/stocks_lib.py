from bs4 import BeautifulSoup
from datetime import date



def parse_etf_master_data(html: str):
    """
    Extracts masterdata for each stock given by the BeautifulSoup object from justetf.com overpage.
    :param soup_base: HTML object from justetf.com overview page
    :return: dictionary of masterdata key:value pairs
    """
    soup_base = BeautifulSoup(html, 'html.parser')
    assert isinstance(soup_base, type(BeautifulSoup())), "EXTRACT: Input is no BeautifulSoup object!"
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
    return metadata


def parse_etf_prices(html: str):
    """
    Extracts price information from BeautifulSoup object created from HTML of justetf.com overview page.
    :param html: HTML of justetf.com overview page
    :return: dictionary with price, currency, Datum keys
    """
    soup_base = BeautifulSoup(html, 'html.parser')
    assert isinstance(soup_base, type(BeautifulSoup())), "Input is no BeautifulSoup object!"
    price_dict = {}

    price_obj = soup_base.find_all("div", {"class": "infobox"})[0].find_all("div", {"class": "val"})[0].find_all("span")
    currency = price_obj[0].text
    price = float(price_obj[1].text.replace(".", "").replace(",", "."))

    price_dict["Currency"] = currency
    price_dict["Price"] = price
    price_dict["Date"] = date.today().strftime("%d.%m.%Y")

    return price_dict