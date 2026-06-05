from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from openai import OpenAIError
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from app.db import get_engine
from app.llm import LLMConfigurationError, LLMRequestError, get_openai_client
from app.router import extract_json_object


ALLOWED_SQL_TABLES = {
    "departments",
    "employees",
    "vendors",
    "expense_reports",
    "invoices",
}
MAX_SQL_ROWS = 50
FORBIDDEN_SQL_KEYWORDS = (
    "ALTER",
    "CALL",
    "CREATE",
    "DELETE",
    "DUMPFILE",
    "DROP",
    "EXEC",
    "EXECUTE",
    "GRANT",
    "INTO",
    "INSERT",
    "LOAD_FILE",
    "LOAD",
    "LOCK",
    "MERGE",
    "OUTFILE",
    "REPLACE",
    "REVOKE",
    "SET",
    "SHOW",
    "SLEEP",
    "TRUNCATE",
    "UNION",
    "UNLOCK",
    "UPDATE",
    "USE",
    "BENCHMARK",
)


class SQLAgentError(RuntimeError):
    def __init__(self, message: str, *, stage: str = "sql_agent"):
        super().__init__(message)
        self.stage = stage


class SQLValidationError(SQLAgentError):
    def __init__(self, message: str):
        super().__init__(message, stage="sql_validation")


class SQLGeneration(BaseModel):
    sql: str = Field(min_length=1)
    reason: str = ""


@dataclass
class SQLExecutionResult:
    columns: list[str]
    rows: list[dict[str, Any]]


def serialize_sql_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def strip_sql_code_fence(sql: str) -> str:
    cleaned = sql.strip()
    fenced_match = re.search(r"```(?:sql)?\s*(.*?)\s*```", cleaned, re.IGNORECASE | re.DOTALL)
    if fenced_match:
        cleaned = fenced_match.group(1).strip()
    return cleaned


def strip_string_literals(sql: str) -> str:
    return re.sub(r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"", "''", sql)


def normalize_identifier(identifier: str) -> str:
    value = identifier.strip().strip("`").strip('"')
    if "." in value:
        value = value.split(".")[-1]
    return value.lower()


def get_schema_snapshot() -> list[dict[str, Any]]:
    inspector = inspect(get_engine())
    tables = []

    for table_name in sorted(ALLOWED_SQL_TABLES):
        if not inspector.has_table(table_name):
            continue

        columns = []
        for column in inspector.get_columns(table_name):
            columns.append(
                {
                    "name": column["name"],
                    "type": str(column["type"]),
                    "nullable": bool(column.get("nullable")),
                    "primary_key": bool(column.get("primary_key")),
                }
            )

        foreign_keys = []
        for foreign_key in inspector.get_foreign_keys(table_name):
            if not foreign_key.get("referred_table"):
                continue
            foreign_keys.append(
                {
                    "columns": foreign_key.get("constrained_columns", []),
                    "referred_table": foreign_key["referred_table"],
                    "referred_columns": foreign_key.get("referred_columns", []),
                }
            )

        tables.append(
            {
                "name": table_name,
                "columns": columns,
                "foreign_keys": foreign_keys,
            }
        )

    return tables


def build_schema_text(schema: list[dict[str, Any]]) -> str:
    lines = [
        "可查詢的資料表與欄位如下，只能使用這些資料表：",
        "",
    ]

    for table in schema:
        lines.append(f"Table: {table['name']}")
        for column in table["columns"]:
            nullable = "nullable" if column["nullable"] else "required"
            pk = ", primary key" if column["primary_key"] else ""
            lines.append(f"- {column['name']} ({column['type']}, {nullable}{pk})")

        if table["foreign_keys"]:
            lines.append("Relationships:")
            for foreign_key in table["foreign_keys"]:
                left = ", ".join(foreign_key["columns"])
                right = ", ".join(foreign_key["referred_columns"])
                lines.append(f"- {table['name']}.{left} -> {foreign_key['referred_table']}.{right}")
        lines.append("")

    lines.extend(
        [
            "中文業務詞彙對照：",
            "- 資訊部 / 工程部 / 技術部：departments.name = 'Engineering'",
            "- 財務部：departments.name = 'Finance'",
            "- 人資部 / 人力資源：departments.name = 'Human Resources'",
            "- 業務部 / 銷售部：departments.name = 'Sales'",
            "- 未核准通常代表 expense_reports.status <> 'approved'，包含 pending 或 rejected。",
            "- 費用金額使用 expense_reports.amount；發票金額使用 invoices.total_amount。",
        ]
    )
    return "\n".join(lines)


def generate_sql(*, question: str, model: str) -> SQLGeneration:
    schema_text = build_schema_text(get_schema_snapshot())
    system_prompt = f"""
你是課堂 Demo 用的安全 MySQL SQL 產生器。

請根據使用者問題與 schema 產生一段 MySQL SELECT 查詢。

嚴格規則：
- 只能輸出合法 JSON，不要 markdown，不要多餘文字。
- SQL 必須只能是 SELECT。
- SQL 必須包含 LIMIT，最多 LIMIT {MAX_SQL_ROWS}。
- 不要產生 INSERT、UPDATE、DELETE、DROP、ALTER、TRUNCATE、CREATE 等寫入或 DDL。
- 不要使用多語句，不要使用分號。
- 只能查詢 schema 中列出的資料表。
- 欄位名稱請使用英文資料表欄位，不要自行發明欄位。

輸出 JSON schema：
{{
  "sql": "SELECT ... LIMIT 50",
  "reason": "簡短說明為何這樣查"
}}

{schema_text}
""".strip()

    try:
        client = get_openai_client()
        response = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
            temperature=0,
        )
        raw_text = (getattr(response, "output_text", "") or "").strip()
        parsed = extract_json_object(raw_text)
        return SQLGeneration.model_validate(parsed)
    except LLMConfigurationError:
        raise
    except (OpenAIError, ValidationError, json.JSONDecodeError, ValueError, TypeError) as exc:
        raise LLMRequestError(f"SQL generation failed: {exc}") from exc


def validate_select_sql(sql: str) -> str:
    safe_sql = strip_sql_code_fence(sql)

    if not safe_sql:
        raise SQLValidationError("SQL 為空，無法執行。")

    if ";" in safe_sql:
        raise SQLValidationError("基於安全限制，不允許多語句 SQL 或分號。")

    if re.search(r"(--|#|/\*|\*/)", safe_sql):
        raise SQLValidationError("基於安全限制，不允許 SQL 註解。")

    sql_without_literals = strip_string_literals(safe_sql)
    normalized = re.sub(r"\s+", " ", sql_without_literals).strip()
    normalized_upper = normalized.upper()

    if not re.match(r"^SELECT\b", normalized_upper):
        raise SQLValidationError("只允許 SELECT 查詢。")

    forbidden_pattern = r"\b(" + "|".join(FORBIDDEN_SQL_KEYWORDS) + r")\b"
    if re.search(forbidden_pattern, normalized_upper):
        raise SQLValidationError("SQL 包含不允許的資料庫操作。")

    referenced_tables = {
        normalize_identifier(match.group(1))
        for match in re.finditer(r"\b(?:FROM|JOIN)\s+([`\"\w.]+)", normalized_upper, re.IGNORECASE)
    }
    unknown_tables = referenced_tables - ALLOWED_SQL_TABLES
    if unknown_tables:
        raise SQLValidationError(f"SQL 只能查詢允許的 demo tables：{', '.join(sorted(ALLOWED_SQL_TABLES))}。")

    if not referenced_tables:
        raise SQLValidationError("SQL 必須查詢至少一個允許的資料表。")

    limit_match = re.search(r"\bLIMIT\s+(\d+)\b", normalized_upper)
    if limit_match:
        limit_value = int(limit_match.group(1))
        if limit_value <= 0:
            raise SQLValidationError("LIMIT 必須大於 0。")
        if limit_value > MAX_SQL_ROWS:
            safe_sql = re.sub(r"\bLIMIT\s+\d+\b", f"LIMIT {MAX_SQL_ROWS}", safe_sql, count=1, flags=re.IGNORECASE)
    elif re.search(r"\bLIMIT\b", normalized_upper):
        raise SQLValidationError("LIMIT 必須是明確數字。")
    else:
        safe_sql = f"{safe_sql.rstrip()} LIMIT {MAX_SQL_ROWS}"

    return safe_sql


def execute_sql(sql: str) -> SQLExecutionResult:
    try:
        with get_engine().connect() as connection:
            result = connection.execute(text(sql))
            rows = [dict(row) for row in result.mappings().all()]
            columns = list(result.keys())
    except SQLAlchemyError as exc:
        root_error = exc.__cause__ or exc
        raise SQLAgentError(f"資料庫查詢失敗：{root_error}", stage="sql_execution") from exc

    serialized_rows = [
        {key: serialize_sql_value(value) for key, value in row.items()}
        for row in rows
    ]
    return SQLExecutionResult(columns=columns, rows=serialized_rows)


def synthesize_answer(
    *,
    question: str,
    sql: str,
    result: SQLExecutionResult,
    model: str,
    temperature: float,
) -> str:
    if not result.rows:
        return "查詢已完成，但目前沒有找到符合條件的資料。"

    payload = {
        "question": question,
        "sql": sql,
        "columns": result.columns,
        "rows": result.rows,
        "row_count": len(result.rows),
    }
    system_prompt = """
你是 DB Agent Chat 的答案整理器。
請根據 SQL 查詢結果，用繁體中文回答使用者問題。
回答要精簡、清楚，可以用 Markdown 表格或條列。
不要聲稱查到資料以外的內容，不要輸出完整 JSON。
""".strip()

    try:
        client = get_openai_client()
        response = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            temperature=temperature,
        )
        content = (getattr(response, "output_text", "") or "").strip()
        if content:
            return content
    except (OpenAIError, LLMConfigurationError):
        pass

    return f"查詢完成，共找到 {len(result.rows)} 筆資料。你可以展開下方查詢結果表格查看明細。"


def run_sql_agent(*, question: str, model: str, temperature: float) -> dict[str, Any]:
    generation = generate_sql(question=question, model=model)
    safe_sql = validate_select_sql(generation.sql)
    execution_result = execute_sql(safe_sql)
    answer = synthesize_answer(
        question=question,
        sql=safe_sql,
        result=execution_result,
        model=model,
        temperature=temperature,
    )

    return {
        "sql": safe_sql,
        "raw_sql": generation.sql,
        "reason": generation.reason,
        "columns": execution_result.columns,
        "rows": execution_result.rows,
        "row_count": len(execution_result.rows),
        "answer": answer,
        "max_rows": MAX_SQL_ROWS,
        "allowed_tables": sorted(ALLOWED_SQL_TABLES),
    }
