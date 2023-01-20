import os
import json
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def load_json(file_path):
    with open(file_path, 'r') as json_file:
        return json.load(json_file)


def load_data(file_path, sheet_name=None, separator=";", force_csv=False):
    """
    Needs odfpy library to load .ods files!
    :param file_path:
    :return:
    """
    if file_path.endswith('.csv') or force_csv:
        return pd.read_csv(file_path,
                           sep=separator
                           )
    elif file_path.endswith('.ods') and not force_csv:
        df = pd.read_excel(file_path, sheet_name=sheet_name, engine='odf')
        if isinstance(df, dict):
            if len(df.keys()) > 1:
                logger.warning(f"Loaded file contains several sheets! First sheet is selected: {file_path}")
            return df[list(df.keys())[0]]
        else:
            return df


def save_data(data, file_path, separator=";"):
    assert isinstance(data, pd.DataFrame), f"UTILS: Can only save pd.DataFrame! Got type {type(data)}"
    data.to_csv(file_path,
                sep=separator,
                index=False,
                )
