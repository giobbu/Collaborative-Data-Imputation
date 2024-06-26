import pandas as pd
import numpy as np
import random
from sklearn.model_selection import train_test_split

def melt_dataframe(df, id_vars_='periodId', var_name_='farmId', value_name_='power'):
    try:
        df.index.names = [id_vars_]
        df_melt_with_nan = pd.melt(df.reset_index(), id_vars=id_vars_, value_vars=list(df.columns), var_name=var_name_, value_name=value_name_) 
        df_melt_without_nan = df_melt_with_nan.dropna().reset_index(drop=True)
        return df_melt_without_nan, df_melt_with_nan
    except Exception as e:
        print(f"Error during dataframe melting: {e}")
        return None


def _block_shuffle(df, blocksize, seed):
    try:
        # Extract data as a NumPy array
        data = df.values
        num_rows = len(data)
        # Shuffle block indices
        block_indices = list(range(num_rows // blocksize))
        random.Random(seed).shuffle(block_indices)
        # Shuffle blocks
        shuffled_blocks = [data[i * blocksize: (i + 1) * blocksize] for i in block_indices]
        # Concatenate shuffled blocks
        shuffled_data = np.concatenate(shuffled_blocks)
        # Convert to DataFrame
        df_shuffled = pd.DataFrame(shuffled_data, columns=df.columns)
        # Convert 'power' column to numeric
        df_shuffled['power'] = pd.to_numeric(df_shuffled['power'])
        return df_shuffled
    except Exception as e:
        print(f"Error during block shuffling: {e}")
        return None

def split_train_test(df, test_size=0.2, block=True, blocksize=48, seed=42):
    try:
        if block:
            # Shuffle blocks if block is True
            df_block = _block_shuffle(df, blocksize, seed)
            training_df, validation_df = train_test_split(df_block, test_size=test_size, shuffle=False)
        else:
            # Split randomly if block is False
            training_df, validation_df = train_test_split(df, test_size=test_size, random_state=seed)
        # Reset index for both training and validation DataFrames
        training_df.reset_index(drop=True, inplace=True)
        validation_df.reset_index(drop=True, inplace=True)
        return training_df, validation_df
    except Exception as e:
        print(f"Error occurred during data splitting: {e}")
        return None

class Normalizer:
    @staticmethod
    def normalize_power(training_df, validation_df, id_col='farmId', power_col='power'):
        try:
            # Calculate max and min mappings for each farmId
            max_mapping_train = training_df.groupby(id_col)[power_col].max()
            min_mapping_train = training_df.groupby(id_col)[power_col].min()
            # Map max and min values to each row based on farmId
            training_df['max'] = training_df[id_col].map(max_mapping_train)
            training_df['min'] = training_df[id_col].map(min_mapping_train)
            validation_df['max'] = validation_df[id_col].map(max_mapping_train)
            validation_df['min'] = validation_df[id_col].map(min_mapping_train)
            # Normalize power values using min-max scaling
            norm_training_df = training_df.assign(power_z=lambda row: (row[power_col] - row['min']) / (row['max'] - row['min'])).drop(['max', 'min', power_col], axis=1)
            norm_validation_df = validation_df.assign(power_z=lambda row: (row[power_col] - row['min']) / (row['max'] - row['min'])).drop(['max', 'min', power_col], axis=1)
            return norm_training_df, norm_validation_df, max_mapping_train, min_mapping_train
        except Exception as e:
            print(f"Error during normalization: {e}")
            return None

    @staticmethod
    def unnormalize_power(norm_df, id_col, power_col, max_mapping, min_mapping, cols_to_unscale):
        try:
            # Map max and min values to each row based on farmId
            norm_df['max'] = norm_df[id_col].map(max_mapping)
            norm_df['min'] = norm_df[id_col].map(min_mapping)
            # Unnormalize the specified columns
            for col in cols_to_unscale:
                norm_df[col] = norm_df['min'] + norm_df[col] * (norm_df['max'] - norm_df['min'])
            # Drop unnecessary columns
            norm_df.drop(['max', 'min', power_col], axis=1, inplace=True)
            return norm_df
        except Exception as e:
            print(f"Error during unnormalization: {e}")
            return None

def preprocess_ids(training_df, validation_df):
    try:
        # Retain Ids of the training set in the validation set
        validation_df = validation_df[validation_df.farmId.isin(training_df.farmId)]
        validation_df = validation_df[validation_df.periodId.isin(training_df.periodId)].reset_index(drop=True)
        # Map datetimes
        periodId = training_df.periodId.unique()
        datetime2id_mapping = dict(zip(periodId, range(len(periodId))))
        training_df.periodId = training_df.periodId.map(datetime2id_mapping)
        validation_df.periodId = validation_df.periodId.map(datetime2id_mapping)
        id2datetime_mapping = {v: k for k, v in datetime2id_mapping.items()}
        # Map farms
        farmId = training_df.farmId.unique()
        farm2id_mapping = dict(zip(farmId, range(len(farmId))))
        training_df.farmId = training_df.farmId.map(farm2id_mapping)
        validation_df.farmId = validation_df.farmId.map(farm2id_mapping)
        id2farm_mapping = {v: k for k, v in farm2id_mapping.items()}
        return training_df, validation_df, id2datetime_mapping, id2farm_mapping
    except Exception as e:
        print(f"Error occurred during retaining IDs: {e}")
        return None



def filter_data_by_common_periods_farms(training_df, validation_df):
    """
    Filter training and validation data to have common periods and farms.

    Args:
    - training_df (pandas.DataFrame): DataFrame containing training data with columns 'periodId' and 'farmId'.
    - validation_df (pandas.DataFrame): DataFrame containing validation data with columns 'periodId' and 'farmId'.

    Returns:
    - filtered_training_df (pandas.DataFrame): DataFrame containing filtered training data.
    - filtered_validation_df (pandas.DataFrame): DataFrame containing filtered validation data.
    """
    # Check input types
    if not all(isinstance(df, pd.DataFrame) for df in [training_df, validation_df]):
        raise TypeError("Both training_df and validation_df must be pandas DataFrames.")

    # Check column existence
    required_columns = ['periodId', 'farmId']
    for df, df_name in zip([training_df, validation_df], ['training_df', 'validation_df']):
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"{df_name} is missing columns: {', '.join(missing_columns)}.")

    # Filter common periods
    common_periods = set(validation_df['periodId']).intersection(training_df['periodId'])
    filtered_training_df = training_df[training_df['periodId'].isin(common_periods)]
    filtered_validation_df = validation_df[validation_df['periodId'].isin(common_periods)]

    # Filter common farms
    common_farms = set(filtered_validation_df['farmId']).intersection(filtered_training_df['farmId'])
    filtered_training_df = filtered_training_df[filtered_training_df['farmId'].isin(common_farms)]
    filtered_validation_df = filtered_validation_df[filtered_validation_df['farmId'].isin(common_farms)]

    # Check for consistency
    if len(filtered_training_df['periodId'].unique()) != len(filtered_validation_df['periodId'].unique()) \
            or len(filtered_training_df['farmId'].unique()) != len(filtered_validation_df['farmId'].unique()):
        raise ValueError("Number of unique periodIds and farmIds in training and validation data must match.")

    return filtered_training_df, filtered_validation_df


def sqrt_transformation(df):
    try:
        for col in list(df['farmId'].unique()):
            mask = df['farmId'] == col
            df.loc[mask, 'power_z'] = np.sqrt(df.loc[mask, 'power_z'])
        return df
    except Exception as e:
        print(f"Error occurred in sqrt_transformation function: {str(e)}")
        return None


def create_insample_df(train_periods, train_farms, train_targets, train_predictions, lst_farms):
    try:
        # Create DataFrame from input lists
        df_insample = pd.DataFrame({
            'periodId': train_periods,
            'farmId': train_farms,
            'targets': train_targets,
            'predictions': train_predictions
        })
        df_insample = df_insample.set_index('periodId')
        # Filter DataFrame by selected farm IDs
        df_insample = df_insample[df_insample['farmId'].isin(lst_farms)]
        # Calculate residuals
        df_insample['residuals'] = df_insample['targets'] - df_insample['predictions']
        return df_insample
    except Exception as e:
        print(f"An error occurred during data preprocessing: {e}")
        return None

def create_outsample_df(test_periods, test_farms, test_targets, test_predictions, lst_farms):
    try:
        # Create DataFrame from input lists
        df_outsample = pd.DataFrame({
            'periodId': test_periods,
            'farmId': test_farms,
            'targets': test_targets,
            'predictions': test_predictions
        })
        # Set periodId as index
        df_outsample = df_outsample.set_index('periodId')
        # Filter DataFrame by selected farm IDs
        df_outsample = df_outsample[df_outsample['farmId'].isin(lst_farms)]
        return df_outsample
    except Exception as e:
        print(f"An error occurred during out-of-sample data preprocessing: {e}")
        return None