import os
import pandas as pd


def update_cashflow_data():
    """
    Loads all existing raw files of cashflow per month, appends them and saves them in a single csv.
    :return:
    """
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
        print(
            "Bilanz " + filename[7:14] + ": Number of transactions = ",
            df.count()[0],
        )
    df_all.to_csv(base_path + out_filename + ".csv", index=False)
