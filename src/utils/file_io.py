import os
import json
from pathlib import Path
import pandas as pd
from warnings import warn
import logging

logger = logging.getLogger(__name__)


def load_json(file_path):
    with open(file_path, "r") as json_file:
        return json.load(json_file)


def load_data(
    filepath: Path,
    used_library: str = "pandas",
    file_type: str = "csv",
    sheet_name: str = None,
) -> pd.DataFrame | None:
    """
    Loads data from given filepath and given file_extension
    Parameters
    ----------
    filepath: Path including filename and file extension
    used_library: Specifies the python library to load data

    Returns
    -------

    """
    implemented_libraries = "pandas"
    # TODO: Change filetype to excel instead of odf, add check that nothing else gets handed over
    allowed_file_types = ("csv", "odf")
    # if file_type == "csv":
    #     load_func = pd.read_csv
    # elif file_type == "odf":
    #     load_func = pd.read_excel
    # TODO: Add polars
    if used_library == "pandas" and file_type == "csv":
        return pd.read_csv(filepath_or_buffer=filepath)
    elif used_library == "pandas" and file_type == "excel":
        if not sheet_name:
            return pd.read_excel(filepath, engine="odf")
        else:
            return pd.read_excel(filepath, sheet_name=sheet_name, engine="odf")
    elif used_library != "pandas":
        warn(
            f"Provided library is not supported yet! Use one of the following: {''.join(implemented_libraries)}"
        )


def save_data(data, file_path, separator=";"):
    assert isinstance(
        data, pd.DataFrame
    ), f"UTILS: Can only save pd.DataFrame! Got type {type(data)}"
    data.to_csv(
        file_path,
        sep=separator,
        index=False,
    )
