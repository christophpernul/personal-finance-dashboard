import lib_finance as fdlib
import pandas as pd
import os

base_path = "/home/chris/Dropbox/Finance/data/"
fname_isin_full = "ETF_investing.ods"
fname_regionMapping = "ETF_regionTypes.ods"
fname_isin_needed = "finanzübersicht.ods"
fname_master_data = "master_data_stocks.ods"
fname_price_data = "stock_prices.ods"

df_etfs = pd.read_excel(base_path+fname_isin_full, engine="odf", sheet_name="ETF list")
isin_list_full = list(df_etfs["ISIN"].drop_duplicates())
print("Length of full ISIN list = ", len(isin_list_full))

dfn = pd.read_excel(base_path+fname_isin_needed, engine="odf", sheet_name="3.2 Portfolio langfristig Transactions")
isin_list = list(dfn["ISIN"].dropna().drop_duplicates())
print("Length of ISIN list = ", len(isin_list))

if fname_master_data in os.listdir(base_path):
    df_master = pd.read_csv(base_path+fname_master_data)
else:
    df_master = None
if fname_regionMapping in os.listdir(base_path):
    df_regions = pd.read_excel(base_path+fname_regionMapping, engine="odf")
else:
    df_regions = None
if fname_price_data in os.listdir(base_path):
    df_price = pd.read_csv(base_path+fname_price_data)
else:
    df_price = None

print("Extract stock masterdata from justetf.com!")
stock_dict = fdlib.get_master_data(isin_list_full)
master = pd.DataFrame(stock_dict)
assert master.count()[0] == len(isin_list_full), "Too less rows!"
if ~isinstance(df_regions, type(None)):
    print("Join region types to ETF master data!")
    master = master.merge(df_regions, how="left", left_on="ISIN", right_on="ISIN").drop("Name_y", axis=1)\
                    .rename(columns={"Name_x": "Name"})
print("Write master data to file!")
master.to_csv(base_path+fname_master_data, index=False)

print("Extract stock prices from justetf.com!")
price_dict = fdlib.get_prices(isin_list)
prices = pd.DataFrame(price_dict)
assert prices.count()[0] == len(isin_list), "Too less rows!"
print("Write price data to file!")
if isinstance(df_price, type(None)):
    prices.to_csv(base_path+fname_price_data, index=False)
else:
    print("Price data already exists!")
    overlap = df_price.merge(prices, left_on="Datum", right_on="Datum", how="inner")
    assert overlap.count()[0] == 0, "Price data for this date already exists!"
    df_price_new = df_price.append(prices, ignore_index=True)
    assert df_price_new.count()[0] == df_price.count()[0] + prices.count()[0], "Appending prices failed!"
    df_price_new.to_csv(base_path+fname_price_data, index=False)
