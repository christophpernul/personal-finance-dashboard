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

    dfp["Date"] = pd.to_datetime(dfp["Date"], format="%d.%m.%Y")
    latest_date = dfp["Date"].max()
    df_current_prices = dfp[dfp["Date"] == latest_date].reset_index(drop=True)
    return(df_current_prices)


def preprocess_orders(df_orders: pd.DataFrame) -> pd.DataFrame:
    """
    Set datatypes of columns and split input into dividends transactions and savings-plan transactions.
    :param df_orders: Includes all transaction data of the portfolio, all columns in list portfolio_columns
                        need to be present, Kommentar column needs to be either "monatlich" (transaction of the
                        savings plan, an ETF is bought) or "Dividende" (income)
    :return: tuple of orders- and dividend transaction entries
    """
    orders_portfolio = df_orders.copy()
    expected_comments = ['monatlich', 'Dividende']
    portfolio_columns = ["Index", "Datum", "Kurs", "Betrag", "Kosten", "Anbieter", "Name", "ISIN"]
    new_portfolio_columns = ["Index", "Date", "Price", "Investment", "Ordercost", "Depotprovider", "Name", "ISIN"]
    rename_columns = {key: value for key, value in zip(portfolio_columns, new_portfolio_columns)}

    orders_portfolio = orders_portfolio.rename(columns=rename_columns)

    assert set(orders_portfolio.columns).intersection(set(new_portfolio_columns)) == set(new_portfolio_columns), \
            "Some necessary columns are missing in the input dataframe!"
    assert orders_portfolio["Art"].dropna().drop_duplicates().count() == 1, "Mehrere Arten von Investments!"
    assert orders_portfolio["Art"].dropna().drop_duplicates()[0] == "ETF Sparplan", "Falsche Investmentart!"

    ### Keep only valid entries
    orders_portfolio = orders_portfolio[~orders_portfolio["Investment"].isna()]

    assert set(orders_portfolio["Kommentar"].drop_duplicates()).difference(set(expected_comments)) == set(), \
        "Unerwartete Kommentare enthalten! Erwartet: {}".format(expected_comments)

    dividends_portfolio = orders_portfolio[orders_portfolio["Kommentar"] == "Dividende"]
    orders_portfolio = orders_portfolio[orders_portfolio["Kommentar"] == "monatlich"]

    orders_portfolio = orders_portfolio[new_portfolio_columns]
    orders_portfolio = orders_portfolio[~orders_portfolio["Date"].isna()]
    orders_portfolio["Date"] = pd.to_datetime(orders_portfolio["Date"], format="%d.%m.%Y")
    orders_portfolio["Index"] = orders_portfolio["Index"].astype(int)

    assert (orders_portfolio[orders_portfolio["Investment"] > 0.].count() != 0).any() == False, \
        "Positive Einträge im Orderportfolio!"
    orders_portfolio["Investment"] = -orders_portfolio["Investment"]
    orders_portfolio["Ordercost"] = -orders_portfolio["Ordercost"]

    return ((orders_portfolio, dividends_portfolio))


def preprocess_etf_masterdata(df_master: pd.DataFrame) -> pd.DataFrame:
    """
    Convert columns "physical" and "Acc" to booleans and map all entries in "Region" containing "Emerging" to "Emerging"
    :param df_master: Master data of all ETFs, columns in etf_columns are required
    :return: preprocessed dataframe
    """
    etf_master = df_master.copy()
    etf_columns = ["Type", "Name", "ISIN", "Region", "Replikationsmethode", "Ausschüttung", "TER%"]
    new_etf_columns = ["Type", "Name", "ISIN", "Region", "Replicationmethod", "Distributing", "TER%"]
    etf_master = etf_master.rename(columns={key: value for key, value in zip(etf_columns, new_etf_columns)})

    assert set(etf_master.columns).intersection(set(new_etf_columns)) == set(new_etf_columns), \
        "Some necessary columns are missing in the input dataframe!"

    etf_master = etf_master[new_etf_columns]

    etf_master["Replicationmethod"] = etf_master["Replicationmethod"].map(lambda x: "Physical" \
                                                                            if x[:8] == "Physisch" else "Synthetic")
    etf_master["Distributing"] = etf_master["Distributing"].map(lambda x: "Distributing" \
        if x == "Ausschüttend" else "Accumulating")
    etf_master["Region"] = etf_master["Region"].fillna("").map(lambda x: "Emerging" if "Emerging" in x else x)
    return (etf_master)


def enrich_orders(df_orders, df_etf):
    """
    Join ETF master data to transaction data of ETFs.
    :param df_orders: ETF transaction data
    :param df_etf: ETF master data
    :return:
    """
    join_columns_etf_master = ["ISIN", "Type", "Region", "Replicationmethod", "Distributing", "TER%"]
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
    needed_columns_trx = set(["Investment", "Price", "ISIN"])
    needed_columns_prices = set(["Price", "ISIN"])
    assert needed_columns_trx.intersection(set(df_trx.columns)) == needed_columns_trx, \
            "One of the following columns are missing in df_trx: {}".format(needed_columns_trx)
    assert needed_columns_prices.intersection(set(df_prices.columns)) == needed_columns_prices, \
        "One of the following columns are missing in df_prices: {}".format(needed_columns_prices)
    df = df_trx.copy()
    dfp = df_prices.copy()

    ### Compute amount of stocks bought
    df["Amount"] = df["Investment"] / df["Price"]
    ### Drop price of orderdata, which is the price at which a stock was bought --> here we use the current price
    df = df.drop("Price", axis=1)

    df_portfolio = df.merge(dfp, how="left", left_on="ISIN", right_on="ISIN", suffixes=["", "_y"])\
                        .rename(columns={"Date_y": "last_price_update"})
    assert (df_portfolio["Price"].isna().sum()>0).any() == False, "Prices are missing for a transaction!"
    df_portfolio["Value"] = round(df_portfolio["Amount"] * df_portfolio["Price"], 2)

    return (df_portfolio)

def filter_portfolio_date(portfolio: pd.DataFrame, offset_months: int) -> pd.DataFrame:
    """
    Filters the dataframe, portfolio, to all entries that occur after today's date minus offset_months.
    :param portfolio: Needs column Date
    :param offset_months: Offset of how many months into the past the output of the dataframe should contain.
    :return: dataframe filtered up to offset_months into the past
    """
    from datetime import date

    assert "Date" in portfolio.columns, 'Column "Date" is missing in input dataframe!'

    date_today = pd.Timestamp(date.today())
    if offset_months == -1:
        return(portfolio)
    else:
        date_offset = pd.DateOffset(months=offset_months)
        portfolio_date_filtered = portfolio[portfolio["Date"] >= date_today - date_offset]
        return(portfolio_date_filtered)

def filter_portfolio_stock(portfolio: pd.DataFrame, stock_name: str) -> pd.DataFrame:
    """
    Filters the dataframe, portfolio, to the given stock_name.
    :param portfolio: Dataframe holding transactions
    :param stock_name: Name of the stock, to which the dataframe should be filtered.
    :return: dataframe filtered on the specified stock name
    """
    assert "Name" in portfolio.columns, 'Column "Name" is missing in input dataframe!'
    return(portfolio[portfolio["Name"] == stock_name])

def prepare_orderAmounts_prices(orders: pd.DataFrame):
    """
    Extracts a dataframe of buy-prices for each stock at each date. Additionally prepare order-dataframe
    with amount of stocks at each date.
    :param orders: Holds price and investmentamount data for each stock at every date.
    :return: Tuple of orders (including amount of stocks) and prices.
    """
    prices = orders[["Date", "Name", "Price"]]
    necessary_columns = ["Date", "Name", "Investment", "Ordercost", "Amount"]
    df_orders = orders.drop_duplicates().copy()
    df_orders["Amount"] = df_orders["Investment"] / df_orders["Price"]
    df_orders = df_orders[necessary_columns]
    return((df_orders, prices))


def prepare_timeseries(orders: pd.DataFrame):
    """
    Computes timeseries chart (value/investment vs date) for all stocks in the portfolio.
    Computes timeseries chart for overall portfolio (sum of all stock values at given date) and adds it
    to the dataframe.
    :param orders: dataframe, containing Investmentamount, ordercost and price for each stock per transactiondate
    :return:
    """
    necessary_columns = ["Date", "Name", "Investment", "Price", "Ordercost"]
    assert set(orders.columns).intersection(set(necessary_columns)) == set(necessary_columns), \
        "Necessary columns missing in order data for timeseries preparation!"
    orders["Amount"] = orders["Investment"]/orders["Price"]
    ### Map each transaction-date to the beginning of the month for easier comparison
    orders["Date"] = orders["Date"] - pd.offsets.MonthBegin(1)

    ### Prepare master data of all stocks and dates in order history
    ### TODO: Refine all data preprocessing to just once define master data for all needed tasks
    all_stocks = pd.DataFrame(orders["Name"].drop_duplicates()).copy()
    all_stocks["key"] = 0
    all_dates = pd.DataFrame(orders["Date"].drop_duplicates()).copy()
    all_dates["key"] = 0
    all_combinations = pd.merge(all_dates, all_stocks, on='key').drop("key", axis=1)

    ### Prepare dataframe, that gets converted to a timeseries, it has entries of all stocks, that were
    ### bought in the past at each transaction-date (stock data for stocks, which were not bought at that date,
    ### is filled with 0 to enable correct computation of cumsum()
    group_columns = ["Investment", "Ordercost", "Amount"]
    df_init = all_combinations.merge(orders[["Date", "Name"] + group_columns], how="left",
                                     left_on=["Date", "Name"],
                                     right_on=["Date", "Name"]
                                     ).fillna(0).copy()
    price_lookup = orders[["Date", "Name", "Price"]].copy()

    ### Compute cumsum() per stockgroup and rejoin date
    df_grouped = df_init.sort_values("Date").groupby("Name").cumsum()
    df_grouped_all = df_init.merge(df_grouped, how="left",
                                   left_index=True,
                                   right_index=True,
                                   suffixes=["_init", None]
                                   )
    df_grouped_all = df_grouped_all.drop(["Investment_init", "Ordercost_init", "Amount_init"], axis=1)
    ### Rejoin prices and compute values for each stock at each date, fill values of stocks, which were not
    ### bought at that date again with 0s
    df_grouped_all = df_grouped_all.merge(price_lookup, how="left",
                                          left_on=["Date", "Name"],
                                          right_on=["Date", "Name"],
                                          suffixes=[None, "_y"]
                                          )
    df_grouped_all["Value"] = df_grouped_all["Amount"] * df_grouped_all["Price"]
    df_grouped_all = df_grouped_all.drop(["Amount", "Price"], axis=1)#.fillna(0)

    ### Finally sum over stock values at each date to arrive at timeseries format
    df_overall = df_grouped_all.sort_values("Date").set_index("Date")\
                                                        .drop(["Name"], axis=1)\
                                                        .groupby("Date").sum() \
                                                        .reset_index()
    df_overall["Name"] = "Overall Portfolio"
    df_timeseries = pd.concat([df_grouped_all, df_overall], ignore_index=True, sort=False)
    return(df_timeseries)

