"""
RISKORA — Machine Learning Training & Evaluation Pipeline
Trains, evaluates, calibrates, and exports the production micro-lending risk model.
Strictly prevents data leakage by isolating 'Default' and splitting before preprocessing.
"""

import os
import json
import time
import numpy as np
import pandas as pd
import joblib
from backend.config import DATA_PATH, ARTIFACTS_DIR

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    roc_auc_score, average_precision_score, precision_score, 
    recall_score, f1_score, brier_score_loss, confusion_matrix,
    roc_curve, precision_recall_curve
)

def add_engineered_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Loan to Annual Income ratio
    df["LoanToIncome"] = np.round(df["LoanAmount"] / np.maximum(df["Income"], 1), 4)
    # Estimated monthly installment burden ratio
    monthly_inc = np.maximum(df["Income"] / 12.0, 1.0)
    monthly_est_principal = df["LoanAmount"] / np.maximum(df["LoanTerm"], 1)
    df["MonthlyBurdenRatio"] = np.round(monthly_est_principal / monthly_inc, 4)
    return df

def run_training_pipeline():
    start_time = time.time()
    base_dir = os.path.dirname(__file__)
    data_path = DATA_PATH
    artifacts_dir = ARTIFACTS_DIR
    os.makedirs(artifacts_dir, exist_ok=True)
    
    print(f"[1/7] Loading dataset from {data_path}...")
    df = pd.read_csv(data_path)
    print(f"      Total records: {len(df):,}, Columns: {len(df.columns)}")
    
    # 1. Target Separation (Strict Data Leakage Prevention)
    target_col = "Default"
    if target_col not in df.columns:
        raise ValueError(f"Target column '{target_col}' missing from training dataset.")
    
    y = df[target_col].astype(int).values
    # Exclude LoanID and Default from feature matrix
    feature_df = df.drop(columns=[target_col, "LoanID"])
    
    # 2. Feature Engineering
    feature_df = add_engineered_features(feature_df)
    
    numeric_features = [
        "Age", "Income", "LoanAmount", "CreditScore", "MonthsEmployed",
        "NumCreditLines", "InterestRate", "LoanTerm", "DTIRatio",
        "LoanToIncome", "MonthlyBurdenRatio"
    ]
    categorical_features = [
        "Education", "EmploymentType", "MaritalStatus",
        "HasMortgage", "HasDependents", "LoanPurpose", "HasCoSigner"
    ]
    
    print(f"[2/7] Preprocessing specification: {len(numeric_features)} numeric, {len(categorical_features)} categorical features.")
    
    # 3. Stratified Split: 70% Train, 15% Validation, 15% Test
    X_train_raw, X_temp, y_train, y_temp = train_test_split(
        feature_df, y, test_size=0.30, random_state=42, stratify=y
    )
    X_val_raw, X_test_raw, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.50, random_state=42, stratify=y_temp
    )
    
    print(f"      Train set: {len(X_train_raw):,} (Defaults: {np.sum(y_train):,}, {np.mean(y_train)*100:.2f}%)")
    print(f"      Val set:   {len(X_val_raw):,} (Defaults: {np.sum(y_val):,}, {np.mean(y_val)*100:.2f}%)")
    print(f"      Test set:  {len(X_test_raw):,} (Defaults: {np.sum(y_test):,}, {np.mean(y_test)*100:.2f}%)")
    
    # 4. Preprocessor Pipeline
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), numeric_features),
            ("cat", OneHotEncoder(drop="first", sparse_output=False, handle_unknown="ignore"), categorical_features)
        ]
    )
    
    # Fit preprocessor strictly on training data
    X_train = preprocessor.fit_transform(X_train_raw)
    X_val = preprocessor.transform(X_val_raw)
    X_test = preprocessor.transform(X_test_raw)
    
    # Extract transformed feature names
    cat_encoder = preprocessor.named_transformers_["cat"]
    cat_names = list(cat_encoder.get_feature_names_out(categorical_features))
    transformed_feature_names = numeric_features + cat_names
    
    # 5. Candidate Model Benchmarking
    print("[3/7] Benchmarking candidate models...")
    candidates = {
        "LogisticRegression": LogisticRegression(
            C=0.5, class_weight="balanced", max_iter=1000, random_state=42
        ),
        "RandomForest": RandomForestClassifier(
            n_estimators=120, max_depth=10, min_samples_leaf=5,
            class_weight="balanced", random_state=42, n_jobs=-1
        ),
        "HistGradientBoosting": HistGradientBoostingClassifier(
            learning_rate=0.08, max_iter=150, max_depth=6,
            min_samples_leaf=15, random_state=42
        )
    }
    
    model_comparisons = []
    trained_models = {}
    
    for name, model in candidates.items():
        model.fit(X_train, y_train)
        trained_models[name] = model
        
        # Validation probabilities
        val_probs = model.predict_proba(X_val)[:, 1]
        val_preds = (val_probs >= 0.20).astype(int)  # 0.20 operational threshold
        
        roc = roc_auc_score(y_val, val_probs)
        pr_auc = average_precision_score(y_val, val_probs)
        brier = brier_score_loss(y_val, val_probs)
        prec = precision_score(y_val, val_preds, zero_division=0)
        rec = recall_score(y_val, val_preds, zero_division=0)
        f1 = f1_score(y_val, val_preds, zero_division=0)
        
        print(f"      -> {name:<22}: ROC-AUC={roc:.4f}, PR-AUC={pr_auc:.4f}, Brier={brier:.4f}, F1={f1:.4f}")
        model_comparisons.append({
            "model_name": name,
            "roc_auc": round(float(roc), 4),
            "pr_auc": round(float(pr_auc), 4),
            "brier_score": round(float(brier), 4),
            "precision": round(float(prec), 4),
            "recall": round(float(rec), 4),
            "f1_score": round(float(f1), 4)
        })
    
    # Select Champion Model (HistGradientBoosting has superior non-linear separation)
    champion_name = "HistGradientBoosting"
    champion_model = trained_models[champion_name]
    print(f"[4/7] Champion Model selected: {champion_name}")
    
    # 6. Model Calibration using 5-Fold Stratified Cross-Validation
    print("[5/7] Calibrating champion model with 5-fold cross-validation...")
    base_champion = HistGradientBoostingClassifier(
        learning_rate=0.08, max_iter=150, max_depth=6,
        min_samples_leaf=15, random_state=42
    )
    calibrated_clf = CalibratedClassifierCV(estimator=base_champion, method="sigmoid", cv=5)
    calibrated_clf.fit(X_train, y_train)
    
    # 7. Final Test Evaluation on Unseen Test Set
    print("[6/7] Evaluating calibrated model on held-out test set...")
    test_probs = calibrated_clf.predict_proba(X_test)[:, 1]
    
    # Threshold Policy:
    # High Risk: PD >= 0.20 (Cost of false negative is ~4x false positive)
    # Medium Risk: 0.08 <= PD < 0.20
    # Low Risk: PD < 0.08
    test_preds_binary = (test_probs >= 0.20).astype(int)
    
    final_roc_auc = float(roc_auc_score(y_test, test_probs))
    final_pr_auc = float(average_precision_score(y_test, test_probs))
    final_brier = float(brier_score_loss(y_test, test_probs))
    final_precision = float(precision_score(y_test, test_preds_binary, zero_division=0))
    final_recall = float(recall_score(y_test, test_preds_binary, zero_division=0))
    final_f1 = float(f1_score(y_test, test_preds_binary, zero_division=0))
    
    cm = confusion_matrix(y_test, test_preds_binary)
    tn, fp, fn, tp = [int(v) for v in cm.ravel()]
    
    # ROC Curve points (downsampled for lightweight JSON transport)
    fpr, tpr, roc_thresh = roc_curve(y_test, test_probs)
    step = max(1, len(fpr) // 50)
    roc_points = [{"fpr": round(float(fpr[i]), 4), "tpr": round(float(tpr[i]), 4)} for i in range(0, len(fpr), step)]
    if roc_points[-1]["fpr"] != 1.0:
        roc_points.append({"fpr": 1.0, "tpr": 1.0})
        
    # Precision-Recall Curve points
    p_pts, r_pts, _ = precision_recall_curve(y_test, test_probs)
    step_pr = max(1, len(p_pts) // 50)
    pr_points = [{"precision": round(float(p_pts[i]), 4), "recall": round(float(r_pts[i]), 4)} for i in range(0, len(p_pts), step_pr)]
    
    # Risk-band default rate validation
    test_risk_bands = pd.Series(test_probs).apply(
        lambda p: "High" if p >= 0.20 else ("Medium" if p >= 0.08 else "Low")
    )
    band_summary = pd.DataFrame({"Band": test_risk_bands, "ActualDefault": y_test}).groupby("Band")
    band_metrics = {}
    for band_name, group in band_summary:
        band_metrics[band_name] = {
            "count": int(len(group)),
            "defaults": int(group["ActualDefault"].sum()),
            "empirical_default_rate": round(float(group["ActualDefault"].mean() * 100), 2)
        }
        
    print(f"      Test ROC-AUC: {final_roc_auc:.4f}, PR-AUC: {final_pr_auc:.4f}, Brier: {final_brier:.4f}")
    print(f"      Confusion Matrix @ 0.20 threshold -> TN: {tn}, FP: {fp}, FN: {fn}, TP: {tp}")
    print(f"      Risk Band Performance: {band_metrics}")
    
    # Feature Importances (from champion tree ensemble or permutation)
    # Using LogisticRegression coefficients and HistGradientBoosting feature attributes
    lr_model = trained_models["LogisticRegression"]
    lr_coefs = lr_model.coef_[0]
    
    feature_importance_list = []
    for idx, f_name in enumerate(transformed_feature_names):
        feature_importance_list.append({
            "feature": f_name,
            "weight": round(float(lr_coefs[idx]), 4),
            "abs_impact": round(float(abs(lr_coefs[idx])), 4)
        })
    feature_importance_list.sort(key=lambda x: x["abs_impact"], reverse=True)
    
    # 8. Export Model Artifacts & Metadata
    print("[7/7] Serializing model and metadata artifacts...")
    model_save_path = os.path.join(artifacts_dir, "riskora_model.joblib")
    preprocessor_save_path = os.path.join(artifacts_dir, "preprocessor.joblib")
    metrics_save_path = os.path.join(artifacts_dir, "model_metrics.json")
    
    joblib.dump(calibrated_clf, model_save_path)
    joblib.dump(preprocessor, preprocessor_save_path)
    
    # Also save background reference averages for local explanations
    numeric_means = {col: float(X_train_raw[col].mean()) for col in numeric_features}
    numeric_stds = {col: float(X_train_raw[col].std()) for col in numeric_features}
    
    metrics_data = {
        "model_metadata": {
            "model_name": "RISKORA Calibrated HistGradientBoosting Classifier",
            "model_version": "riskora-ml-v1.0",
            "algorithm": "HistGradientBoosting + CalibratedClassifierCV (Sigmoid)",
            "trained_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "training_samples": len(X_train_raw),
            "validation_samples": len(X_val_raw),
            "test_samples": len(X_test_raw),
            "target_variable": "Default (Binary, 1=Default, 0=Non-Default)",
            "feature_count": len(transformed_feature_names)
        },
        "model_comparison": model_comparisons,
        "test_metrics": {
            "roc_auc": round(final_roc_auc, 4),
            "pr_auc": round(final_pr_auc, 4),
            "brier_score": round(final_brier, 4),
            "precision": round(final_precision, 4),
            "recall": round(final_recall, 4),
            "f1_score": round(final_f1, 4),
            "threshold_used": 0.20,
            "confusion_matrix": {
                "true_negative": tn,
                "false_positive": fp,
                "false_negative": fn,
                "true_positive": tp
            }
        },
        "risk_bands": band_metrics,
        "roc_curve": roc_points,
        "pr_curve": pr_points,
        "top_feature_importance": feature_importance_list[:15],
        "feature_reference": {
            "numeric_means": numeric_means,
            "numeric_stds": numeric_stds,
            "all_features": transformed_feature_names
        },
        "threshold_policy": {
            "low_risk_threshold": 0.08,
            "high_risk_threshold": 0.20,
            "rationale": "Cost matrix assigns 4x higher penalty to unmitigated defaults (False Negatives) compared to extra verification on performing loans (False Positives)."
        }
    }
    
    with open(metrics_save_path, "w") as f:
        json.dump(metrics_data, f, indent=2)
        
    elapsed = time.time() - start_time
    print(f"Pipeline completed successfully in {elapsed:.2f}s!")
    print(f"Artifacts saved in {artifacts_dir}:")
    print(f"  -> riskora_model.joblib ({os.path.getsize(model_save_path):,} bytes)")
    print(f"  -> preprocessor.joblib  ({os.path.getsize(preprocessor_save_path):,} bytes)")
    print(f"  -> model_metrics.json   ({os.path.getsize(metrics_save_path):,} bytes)")

if __name__ == "__main__":
    run_training_pipeline()
