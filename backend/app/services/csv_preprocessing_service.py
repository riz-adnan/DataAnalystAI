import re
from io import BytesIO
from typing import Any

import pandas as pd


DATE_NAME_HINTS = ("date", "time", "created", "updated")
NUMERIC_RATIO_THRESHOLD = 0.8
DATETIME_RATIO_THRESHOLD = 0.8


def _empty_report(rows_before: int, columns_count: int) -> dict[str, Any]:
    return {
        "rows_before": rows_before,
        "rows_after": rows_before,
        "columns_count": columns_count,
        "duplicates_removed": 0,
        "missing_values": {"total_missing": 0, "columns": {}},
        "type_inference": {
            "date_columns": [],
            "numeric_columns": [],
            "categorical_columns": [],
            "text_columns": [],
        },
        "type_conversions": {},
        "outliers": {"columns": {}},
        "cleaning_summary": [],
    }


def _json_safe(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value


def _json_safe_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    return df.astype(object).where(pd.notnull(df), None).map(_json_safe)


def build_schema_preview(csv_name: str, cleaned_df: pd.DataFrame) -> dict[str, Any]:
    preview_df = _json_safe_dataframe(cleaned_df.head(2))

    return {
        "csv_name": csv_name,
        "columns": [str(column) for column in cleaned_df.columns.tolist()],
        "sample_rows": preview_df.to_dict(orient="records"),
    }


def dataframe_to_json_safe_records(df: pd.DataFrame, limit: int) -> list[dict[str, Any]]:
    preview_df = _json_safe_dataframe(df.head(limit))
    return preview_df.to_dict(orient="records")


def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize headers while preserving uniqueness after cleanup."""
    normalized_columns: list[str] = []
    seen: dict[str, int] = {}

    for index, column in enumerate(df.columns):
        normalized = str(column).strip().lower()
        normalized = re.sub(r"\s+", "_", normalized)
        normalized = re.sub(r"[^a-z0-9_]", "", normalized)
        normalized = re.sub(r"_+", "_", normalized).strip("_")
        normalized = normalized or f"column_{index + 1}"

        count = seen.get(normalized, 0)
        seen[normalized] = count + 1
        if count:
            normalized = f"{normalized}_{count + 1}"

        normalized_columns.append(normalized)

    cleaned = df.copy()
    cleaned.columns = normalized_columns
    return cleaned


def _clean_numeric_series(series: pd.Series) -> pd.Series:
    as_text = series.astype("string").str.strip()
    as_text = as_text.str.replace("[$\u20ac\u00a3\u20b9,]", "", regex=True)
    as_text = as_text.str.replace(r"^\((.*)\)$", r"-\1", regex=True)
    return pd.to_numeric(as_text, errors="coerce")


def convert_dates(df: pd.DataFrame, report: dict[str, Any]) -> pd.DataFrame:
    cleaned = df.copy()

    for column in cleaned.columns:
        if pd.api.types.is_datetime64_any_dtype(cleaned[column]) or pd.api.types.is_numeric_dtype(cleaned[column]):
            continue

        non_null = cleaned[column].dropna()
        if non_null.empty:
            continue

        name_hint = any(hint in column.lower() for hint in DATE_NAME_HINTS)
        numeric_like = _clean_numeric_series(cleaned[column]).loc[non_null.index].notna().mean()
        if not name_hint and numeric_like >= NUMERIC_RATIO_THRESHOLD:
            continue

        parsed = pd.to_datetime(cleaned[column], errors="coerce", format="mixed")
        parsed_non_null = parsed.loc[non_null.index]
        parse_ratio = float(parsed_non_null.notna().mean())

        if name_hint or parse_ratio >= DATETIME_RATIO_THRESHOLD:
            failed_values = int(non_null.shape[0] - parsed_non_null.notna().sum())
            report["type_conversions"][column] = {
                "from": str(cleaned[column].dtype),
                "to": "datetime",
                "failed_values": failed_values,
            }
            cleaned[column] = parsed
            report["cleaning_summary"].append(f"Converted {column} to datetime")

    return cleaned


def convert_numeric_columns(df: pd.DataFrame, report: dict[str, Any]) -> pd.DataFrame:
    cleaned = df.copy()

    for column in cleaned.columns:
        if pd.api.types.is_numeric_dtype(cleaned[column]) or pd.api.types.is_datetime64_any_dtype(cleaned[column]):
            continue

        non_null = cleaned[column].dropna()
        if non_null.empty:
            continue

        converted = _clean_numeric_series(cleaned[column])
        converted_non_null = converted.loc[non_null.index]
        convert_ratio = float(converted_non_null.notna().mean())

        if convert_ratio >= NUMERIC_RATIO_THRESHOLD:
            failed_values = int(non_null.shape[0] - converted_non_null.notna().sum())
            report["type_conversions"][column] = {
                "from": str(cleaned[column].dtype),
                "to": "numeric",
                "failed_values": failed_values,
            }
            cleaned[column] = converted
            report["cleaning_summary"].append(f"Converted {column} to numeric")

    return cleaned


def infer_column_types(df: pd.DataFrame) -> dict[str, list[str]]:
    inferred = {
        "date_columns": [],
        "numeric_columns": [],
        "categorical_columns": [],
        "text_columns": [],
    }

    for column in df.columns:
        series = df[column]
        if pd.api.types.is_datetime64_any_dtype(series):
            inferred["date_columns"].append(column)
        elif pd.api.types.is_numeric_dtype(series):
            inferred["numeric_columns"].append(column)
        else:
            unique_ratio = 0.0 if len(series) == 0 else float(series.nunique(dropna=True) / max(len(series), 1))
            average_length = series.dropna().astype(str).str.len().mean()
            if unique_ratio > 0.5 or (not pd.isna(average_length) and average_length > 40):
                inferred["text_columns"].append(column)
            else:
                inferred["categorical_columns"].append(column)

    return inferred


def handle_missing_values(df: pd.DataFrame, report: dict[str, Any]) -> pd.DataFrame:
    cleaned = df.copy()
    total_missing = int(cleaned.isna().sum().sum())
    report["missing_values"]["total_missing"] = total_missing

    for column in cleaned.columns:
        missing_count = int(cleaned[column].isna().sum())
        if missing_count == 0:
            continue

        missing_percentage = round((missing_count / max(len(cleaned), 1)) * 100, 2)
        strategy = "none"

        if pd.api.types.is_numeric_dtype(cleaned[column]):
            median_value = cleaned[column].median()
            if not pd.isna(median_value):
                cleaned[column] = cleaned[column].fillna(median_value)
                strategy = "median_fill"
                report["cleaning_summary"].append(
                    f"Filled {missing_count} missing values in {column} using median"
                )
        elif pd.api.types.is_datetime64_any_dtype(cleaned[column]):
            strategy = "none"
        else:
            cleaned[column] = cleaned[column].fillna("Unknown")
            strategy = "unknown_fill"
            report["cleaning_summary"].append(
                f"Filled {missing_count} missing values in {column} using Unknown"
            )

        report["missing_values"]["columns"][column] = {
            "missing_count": missing_count,
            "missing_percentage": missing_percentage,
            "strategy": strategy,
        }

    return cleaned


def handle_outliers(df: pd.DataFrame, report: dict[str, Any]) -> pd.DataFrame:
    cleaned = df.copy()

    for column in cleaned.select_dtypes(include="number").columns:
        q1 = cleaned[column].quantile(0.25)
        q3 = cleaned[column].quantile(0.75)
        iqr = q3 - q1

        if pd.isna(iqr) or iqr == 0:
            continue

        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        outlier_mask = (cleaned[column] < lower_bound) | (cleaned[column] > upper_bound)
        outlier_count = int(outlier_mask.sum())

        if outlier_count == 0:
            continue

        cleaned[column] = cleaned[column].clip(lower=lower_bound, upper=upper_bound)
        report["outliers"]["columns"][column] = {
            "method": "IQR",
            "outlier_count": outlier_count,
            "lower_bound": float(lower_bound),
            "upper_bound": float(upper_bound),
            "strategy": "capped",
        }
        report["cleaning_summary"].append(
            f"Capped {outlier_count} outliers in {column} using IQR"
        )

    return cleaned


def preprocess_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    report = _empty_report(rows_before=int(len(df)), columns_count=int(len(df.columns)))

    cleaned = normalize_column_names(df)

    duplicates_removed = int(cleaned.duplicated().sum())
    if duplicates_removed:
        cleaned = cleaned.drop_duplicates().reset_index(drop=True)
        report["duplicates_removed"] = duplicates_removed
        report["cleaning_summary"].append(f"Removed {duplicates_removed} duplicate rows")

    cleaned = convert_dates(cleaned, report)
    cleaned = convert_numeric_columns(cleaned, report)
    report["type_inference"] = infer_column_types(cleaned)
    cleaned = handle_missing_values(cleaned, report)
    cleaned = handle_outliers(cleaned, report)

    report["rows_after"] = int(len(cleaned))
    report["columns_count"] = int(len(cleaned.columns))

    if not report["cleaning_summary"]:
        report["cleaning_summary"].append("No cleaning changes were required")

    return cleaned, report


def preprocess_csv(file_path: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    df = pd.read_csv(file_path)
    return preprocess_dataframe(df)


def preprocess_csv_bytes(content: bytes) -> tuple[pd.DataFrame, dict[str, Any]]:
    df = pd.read_csv(BytesIO(content))
    return preprocess_dataframe(df)
