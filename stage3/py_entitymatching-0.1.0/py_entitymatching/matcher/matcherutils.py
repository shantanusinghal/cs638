"""
This module contains some utility functions for the matcher.
"""
import logging
import math
import time
from collections import OrderedDict

import pandas as pd
import sklearn.cross_validation as cv
from  sklearn.preprocessing import Imputer

import py_entitymatching.catalog.catalog_manager as cm
import py_entitymatching.utils.catalog_helper as ch
import py_entitymatching.utils.generic_helper as gh

logger = logging.getLogger(__name__)


def split_train_test(labeled_data, train_proportion=0.5,
                     random_state=None, verbose=True):
    """
    This function splits the input data into train and test.

    Specifically, this function is just a wrapper of scikit-learn's
    train_test_split function.

    This function also takes care of copying the metadata from the input
    table to train and test splits.

    Args:
        labeled_data (DataFrame): The input pandas DataFrame that needs to be
            split into train and test.
        train_proportion (float): A number between 0 and 1, indicating the
            proportion of tuples that should be included in the train split (
            defaults to 0.5).
        random_state (object): A number of random number object (as in
            scikit-learn).
        verbose (boolean): A flag to indicate whether the debug information
            should be displayed.

    Returns:

        A Python dictionary containing two keys - train and test.

        The value for the key 'train' is a pandas DataFrame containing tuples
        allocated from the input table based on train_proportion.

        Similarly, the value for the key 'test' is a pandas DataFrame containing
        tuples for evaluation.

        This function sets the output DataFrames (train, test) properties
        same as the input DataFrame.

    """
    # Validate input parameters
    # # We expected labeled data to be of type pandas DataFrame
    if not isinstance(labeled_data, pd.DataFrame):
        logger.error('Input table is not of type DataFrame')
        raise AssertionError('Input table is not of type DataFrame')

    ch.log_info(logger, 'Required metadata: cand.set key, fk ltable, '
                        'fk rtable, '
                        'ltable, rtable, ltable key, rtable key', verbose)

    # # Get metadata
    key, fk_ltable, fk_rtable, ltable, rtable, l_key, r_key = \
        cm.get_metadata_for_candset(
            labeled_data,
            logger, verbose)

    # # Validate metadata
    cm._validate_metadata_for_candset(labeled_data, key, fk_ltable, fk_rtable,
                                      ltable, rtable, l_key, r_key,
                                      logger, verbose)

    num_rows = len(labeled_data)
    # We expect the train proportion to be between 0 and 1.
    assert train_proportion >= 0 and train_proportion <= 1, \
        " Train proportion is expected to be between 0 and 1"

    # We expect the number of rows in the table to be non-empty
    assert num_rows > 0, 'The input table is empty'

    # Explicitly get the train and test size in terms of tuples (based on the
    #  given proportion)
    train_size = int(math.floor(num_rows * train_proportion))
    test_size = int(num_rows - train_size)

    # Use sk-learn to split the data
    idx_values = pd.np.array(labeled_data.index.values)
    idx_train, idx_test = cv.train_test_split(idx_values, test_size=test_size,
                                              train_size=train_size,
                                              random_state=random_state)

    # Construct output tables.
    label_train = labeled_data.ix[idx_train]
    label_test = labeled_data.ix[idx_test]

    # Update catalog
    cm.init_properties(label_train)
    cm.copy_properties(labeled_data, label_train)

    cm.init_properties(label_test)
    cm.copy_properties(labeled_data, label_test)

    # Return output tables
    result = OrderedDict()
    result['train'] = label_train
    result['test'] = label_test

    # Finally, return the dictionary.
    return result


def get_ts():
    """
    This is a helper function, to generate a random string based on current
    time.
    """
    t = int(round(time.time() * 1e10))
    # Return the random string.
    return str(t)[::-1]


def impute_table(table, exclude_attrs=None, missing_val='NaN',
                 strategy='mean', axis=0, val_all_nans=0, verbose=True):
    """
    Impute table containing missing values.

    Args:
        table (DataFrame): DataFrame which values should be imputed.
        exclude_attrs (List) : list of attribute names to be excluded from
            imputing (defaults to None).
        missing_val (string or int):  The placeholder for the missing values.
            All occurrences of `missing_values` will be imputed.
            For missing values encoded as np.nan, use the string value 'NaN'
            (defaults to 'NaN').
        strategy (string): String that specifies on how to impute values. Valid
            strings: 'mean', 'median', 'most_frequent' (defaults to 'mean').
        axis (int):  axis=1 along rows, and axis=0 along columns  (defaults
            to 0).
        val_all_nans (float): Value to fill in if all the values in the column
            are NaN.

    Returns:
        Imputed DataFrame.


    Raises:
        AssertionError: If `table` is not of type pandas DataFrame.

    """
    # Validate input paramaters
    # # We expect the input table to be of type pandas DataFrame
    if not isinstance(table, pd.DataFrame):
        logger.error('Input table is not of type DataFrame')
        raise AssertionError('Input table is not of type DataFrame')

    ch.log_info(logger, 'Required metadata: cand.set key, fk ltable, '
                        'fk rtable, '
                        'ltable, rtable, ltable key, rtable key', verbose)

    # # Get metadata
    key, fk_ltable, fk_rtable, ltable, rtable, l_key, r_key = \
        cm.get_metadata_for_candset(
            table,
            logger, verbose)

    # # Validate metadata
    cm._validate_metadata_for_candset(table, key, fk_ltable, fk_rtable,
                                      ltable, rtable, l_key, r_key,
                                      logger, verbose)


    fv_columns = table.columns

    if exclude_attrs == None:
        feature_names = fv_columns

    else:

        # Check if the exclude attributes are present in the input table
        if not ch.check_attrs_present(table, exclude_attrs):
            logger.error('The attributes mentioned in exclude_attrs '
                         'is not present '
                         'in the input table')
            raise AssertionError(
                'The attributes mentioned in exclude_attrs '
                'is not present '
                'in the input table')
        # We expect exclude attributes to be of type list. If not convert it into
        #  a list.
        if not isinstance(exclude_attrs, list):
            exclude_attrs = [exclude_attrs]

        # Drop the duplicates from the exclude attributes
        exclude_attrs = gh.list_drop_duplicates(exclude_attrs)


        cols = [c not in exclude_attrs for c in fv_columns]
        feature_names = fv_columns[cols]
    # print feature_names
    table_copy = table.copy()
    projected_table = table_copy[feature_names]

    projected_table_values = projected_table.values

    imp = Imputer(missing_values=missing_val, strategy=strategy, axis=axis)
    imp.fit(projected_table_values)
    imp.statistics_[pd.np.isnan(imp.statistics_)] = val_all_nans
    projected_table_values = imp.transform(projected_table_values)
    table_copy[feature_names] = projected_table_values
    # Update catalog
    cm.init_properties(table_copy)
    cm.copy_properties(table, table_copy)

    return table_copy
