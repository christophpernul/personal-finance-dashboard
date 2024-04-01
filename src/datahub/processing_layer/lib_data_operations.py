import pandas as pd
import yfinance as yf

from utils.datacleaning import clean


def fetch_prices(etfs: list) -> pd.DataFrame:
    """Extracts historic price data for relevant etfs."""
    prices = pd.DataFrame(columns=["isin", "Date", "Close"])
    for isin in etfs:
        try:
            price_isin = yf.Ticker(isin).history(period="1d")
            price_isin["isin"] = isin
        except:
            print(f"Cannot find price data for `{isin}` via yahoo finance!")
            continue
        prices = pd.concat(
            [prices, price_isin[["isin", "Close"]].reset_index()],
            ignore_index=True,
        )
    # Returned dataframe from yahoo contains columns Close, and Date after resetting index
    prices.rename(
        columns={
            "Close": "price",
            "Date": "date",
        },
        inplace=True,
    )
    return prices


def preprocess_orders(orders: pd.DataFrame) -> pd.DataFrame:
    """Select necessary columns, clean data and provide positive amount and costs."""
    orders_out = orders.copy()

    # Keep valid orders
    orders_out = orders_out[~orders_out["amount"].isna()]
    orders_out = orders_out[orders_out["type"] == "ETF Sparplan"]
    orders_out = orders_out[~orders_out["date"].isna()]

    # Select necessary columns
    necessary_columns = [
        "depot",
        "type",
        "amount",
        "date",
        "isin",
        "index",
        "cost",
        "price",
        "name",
    ]
    assert set(orders_out.columns).intersection(set(necessary_columns)) == set(
        necessary_columns
    ), "Some necessary columns are missing in the input dataframe!"
    orders_out = orders_out[necessary_columns]

    # Data cleaning and data type conversion
    orders_out = clean(
        data=orders_out,
        strip_columns=[
            "date",
            "type",
            "depot",
            "name",
            "isin",
        ],
    )
    orders_out["date"] = pd.to_datetime(orders_out["date"], format="%d.%m.%Y")
    orders_out["index"] = orders_out["index"].astype(int)

    # Preprocess
    assert (
        orders_out[orders_out["amount"] > 0.0].count() != 0
    ).any() == False, "There should be no positive values in amount column!"
    orders_out["amount"] = -orders_out["amount"]
    orders_out["cost"] = -orders_out["cost"]

    return orders_out


def preprocess_etf_masterdata(master_data: pd.DataFrame) -> pd.DataFrame:
    """
    Selects necessary columns, cleans data and performs preprocessing:
    - Convert ter to float
    """
    master_data_out = master_data.copy()

    necessary_columns = [
        "isin",
        "name",
        "symbol",
        "type",
        "currency",
        "distribution",
        "replication",
        "ter",
        "region",
        "etf_type",
    ]
    # Select necessary columns
    assert set(master_data_out.columns).intersection(
        set(necessary_columns)
    ) == set(
        necessary_columns
    ), "Some necessary columns are missing in the input dataframe!"
    master_data_out = master_data_out[necessary_columns]

    # Data Cleaning & Preprocessing
    clean(data=master_data_out, strip_columns=list(master_data_out.columns))

    master_data_out["ter"] = (
        master_data_out["ter"].str.replace(",", ".").astype(float)
    )

    return master_data_out


# def compute_crypto_portfolio_value(portfolio: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
#     """
#     Combines current crypto-price data with portfolio and computes value per exchange/currency.
#     Adds the overall portfolio value with exchange-name "Overall" to the data.
#     :param portfolio: Holds crypto portfolio data (exchange, currency, amount)
#     :param prices: Holds prices and masterdata of cryptos (name, symbol, price)
#     :return: Value of portfolio per cryptocurrency
#     """
#
#     portfolio_all = portfolio.merge(prices, left_on="currency", right_on="symbol").copy()
#     portfolio_all = portfolio_all[["exchange", "currency", "name", "amount", "price"]]
#
#     portfolio_all.loc[:, "value"] = round(portfolio_all["amount"] * portfolio_all["price"], 2)
#     portfolio_all = portfolio_all.drop("price", axis=1)
#
#     portfolio_all = portfolio_all.groupby(["exchange", "currency", "name"]).sum().reset_index()
#
#     portfolio_overall = portfolio_all.groupby(["currency", "name"]).sum().reset_index()
#     portfolio_overall["exchange"] = "Overall"
#
#     portfolio_value = portfolio_all.append(portfolio_overall, ignore_index=True, sort=False)
#
#     return(portfolio_value)
#
#
def enrich_orders(orders, master_data):
    """Enrich ETF orders with master data."""
    # Drop columns that occur in master_data too
    orders_temp = orders.copy().drop(
        columns=[
            "name",
            "type",
        ],
        axis=1,
    )

    join_columns_master = [
        "isin",
        "name",
        "type",
        "etf_type",
        "region",
        "replication",
        "distribution",
        "ter",
    ]
    orders_temp = orders_temp.merge(
        master_data[join_columns_master].drop_duplicates(),
        how="inner",
        left_on="isin",
        right_on="isin",
    )
    orders_temp["cost_per_year"] = (
        12 * orders_temp["amount"] * orders_temp["ter"] / 100
    )

    assert (
        orders_temp[orders_temp[join_columns_master].isna()][["isin", "name"]]
        .drop_duplicates()
        .count()
        > 0
    ).any() == False, "No ETF master data!"
    return orders_temp


def get_current_portfolio(orders: pd.DataFrame) -> pd.DataFrame:
    """Gets transactions of latest executed monthly savings plan of ETF portfolio."""
    portfolio = orders.copy()
    last_execution_index = portfolio["index"].max()
    portfolio = (
        portfolio[portfolio["index"] == last_execution_index]
        .reset_index(drop=True)
        .drop("index", axis=1)
    )
    return portfolio


def compute_percentage_per_group(
    current_portfolio: pd.DataFrame,
    group_names: list,
    compute_columns: list,
    agg_functions: list,
) -> list:
    """
    Computes len(group_names) aggregations of input dataframe df according to the given agg_functions wrt to the
    specified columns in compute_columns.
    These three lists need to have the same length!
    Currently only sum() as aggregate function is available.
    :param current_portfolio: pd.DataFrame, that needs to have all columns specified in group_names, compute_columns
    :param group_names: list of grouping columns
    :param compute_columns: list of columns along which groupby computation should be done
    :param agg_functions: list of aggregate functions, which are applied to compute_columns
    :return result_list: list of resulting dataframes after groupby aggregation
    """
    all_columns = set(current_portfolio.columns)
    all_needed_columns = set(group_names).union(set(compute_columns))
    assert (
        all_columns.intersection(all_needed_columns) == all_needed_columns
    ), "Columns not present in current portfolio to calculate aggregation per group!"
    assert len(group_names) == len(
        compute_columns
    ), "Number of grouping columns does not match compute columns!"
    assert len(group_names) == len(
        agg_functions
    ), "Number of grouping columns does not match number of aggregate functions!"

    portfolio_temp = current_portfolio.copy()
    result_list = []
    for idx, group in enumerate(group_names):
        compute_col = compute_columns[idx]
        agg_func = agg_functions[idx]
        if agg_func == "sum":
            df_grouped = (
                portfolio_temp[[group, compute_col]].groupby([group]).sum()
            )
        else:
            raise NotImplemented(
                f"Other aggregation functions than `sum()` are not implemented yet!"
            )
        total_sum = portfolio_temp[compute_col].sum()
        df_grouped["percentage"] = (
            round(df_grouped[compute_col] / total_sum, 3) * 100
        )
        result_list.append(df_grouped.reset_index())

    return result_list


def get_portfolio_value(
    orders_enriched: pd.DataFrame, prices: pd.DataFrame
) -> pd.DataFrame:
    """
    Computes the current value of each stock given in the `orders_enriched` by using most recent price data.
    :param orders_enriched: dataframe containing all portfolio orders
    :param prices: dataframe containing current price data
    :return:
    """
    if (orders_enriched.isna().sum() > 0).any():
        print(
            "Some entries contain NaN values! The statistics might be wrong!"
        )
        print(orders_enriched.isna().sum())
    needed_columns_trx = set(["amount", "price", "isin"])
    needed_columns_prices = set(["price", "isin"])
    assert (
        needed_columns_trx.intersection(set(orders_enriched.columns))
        == needed_columns_trx
    ), "One of the following columns are missing in df_trx: {}".format(
        needed_columns_trx
    )
    assert (
        needed_columns_prices.intersection(set(prices.columns))
        == needed_columns_prices
    ), "One of the following columns are missing in df_prices: {}".format(
        needed_columns_prices
    )
    orders_temp = orders_enriched.copy()
    prices_temp = prices.copy()

    ### Compute amount of stocks bought
    orders_temp["shares"] = orders_temp["amount"] / orders_temp["price"]
    ### Drop price of orderdata, which is the price at which a stock was bought --> here we use the current price
    orders_temp = orders_temp.drop("price", axis=1)

    orders_priced = orders_temp.merge(
        prices_temp,
        how="left",
        left_on="isin",
        right_on="isin",
        suffixes=["", "_y"],
    ).rename(columns={"date_y": "last_price_update"})
    # TODO: Check what happens if we keep NaNs in here in case prices could not have been retrieved
    # assert (
    #     orders_priced["price"].isna().sum() > 0
    # ).any() == False, "Prices are missing for a transaction!"
    orders_priced["value"] = round(
        orders_priced["shares"] * orders_priced["price"], 2
    )

    return orders_priced


def filter_portfolio_date(
    portfolio: pd.DataFrame, offset_months: int
) -> pd.DataFrame:
    """
    Filters the dataframe, portfolio, to all entries that occur after today's date minus offset_months.
    :param portfolio: Needs column Date
    :param offset_months: Offset of how many months into the past the output of the dataframe should contain.
    :return: dataframe filtered up to offset_months into the past
    """
    from datetime import date

    assert (
        "date" in portfolio.columns
    ), 'Column "date" is missing in input dataframe!'

    date_today = pd.Timestamp(date.today())
    if offset_months == -1:
        return portfolio
    else:
        date_offset = pd.DateOffset(months=offset_months)
        portfolio_date_filtered = portfolio[
            portfolio["date"] >= date_today - date_offset
        ]
        return portfolio_date_filtered


# def filter_portfolio_stock(portfolio: pd.DataFrame, stock_name: str) -> pd.DataFrame:
#     """
#     Filters the dataframe, portfolio, to the given stock_name.
#     :param portfolio: Dataframe holding transactions
#     :param stock_name: Name of the stock, to which the dataframe should be filtered.
#     :return: dataframe filtered on the specified stock name
#     """
#     assert "name" in portfolio.columns, 'Column "name" is missing in input dataframe!'
#     return(portfolio[portfolio["name"] == stock_name])
#
# def prepare_orderAmounts_prices(orders: pd.DataFrame):
#     """
#     Extracts a dataframe of buy-prices for each stock at each date. Additionally prepare order-dataframe
#     with amount of stocks at each date.
#     :param orders: Holds price and investmentamount data for each stock at every date.
#     :return: Tuple of orders (including amount of stocks) and prices.
#     """
#     prices = orders[["date", "name", "Price"]]
#     necessary_columns = ["date", "name", "Investment", "Ordercost", "shares"]
#     df_orders = orders.drop_duplicates().copy()
#     df_orders["shares"] = df_orders["Investment"] / df_orders["Price"]
#     df_orders = df_orders[necessary_columns]
#     return((df_orders, prices))


def prepare_timeseries(orders: pd.DataFrame):
    """
    Computes timeseries chart (value/investment vs date) for all stocks in the portfolio.
    Computes timeseries chart for overall portfolio (sum of all stock values at given date) and adds it
    to the dataframe.
    :param orders: dataframe, containing Investmentamount, ordercost and price for each stock per transactiondate
    :return:
    """
    necessary_columns = ["date", "name", "amount", "price", "cost"]
    assert set(orders.columns).intersection(set(necessary_columns)) == set(
        necessary_columns
    ), "Necessary columns missing in order data for timeseries preparation!"
    orders["shares"] = orders["amount"] / orders["price"]
    ### Map each transaction-date to the beginning of the month for easier comparison
    orders["date"] = orders["date"].apply(
        lambda date: pd.offsets.MonthBegin().rollback(date)
    )

    ### Prepare master data of all stocks and dates in order history
    ### TODO: Refine all data preprocessing to just once define master data for all needed tasks
    all_stocks = pd.DataFrame(orders["name"].drop_duplicates()).copy()
    all_stocks["key"] = 0
    all_dates = pd.DataFrame(orders["date"].drop_duplicates()).copy()
    all_dates["key"] = 0
    all_combinations = pd.merge(all_dates, all_stocks, on="key").drop(
        "key", axis=1
    )

    ### Prepare dataframe, that gets converted to a timeseries, it has entries of all stocks, that were
    ### bought in the past at each transaction-date (stock data for stocks, which were not bought at that date,
    ### is filled with 0 to enable correct computation of cumsum()
    group_columns = ["amount", "cost", "shares"]
    df_init = (
        all_combinations.merge(
            orders[["date", "name"] + group_columns],
            how="left",
            left_on=["date", "name"],
            right_on=["date", "name"],
        )
        .fillna(0)
        .copy()
    )
    price_lookup = orders[["date", "name", "price"]].copy()

    ### Compute cumsum() per stockgroup and rejoin date
    df_grouped = (
        df_init.sort_values("date").groupby("name")[group_columns].cumsum()
    )
    df_grouped_all = df_init.merge(
        df_grouped,
        how="left",
        left_index=True,
        right_index=True,
        suffixes=["_init", None],
    )
    df_grouped_all = df_grouped_all.drop(
        ["amount_init", "cost_init", "shares_init"], axis=1
    )
    ### Rejoin prices and compute values for each stock at each date, fill values of stocks, which were not
    ### bought at that date again with 0s
    df_grouped_all = df_grouped_all.merge(
        price_lookup,
        how="left",
        left_on=["date", "name"],
        right_on=["date", "name"],
        suffixes=[None, "_y"],
    )
    df_grouped_all["value"] = (
        df_grouped_all["shares"] * df_grouped_all["price"]
    )
    df_grouped_all = df_grouped_all.drop(
        ["shares", "price"], axis=1
    )  # .fillna(0)

    ### Finally sum over stock values at each date to arrive at timeseries format
    df_overall = (
        df_grouped_all.sort_values("date")
        .set_index("date")
        .drop(["name"], axis=1)
        .groupby("date")
        .sum()
        .reset_index()
    )
    df_overall["name"] = "Overall Portfolio"
    df_timeseries = pd.concat(
        [df_grouped_all, df_overall], ignore_index=True, sort=False
    )
    return df_timeseries
