import pandas as pd

def load_data(order_data_absolute_path="/home/chris/Dropbox/Finance/data/finanzübersicht.ods",
              etf_master_data_absolute_path="/home/chris/Dropbox/Finance/data/master_data_stocks.ods",
              stock_price_data_absolute_path="/home/chris/Dropbox/Finance/data/stock_prices.ods",
              include_speculation=False):
    """
    Needs odfpy library to load .ods files!
    Loads all necessary data sources of the given portfolio: ETF savings portfolio data, speculation data
    (stocks, cryptos, etc).
    :param order_data__absolute_path: path to source data for ETF portfolio (filetype: .ods)
    :param etf_master_data_absolute_path: path to master data of ETFs (filetype: .ods)
    :param stock_price_data_absolute_path: path to price data of ETFs (filetype: .ods)
    :param include_speculation: Whether orders of speculation portfolio should be included in output
    :return: tupel of pd.DataFrames with portfolio transactions and master data
    """
    orders_portfolio = pd.read_excel(order_data_absolute_path, engine="odf",\
                                                                sheet_name="3.2 Portfolio langfristig Transactions")
    orders_speculation = pd.read_excel(order_data_absolute_path, engine="odf",\
                                                                sheet_name="3.3 Spekulation Transactions")

    income = pd.read_excel(order_data_absolute_path, engine="odf", sheet_name="3.3 Income Transactions")

    stock_prices = pd.read_csv(stock_price_data_absolute_path)

    etf_master = pd.read_csv(etf_master_data_absolute_path)

    if include_speculation == True:
        return ((etf_master, orders_portfolio, income, stock_prices, orders_speculation))
    else:
        return ((etf_master, orders_portfolio, income, stock_prices, None))

def preprocess_prices(df_prices: pd.DataFrame) -> pd.DataFrame:
    """
    Preprocessing of price dataframe. Get latest available price.
    :param df_prices: Needed columns: ISIN, Price, Datum, Currency
    :return: dataframe containing prices of stocks defined by ISIN on latest available date
    """
    dfp = df_prices.copy()
    assert dfp["Currency"].drop_duplicates().count() == 1, "Multiple currencies used for price data!"
    assert dfp["Currency"].iloc[0] == "EUR", "Currency is not Euro!"

    dfp["Datum"] = pd.to_datetime(dfp["Datum"], format="%d.%m.%Y")
    latest_date = dfp["Datum"].max()
    df_current_prices = dfp[dfp["Datum"] == latest_date].reset_index(drop=True)
    return(df_current_prices)


def preprocess_orders(df_orders: pd.DataFrame) -> pd.DataFrame:
    """
    Data cleaning (drop NaNs and rows with Kommentar = FAIL, which are wrong entries).
    Set datatypes of columns and split input into dividends transactions and savings-plan transactions.
    :param df_orders: Includes all transaction data of the portfolio, all columns in list portfolio_columns
                        need to be present, Kommentar column needs to be either "monatlich" (transaction of the
                        savings plan, an ETF is bought) or "Dividende" (income)
    :return: tuple of orders- and dividend transaction entries
    """
    orders_portfolio = df_orders.copy()
    expected_comments = ['monatlich', 'Dividende']
    portfolio_columns = ["Index", "Datum", "Kurs", "Betrag", "Kosten", "Anbieter", "Name", "ISIN"]

    assert set(orders_portfolio.columns).intersection(set(portfolio_columns)) == set(portfolio_columns), \
            "Some necessary columns are missing in the input dataframe!"
    assert orders_portfolio["Art"].dropna().drop_duplicates().count() == 1, "Mehrere Arten von Investments!"
    assert orders_portfolio["Art"].dropna().drop_duplicates()[0] == "ETF Sparplan", "Falsche Investmentart!"

    ### Keep only valid entries
    orders_portfolio = orders_portfolio[~orders_portfolio["Betrag"].isna()]
    ### Drop faulty entries where comment is empty
    orders_portfolio = orders_portfolio[orders_portfolio["Kommentar"] != "FAIL"]

    assert set(orders_portfolio["Kommentar"].drop_duplicates()).difference(set(expected_comments)) == set(), \
        "Unerwartete Kommentare enthalten! Erwartet: {}".format(expected_comments)

    dividends_portfolio = orders_portfolio[orders_portfolio["Kommentar"] == "Dividende"]
    orders_portfolio = orders_portfolio[orders_portfolio["Kommentar"] == "monatlich"]

    orders_portfolio = orders_portfolio[portfolio_columns]
    orders_portfolio = orders_portfolio[~orders_portfolio["Datum"].isna()]
    orders_portfolio["Datum"] = pd.to_datetime(orders_portfolio["Datum"], format="%d.%m.%Y")
    orders_portfolio["Index"] = orders_portfolio["Index"].astype(int)

    assert (orders_portfolio[orders_portfolio["Betrag"] > 0.].count() != 0).any() == False, \
        "Positive Einträge im Orderportfolio!"
    orders_portfolio["Betrag"] = -orders_portfolio["Betrag"]
    orders_portfolio["Kosten"] = -orders_portfolio["Kosten"]

    return ((orders_portfolio, dividends_portfolio))


def preprocess_etf_masterdata(df_master: pd.DataFrame) -> pd.DataFrame:
    """
    Convert columns "physical" and "Acc" to booleans and map all entries in "Region" containing "Emerging" to "Emerging"
    :param df_master: Master data of all ETFs, columns in etf_columns are required
    :return: preprocessed dataframe
    """
    etf_master = df_master.copy()
    etf_columns = ["Type", "Name", "ISIN", "Region", "Replikationsmethode", "Ausschüttung", "TER%"]

    assert set(etf_master.columns).intersection(set(etf_columns)) == set(etf_columns), \
        "Some necessary columns are missing in the input dataframe!"

    etf_master = etf_master[etf_columns]

    etf_master["Replikationsmethode"] = etf_master["Replikationsmethode"].map(lambda x: "Physisch" \
                                                                            if x[:8] == "Physisch" else "Synthetisch")
    etf_master["Region"] = etf_master["Region"].fillna("").map(lambda x: "Emerging" if "Emerging" in x else x)
    return (etf_master)


def enrich_orders(df_orders, df_etf):
    """
    Join ETF master data to transaction data of ETFs.
    :param df_orders: ETF transaction data
    :param df_etf: ETF master data
    :return:
    """
    join_columns_etf_master = ["ISIN", "Type", "Region", "Replikationsmethode", "Ausschüttung", "TER%"]
    orders_etf = df_orders.merge(df_etf[join_columns_etf_master].drop_duplicates(),
                                 how="inner",
                                 left_on="ISIN",
                                 right_on="ISIN").copy()

    assert (orders_etf[orders_etf["Region"].isna()][["ISIN", "Name"]].drop_duplicates().count() > 0).any() == False, \
        "No ETF master data!"
    return (orders_etf)


def get_current_portfolio(df_orders: pd.DataFrame) -> pd.DataFrame:
    """
    Gets transactions of latest executed monthly savings plan of ETF portfolio.
    :param df_orders: ETF transaction data
    :return:
    """
    portfolio = df_orders.copy()
    last_execution_index = portfolio["Index"].max()
    portfolio = portfolio[portfolio["Index"] == last_execution_index].reset_index(drop=True).drop("Index", axis=1)
    return (portfolio)


def compute_percentage_per_group(df: pd.DataFrame, group_names: list, compute_columns:list, agg_functions:list) -> list:
    """
    Computes len(group_names) aggregations of input dataframe df according to the given agg_functions wrt to the
    specified columns in compute_columns.
    These three lists need to have the same length!
    Currently only sum() as aggregate function is available.
    :param df: pd.DataFrame, that needs to have all columns specified in group_names, compute_columns
    :param group_names: list of grouping columns
    :param compute_columns: list of columns along which groupby computation should be done
    :param agg_functions: list of aggregate functions, which are applied to compute_columns
    :return result_list: list of resulting dataframes after groupby aggregation
    """
    all_columns = set(df.columns)
    all_needed_columns = set(group_names).union(set(compute_columns))
    assert all_columns.intersection(all_needed_columns) == all_needed_columns, "Columns not present!"
    assert len(group_names) == len(compute_columns), "Number of grouping columns does not match compute columns!"
    assert len(group_names) == len(
        agg_functions), "Number of grouping columns does not match number of aggregate functions!"

    df_copy = df.copy()
    result_list = []
    for idx, group in enumerate(group_names):
        compute_col = compute_columns[idx]
        agg_func = agg_functions[idx]
        if agg_func == "sum":
            df_grouped = df_copy[[group, compute_col]].groupby([group]).sum()
        total_sum = df_copy[compute_col].sum()
        df_grouped["Percentage"] = round(df_grouped[compute_col] / total_sum, 3) * 100
        result_list.append(df_grouped.reset_index())

    return (result_list)


def get_portfolio_value(df_trx: pd.DataFrame, df_prices: pd.DataFrame) -> pd.DataFrame:
    """
    Computes the current value of each stock given in the transaction list by using most recent price data.
    :param df_trx: dataframe containing all transactions
    :param df_prices: dataframe containing historic price data
    :return:
    """
    if (df_trx.isna().sum()>0).any():
        print("Some entries contain NaN values! The statistics might be wrong!")
        print(df_trx.isna().sum())
    needed_columns_trx = set(["Betrag", "Kurs", "ISIN"])
    needed_columns_prices = set(["Price", "ISIN"])
    assert needed_columns_trx.intersection(set(df_trx.columns)) == needed_columns_trx, \
            "One of the following columns are missing in df_trx: {}".format(needed_columns_trx)
    assert needed_columns_prices.intersection(set(df_prices.columns)) == needed_columns_prices, \
        "One of the following columns are missing in df_prices: {}".format(needed_columns_prices)
    df = df_trx.copy()
    dfp = df_prices.copy()

    ### Compute amount of stocks bought
    df["Stück"] = df["Betrag"] / df["Kurs"]

    df_portfolio = df.merge(dfp, how="left", left_on="ISIN", right_on="ISIN", suffixes=["", "_y"])\
                        .drop("Datum_y", axis=1)
    assert (df_portfolio["Price"].isna().sum()>0).any() == False, "Prices are missing for a transaction!"
    df_portfolio["Wert"] = df_portfolio["Stück"] * df_portfolio["Price"]

    return (df_portfolio)



