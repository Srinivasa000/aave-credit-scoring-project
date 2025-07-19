# **Aave V2 On-Chain Credit Scoring Model**

## **1. Project Overview**

This project introduces a robust, transparent credit scoring model for wallets interacting with the Aave V2 protocol. The model analyzes raw, historical transaction data to assign a credit score between **0 and 1000** to each wallet.

The primary goal is to quantify a wallet's financial reliability based purely on its on-chain behavior, without relying on any off-chain or personally identifiable information.

* **High Score (e.g., 800-1000):** Indicates a reliable, responsible, and low-risk user. These are typically long-term liquidity providers or highly collateralized borrowers.
* **Low Score (e.g., 0-300):** Reflects risky, speculative, or potentially mismanaged behavior. These wallets are often highly leveraged and may have a history of being liquidated.

## **2. Scoring Logic and Architecture**

Instead of a "black box" machine learning model, this project uses a **transparent, feature-based heuristic system**. This ensures that every score is easily explainable and directly tied to a wallet's on-chain actions.

The final score is a weighted combination of several key behavioral features, which are then normalized to a 0-1000 scale.

### **Key Behavioral Features**

The model evaluates wallets across the following dimensions:

1.  **Risk Profile (Liquidations):** This is the most critical factor. Wallets are heavily penalized for each `liquidationcall` event, as this is the clearest sign of poor debt management.
2.  **Capital Health (Health Factor Proxy):** Calculated as the ratio of the total USD value of a wallet's deposits to its borrows. A higher ratio signifies a safer, over-collateralized position and results in a higher score.
3.  **Repayment Reliability:** The model measures the ratio of `repay` actions to `borrow` actions. Wallets that consistently repay their debts are rewarded for their reliability.
4.  **Protocol Loyalty & History:** Long-term, consistent interaction is a positive signal. The model rewards wallets based on their "age" (time since their first transaction) and their total transaction count.
5.  **Liquidity Provision:** Wallets that are net depositors (i.e., `deposit` value > `redeem` value) are rewarded, as they provide essential liquidity that keeps the protocol healthy.

### **Processing Flow**

The `score_wallets.py` script automates the entire process in a single step:

1.  **Load & Clean Data:** Ingests the `user-transactions.json` file. It handles different data formats by renaming columns and manually calculating the transaction's USD value from the raw `amount` and `assetPriceUSD` fields.
2.  **Engineer Features:** For each unique wallet, it calculates all the key behavioral features listed above by aggregating its entire transaction history.
3.  **Calculate Raw Score:** Combines the features into a single raw score using a weighted formula that rewards positive behavior and penalizes negative actions.
4.  **Normalize Score:** The raw scores are scaled to the final **0-1000** range using Min-Max normalization. This ensures all scores are fair and directly comparable.
5.  **Output Results:** The script saves the final scores to `wallet_scores.csv` and generates a score distribution graph named `score_distribution.png`.

## **3. How to Run the Script**

To replicate the results, follow these steps:

1.  **Prerequisites:** Ensure you have Python 3.8+ and the required libraries installed:
    ```bash
    pip install pandas numpy matplotlib seaborn
    ```
2.  **Add Data File:** Place the `user-transactions.json` data file in the same directory as the `score_wallets.py` script.
3.  **Execute:** Run the script from your terminal:
    ```bash
    python score_wallets.py
    ```
4.  **Check Outputs:** The script will generate `wallet_scores.csv` and `score_distribution.png` in the project folder.
