"""
This module contains functions to extract features using a feature table.
"""
import logging

import pandas as pd
import pyprind


import py_entitymatching.catalog.catalog_manager as cm
import py_entitymatching.utils.catalog_helper as ch
import py_entitymatching.utils.generic_helper as gh

logger = logging.getLogger(__name__)


def extract_feature_vecs(candset, attrs_before=None, feature_table=None,
                         attrs_after=None, verbose=False,
                         show_progress=True):
    """
    This function extracts feature vectors from a DataFrame (typically a
    labeled candidate set).

    Specifically, this function uses feature
    table, ltable and rtable (that is present in the `candset`'s
    metadata) to extract feature vectors.

    Args:
        candset (DataFrame): The input candidate set for which the features
            vectors should be extracted.
        attrs_before (list): The list of attributes from the input candset,
            that should be added before the feature vectors (defaults to None).
        feature_table (DataFrame): A DataFrame containing a list of
            features that should be used to compute the feature vectors (
            defaults to None).
        attrs_after (list): The list of attributes from the input candset
            that should be added after the feature vectors (defaults to None).
        verbose (boolean): A flag to indicate whether the debug information
            should be displayed (defaults to False).
        show_progress (boolean): A flag to indicate whether the progress of
            extracting feature vectors must be displayed (defaults to True).


    Returns:
        A pandas DataFrame containing feature vectors.

        The DataFrame will have metadata ltable and rtable, pointing
        to the same ltable and rtable as the input candset.

        Also, the output
        DataFrame will have three columns: key, foreign key ltable, foreign
        key rtable copied from input candset to the output DataFrame. These
        three columns precede the columns mentioned in `attrs_before`.



    Raises:
        AssertionError: If `candset` is not of type pandas
            DataFrame.
        AssertionError: If `attrs_before` has attributes that
            are not present in the input candset.
        AssertionError: If `attrs_after` has attribtues that
            are not present in the input candset.
        AssertionError: If `feature_table` is set to None.

    """
    # Validate input parameters

    # # We expect the input candset to be of type pandas DataFrame.
    if not isinstance(candset, pd.DataFrame):
        logger.error('Input cand.set is not of type dataframe')
        raise AssertionError('Input cand.set is not of type dataframe')

    # # If the attrs_before is given, Check if the attrs_before are present in
    # the input candset
    if attrs_before != None:
        if not ch.check_attrs_present(candset, attrs_before):
            logger.error(
                'The attributes mentioned in attrs_before is not present '
                'in the input table')
            raise AssertionError(
                'The attributes mentioned in attrs_before is not present '
                'in the input table')

    # # If the attrs_after is given, Check if the attrs_after are present in
    # the input candset
    if attrs_after != None:
        if not ch.check_attrs_present(candset, attrs_after):
            logger.error(
                'The attributes mentioned in attrs_after is not present '
                'in the input table')
            raise AssertionError(
                'The attributes mentioned in attrs_after is not present '
                'in the input table')

    # We expect the feature table to be a valid object
    if feature_table is None:
        logger.error('Feature table cannot be null')
        raise AssertionError('The feature table cannot be null')

    # Do metadata checking
    # # Mention what metadata is required to the user
    ch.log_info(logger, 'Required metadata: cand.set key, fk ltable, '
                        'fk rtable, '
                        'ltable, rtable, ltable key, rtable key', verbose)

    # # Get metadata
    ch.log_info(logger, 'Getting metadata from catalog', verbose)

    key, fk_ltable, fk_rtable, ltable, rtable, l_key, r_key = \
        cm.get_metadata_for_candset(
        candset, logger, verbose)

    # # Validate metadata
    ch.log_info(logger, 'Validating metadata', verbose)
    cm._validate_metadata_for_candset(candset, key, fk_ltable, fk_rtable,
                                      ltable, rtable, l_key, r_key,
                                      logger, verbose)

    # Extract features



    # id_list = [(row[fk_ltable], row[fk_rtable]) for i, row in
    #            candset.iterrows()]
    # id_list = [tuple(tup) for tup in candset[[fk_ltable, fk_rtable]].values]

    # # Set index for convenience
    l_df = ltable.set_index(l_key, drop=False)
    r_df = rtable.set_index(r_key, drop=False)

    if show_progress:
        prog_bar = pyprind.ProgBar(len(candset))
    # # Apply feature functions
    feat_vals = []
    ch.log_info(logger, 'Applying feature functions', verbose)
    col_names = list(candset.columns)
    fk_ltable_idx =  col_names.index(fk_ltable)
    fk_rtable_idx =  col_names.index(fk_rtable)
    l_dict = {}
    r_dict = {}

    for row in candset.itertuples(index=False):

        if show_progress:
            prog_bar.update()
        fk_ltable_val = row[fk_ltable_idx]
        fk_rtable_val = row[fk_rtable_idx]

        if fk_ltable_val not in l_dict:
            l_dict[fk_ltable_val] = l_df.ix[fk_ltable_val]
        l_tuple = l_dict[fk_ltable_val]

        if fk_rtable_val not in r_dict:
            r_dict[fk_rtable_val] = r_df.ix[fk_rtable_val]
        r_tuple = r_dict[fk_rtable_val]


        f = apply_feat_fns(l_tuple, r_tuple, feature_table)
        feat_vals.append(f)


    # Construct output table
    feature_vectors = pd.DataFrame(feat_vals, index=candset.index.values)
    # # Rearrange the feature names in the input feature table order
    feature_names = list(feature_table['feature_name'])
    feature_vectors = feature_vectors[feature_names]

    ch.log_info(logger, 'Constructing output table', verbose)
    # print(feature_vectors)
    # # Insert attrs_before
    if attrs_before:
        if not isinstance(attrs_before, list):
            attrs_before = [attrs_before]
        attrs_before = gh.list_diff(attrs_before, [key, fk_ltable, fk_rtable])
        attrs_before.reverse()
        for a in attrs_before:
            feature_vectors.insert(0, a, candset[a])

    # # Insert keys
    feature_vectors.insert(0, fk_rtable, candset[fk_rtable])
    feature_vectors.insert(0, fk_ltable, candset[fk_ltable])
    feature_vectors.insert(0, key, candset[key])

    # # insert attrs after
    if attrs_after:
        if not isinstance(attrs_after, list):
            attrs_after = [attrs_after]
        attrs_after = gh.list_diff(attrs_after, [key, fk_ltable, fk_rtable])
        attrs_after.reverse()
        col_pos = len(feature_vectors.columns)
        for a in attrs_after:
            feature_vectors.insert(col_pos, a, candset[a])
            col_pos += 1

    # Reset the index
    # feature_vectors.reset_index(inplace=True, drop=True)

    # # Update the catalog
    cm.init_properties(feature_vectors)
    cm.copy_properties(candset, feature_vectors)

    # Finally, return the feature vectors
    return feature_vectors


def apply_feat_fns(tuple1, tuple2, feat_dict):
    """
    Apply feature functions to two tuples.
    """
    # Get the feature names
    feat_names = list(feat_dict['feature_name'])
    # Get the feature functions
    feat_funcs = list(feat_dict['function'])
    # Compute the feature value by applying the feature function to the input
    #  tuples.
    feat_vals = [f(tuple1, tuple2) for f in feat_funcs]
    # Return a dictionary where the keys are the feature names and the values
    #  are the feature values.
    return dict(zip(feat_names, feat_vals))
