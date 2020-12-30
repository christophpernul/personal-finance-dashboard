import pandas as pd

def load_data(order_data__absolute_path="/home/chris/Dropbox/Finance/finanzübersicht.ods",
              etf_master_data_absolute_path="/home/chris/Dropbox/Finance/ETF_investing.ods",
              include_speculation=False):
    """
    Needs odfpy library to load .ods files!
    Loads all necessary data sources of the given portfolio: ETF savings portfolio data, speculation data
    (stocks, cryptos, etc).
    :param order_data__absolute_path: path to source data for ETF portfolio (filetype: .ods)
    :param etf_master_data_absolute_path: path to master data of ETFs (filetype: .ods)
    :param include_speculation: Whether orders of speculation portfolio should be included in output
    :return: tupel of pd.DataFrames with portfolio transactions and master data
    """
    orders_portfolio = pd.read_excel(order_data__absolute_path, engine="odf",\
                                                                sheet_name="3.2 Portfolio langfristig Transactions")
    orders_speculation = pd.read_excel(order_data__absolute_path, engine="odf",\
                                                                sheet_name="3.3 Spekulation Transactions")

    income = pd.read_excel(order_data__absolute_path, engine="odf", sheet_name="3.3 Income Transactions")

    etf_master = pd.read_excel(etf_master_data_absolute_path, engine="odf", sheet_name="ETF list")

    if include_speculation == True:
        return ((etf_master, orders_portfolio, income, orders_speculation))
    else:
        return ((etf_master, orders_portfolio, income, None))


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
    return ((orders_portfolio, dividends_portfolio))


def preprocess_etf_masterdata(df_master: pd.DataFrame) -> pd.DataFrame:
    """
    Convert columns "physical" and "Acc" to booleans and map all entries in "Region" containing "Emerging" to "Emerging"
    :param df_master: Master data of all ETFs, columns in etf_columns are required
    :return: preprocessed dataframe
    """
    etf_master = df_master.copy()
    etf_columns = ["Type", "Name", "ISIN", "Region", "physical", "Acc", "TER in %"]

    assert set(etf_master.columns).intersection(set(etf_columns)) == set(etf_columns), \
        "Some necessary columns are missing in the input dataframe!"

    etf_master = etf_master[etf_columns]

    etf_master["physical"] = etf_master["physical"].map(lambda x: True if x == "yes" else False)
    etf_master["Acc"] = etf_master["Acc"].map(lambda x: True if x == "yes" else False)
    etf_master["Region"] = etf_master["Region"].map(lambda x: "Emerging" if "Emerging" in x else x)
    etf_master = etf_master.rename(columns={"Acc": "accumulating"})
    return (etf_master)


def enrich_orders(df_orders, df_etf):
    """
    Join ETF master data to transaction data of ETFs.
    :param df_orders: ETF transaction data
    :param df_etf: ETF master data
    :return:
    """
    join_columns_etf_master = ["ISIN", "Type", "Region", "physical", "accumulating", "TER in %"]
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
    portfolio["total_execution_cost"] = portfolio["Betrag"].sum()
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