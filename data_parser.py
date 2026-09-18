import os
import pandas as pd
from typing import Union

def _resolve_path(path: Union[str, os.PathLike]) -> str:
    if os.path.exists(path):
        return str(path)
    # Check if prefixed with PS1
    ps1_path = os.path.join("PS1", str(path))
    if os.path.exists(ps1_path):
        return ps1_path
    # Check if stripping PS1
    if str(path).startswith("PS1/") or str(path).startswith("PS1\\"):
        strip_path = str(path)[4:]
        if os.path.exists(strip_path):
            return strip_path
    return str(path)

def load_and_merge_data(
    activity_source: Union[str, os.PathLike, pd.DataFrame] = "PS1/01_data/08_ACTIVITY_DETAILS.csv",
    project_source: Union[str, os.PathLike, pd.DataFrame] = "PS1/01_data/07_PROJECT_DETAILS.csv",
) -> pd.DataFrame:
    """
    Load activity details and project details CSVs, left-merge on 'contract_number',
    standardize date formats, and clean up duplicate/overlapping columns.
    
    Supports file paths, Path objects, file-like buffers, or pre-loaded pandas DataFrames.
    """
    # 1. Load activity dataframe
    if isinstance(activity_source, pd.DataFrame):
        df_act = activity_source.copy()
    else:
        df_act = pd.read_csv(_resolve_path(activity_source))
        
    # 2. Load project dataframe
    if isinstance(project_source, pd.DataFrame):
        df_proj = project_source.copy()
    else:
        df_proj = pd.read_csv(_resolve_path(project_source))
        
    # 3. Clean strings / strip whitespace in key columns
    if 'contract_number' in df_act.columns:
        df_act['contract_number'] = df_act['contract_number'].astype(str).str.strip()
    if 'contract_number' in df_proj.columns:
        df_proj['contract_number'] = df_proj['contract_number'].astype(str).str.strip()

    # 4. Perform Left Join on 'contract_number'
    # Note: Both files contain 'activity_type' (e.g. Renewal, Construction).
    # We join on contract_number and handle suffix deduplication.
    merged = pd.merge(df_act, df_proj, on="contract_number", how="left", suffixes=("", "_proj"))

    # If activity_type_proj exists and is duplicate, drop the redundant project column
    if "activity_type_proj" in merged.columns:
        merged.drop(columns=["activity_type_proj"], inplace=True)

    # 5. Handle date parsing and formatting
    date_columns = [
        "planned_start_date",
        "contract_award_date",
        "contract_completion_date",
        "planned_completion_date"
    ]
    for col in date_columns:
        if col in merged.columns:
            merged[col] = pd.to_datetime(merged[col], errors="coerce")

    # 6. Type conversions for key numeric / integer fields
    numeric_int_cols = [
        "total_accesses",
        "activity_priority",
        "contract_priority",
        "number_of_workfronts",
        "number_of_maximum_access_per_week"
    ]
    for col in numeric_int_cols:
        if col in merged.columns:
            merged[col] = pd.to_numeric(merged[col], errors="coerce")

    return merged

if __name__ == "__main__":
    # Test execution
    df = load_and_merge_data()
    print("Successfully loaded and merged data!")
    print(f"Shape: {df.shape}")
    print("\nColumns and Dtypes:")
    print(df.dtypes)
    print("\nSample Preview:")
    print(df[["activity_id", "contract_number", "activity_type", "planned_start_date", "contract_priority", "total_accesses"]].head(5))
