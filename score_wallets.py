# ==============================================================================
# AAVE V2 WALLET CREDIT SCORING SCRIPT (v5 - Manual Calculation)
#
# Description:
# This script performs a complete analysis of Aave V2 transaction data to
# assign a credit score (0-1000) to each wallet. This version correctly
# calculates the transaction's USD value from raw amount and price data.
#
# Instructions:
# 1. Place the 'user-transactions.json' file in the same directory as this script.
# 2. Run the script from your terminal: python score_wallets.py
# ==============================================================================

# --- Part 1: Import necessary libraries ---
import pandas as pd
import numpy as np
import json
import os
import matplotlib.pyplot as plt
import seaborn as sns

# --- Part 2: Define all functions ---

def load_data(filepath: str) -> pd.DataFrame:
    """
    Loads transaction data, renames columns, and manually calculates the
    USD value from the nested 'actionData' column using amount and price.
    """
    print(f"Step 1: Loading data from '{filepath}'...")
    
    if not os.path.exists(filepath):
        print(f"❌ FATAL ERROR: The data file '{filepath}' was not found.")
        exit()
        
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError:
        print(f"❌ FATAL ERROR: The file '{filepath}' is not a valid JSON file.")
        exit()

    if not data:
        print(f"❌ FATAL ERROR: The JSON file '{filepath}' is empty.")
        exit()

    df = pd.DataFrame(data)
    
    # --- **FINAL FIX** Column Mapping and Manual Value Calculation ---
    print("...Remapping columns and manually calculating USD values...")

    column_mapping = {'userWallet': 'wallet', '_id': 'id'}
    df.rename(columns=column_mapping, inplace=True)

    # Dictionary of common token decimals. This is crucial for correct calculations.
    TOKEN_DECIMALS = {
        'USDC': 6,
        'USDT': 6,
        'DAI': 18,
        'WETH': 18,
        'WMATIC': 18,
        'WBTC': 8,
        'AAVE': 18,
        'LINK': 18,
        # Add other tokens as needed, default to 18 if not found
    }

    # Helper function to calculate the USD value
    def calculate_usd_value(action_data):
        if not isinstance(action_data, dict):
            return None
        
        try:
            asset_symbol = action_data.get('assetSymbol')
            # Get decimals, defaulting to 18 (most common) if symbol not in our dict
            decimals = TOKEN_DECIMALS.get(asset_symbol, 18)
            
            # Convert amount and price from string to float for calculation
            amount = float(action_data.get('amount', 0))
            price_usd = float(action_data.get('assetPriceUSD', 0))
            
            # The core calculation: (amount / 10^decimals) * price
            # This correctly scales the raw amount before multiplying by the price.
            if price_usd > 0:
                return (amount / (10**decimals)) * price_usd
            else:
                return 0.0

        except (ValueError, TypeError, KeyError):
            # If any conversion fails or a key is missing, return None
            return None

    df['value_usd'] = df['actionData'].apply(calculate_usd_value)
    # --- End of Final Fix ---

    print(f"...Initial row count: {len(df)}")
    print(f"...Rows with a missing USD value before cleaning: {df['value_usd'].isnull().sum()}")

    df['timestamp'] = pd.to_numeric(df['timestamp'], errors='coerce')
    df['value_usd'] = pd.to_numeric(df['value_usd'], errors='coerce')
    df.dropna(subset=['timestamp', 'value_usd'], inplace=True)
    
    if df.empty:
        print("❌ FATAL ERROR: After manual calculation, no valid transactions with a USD value were found.")
        exit()

    print(f"✅ Data loaded and formatted successfully. Found {len(df)} valid transactions.")
    return df

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Engineers features for each wallet from the raw transaction data.
    """
    print("\nStep 2: Engineering features for each wallet...")
    
    df = df.sort_values('timestamp').reset_index(drop=True)
    wallets_grouped = df.groupby('wallet')
    
    features = wallets_grouped.agg(
        first_tx_time=('timestamp', 'min'),
        last_tx_time=('timestamp', 'max'),
        transaction_count=('id', 'count')
    ).reset_index()

    features['wallet_age_days'] = ((features['last_tx_time'] - features['first_tx_time']) / (60*60*24)).fillna(0).clip(lower=1)

    action_counts = df.pivot_table(index='wallet', columns='action', aggfunc='size', fill_value=0)
    value_agg = df.pivot_table(index='wallet', columns='action', values='value_usd', aggfunc='sum', fill_value=0)
    
    features = features.merge(action_counts, on='wallet', how='left')
    features = features.merge(value_agg, on='wallet', how='left', suffixes=('_count', '_value'))
    
    expected_actions = ['deposit', 'borrow', 'repay', 'redeemunderlying', 'liquidationcall']
    for action in expected_actions:
        if action not in features.columns: features[action] = 0
        if f"{action}_value" not in features.columns: features[f"{action}_value"] = 0
            
    features = features.fillna(0)
    
    print("✅ Features engineered successfully.")
    return features

def calculate_scores(features_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates a credit score (0-1000) for each wallet based on its features.
    """
    print("\nStep 3: Calculating credit scores...")
    df = features_df.copy()
    
    liquidation_penalty = df.get('liquidationcall', 0) * 300
    df['health_factor_proxy'] = df.get('deposit_value', 0) / (df.get('borrow_value', 0) + 1)
    health_score = np.log1p(df['health_factor_proxy']) * 50
    df['repay_borrow_ratio'] = df.get('repay', 0) / (df.get('borrow', 0) + 1)
    reliability_score = np.minimum(df['repay_borrow_ratio'], 1.5) * 100
    age_score = np.log1p(df['wallet_age_days']) * 25
    activity_score = np.log1p(df['transaction_count']) * 10
    df['net_deposit_value'] = df.get('deposit_value', 0) - df.get('redeemunderlying_value', 0)
    provider_score = (df['net_deposit_value'] > 0) * np.log1p(df['net_deposit_value'].clip(lower=0)) * 0.1

    df['raw_score'] = (
        500
        + health_score
        + reliability_score
        + age_score
        + activity_score
        + provider_score
        - liquidation_penalty
    )

    min_raw_score = df['raw_score'].min()
    max_raw_score = df['raw_score'].max()
    
    if max_raw_score == min_raw_score:
        df['credit_score'] = 500
    else:
        df['credit_score'] = 1000 * (df['raw_score'] - min_raw_score) / (max_raw_score - min_raw_score)

    df['credit_score'] = df['credit_score'].astype(int)
    
    print("✅ Scoring complete.")
    
    return df[['wallet', 'credit_score']].sort_values('credit_score', ascending=False)

def generate_analysis_visuals(scored_df: pd.DataFrame, output_filename: str):
    """
    Generates and saves the score distribution histogram.
    """
    print(f"\nStep 4: Generating analysis graph...")
    plt.style.use('seaborn-v0_8-whitegrid')
    plt.figure(figsize=(12, 7))
    
    sns.histplot(data=scored_df, x='credit_score', bins=10, kde=False, color='#3498db', edgecolor='black')
    
    plt.title('Distribution of Wallet Credit Scores (0-1000)', fontsize=18, fontweight='bold')
    plt.xlabel('Credit Score Bins', fontsize=14)
    plt.ylabel('Number of Wallets', fontsize=14)
    plt.xticks(range(0, 1001, 100))
    
    plt.savefig(output_filename, dpi=300, bbox_inches='tight')
    print(f"✅ Analysis graph saved to '{output_filename}'")


# --- Part 3: Main execution block ---

def main():
    """
    Main function to run the entire scoring and analysis pipeline.
    """
    json_filepath = 'user-transactions.json'
    output_csv_filepath = 'wallet_scores.csv'
    output_image_filepath = 'score_distribution.png'
    
    raw_df = load_data(json_filepath)
    features_df = engineer_features(raw_df)
    scored_df = calculate_scores(features_df)
    generate_analysis_visuals(scored_df, output_image_filepath)
    
    scored_df.to_csv(output_csv_filepath, index=False)
    print(f"✅ Final scores saved to '{output_csv_filepath}'")
    
    print("\n🎉 Pipeline finished successfully!")

if __name__ == '__main__':
    main()
# --- End of script ---
# ==============================================================================