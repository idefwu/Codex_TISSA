from __future__ import annotations

import json
import re
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from openai import OpenAIError
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from app.llm import LLMConfigurationError, get_openai_client
from app.models import AuditLog, Employee, ExpenseReport, Invoice, Vendor
from app.router import extract_json_object


ToolName = Literal["create_expense_report", "create_invoice"]


class DBWriteAgentError(RuntimeError):
    pass


class DBWriteExecutionError(DBWriteAgentError):
    pass


class DBWriteExtraction(BaseModel):
    tool: ToolName
    fields: dict[str, Any] = Field(default_factory=dict)


class CreateExpenseReportFields(BaseModel):
    model_config = ConfigDict(extra="ignore")

    employee_name: str | None = None
    employee_code: str | None = None
    vendor_name: str | None = None
    expense_date: date
    category: str
    amount: Decimal = Field(gt=0)
    currency: str = "TWD"
    description: str
    status: Literal["pending", "approved", "rejected"] = "pending"

    @field_validator("employee_name", "employee_code", "vendor_name", "category", "currency", "description", mode="before")
    @classmethod
    def normalize_text(cls, value):
        if value is None:
            return None
        value = str(value).strip()
        return value or None

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def require_employee_identifier(self):
        if not self.employee_name and not self.employee_code:
            raise ValueError("employee_name 或 employee_code 至少需要一個。")
        return self


class CreateInvoiceFields(BaseModel):
    model_config = ConfigDict(extra="ignore")

    vendor_name: str | None = None
    invoice_number: str
    invoice_date: date
    buyer_tax_id: str
    seller_tax_id: str
    total_amount: Decimal = Field(gt=0)
    raw_text: str | None = None
    source_image_path: str | None = None

    @field_validator(
        "vendor_name",
        "invoice_number",
        "buyer_tax_id",
        "seller_tax_id",
        "raw_text",
        "source_image_path",
        mode="before",
    )
    @classmethod
    def normalize_text(cls, value):
        if value is None:
            return None
        value = str(value).strip()
        return value or None


def jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [jsonable(item) for item in value]
    return value


def normalize_lookup_text(value: str | None) -> str:
    return re.sub(r"\s+", "", (value or "").strip().lower())


def find_employee(session, *, employee_name: str | None, employee_code: str | None) -> Employee | None:
    if employee_code:
        employee = (
            session.query(Employee)
            .filter(func.lower(Employee.employee_code) == employee_code.strip().lower())
            .one_or_none()
        )
        if employee:
            return employee

    if employee_name:
        normalized_name = normalize_lookup_text(employee_name)
        employees = session.query(Employee).all()

        for employee in employees:
            if normalize_lookup_text(employee.name) == normalized_name:
                return employee

        for employee in employees:
            if normalized_name and normalized_name in normalize_lookup_text(employee.name):
                return employee

    return None


def find_vendor(session, vendor_name: str | None) -> Vendor | None:
    if not vendor_name:
        return None

    normalized_name = normalize_lookup_text(vendor_name)
    vendors = session.query(Vendor).all()

    for vendor in vendors:
        if normalize_lookup_text(vendor.name) == normalized_name:
            return vendor

    for vendor in vendors:
        if normalized_name and normalized_name in normalize_lookup_text(vendor.name):
            return vendor

    return None


def extract_missing_fields(error: ValidationError, tool: ToolName, raw_fields: dict[str, Any]) -> list[str]:
    labels = {
        "employee_name": "employee_name 或 employee_code",
        "employee_code": "employee_name 或 employee_code",
        "expense_date": "expense_date",
        "category": "category",
        "amount": "amount",
        "description": "description",
        "invoice_number": "invoice_number",
        "invoice_date": "invoice_date",
        "buyer_tax_id": "buyer_tax_id",
        "seller_tax_id": "seller_tax_id",
        "total_amount": "total_amount",
    }
    missing = []

    for item in error.errors():
        loc = item.get("loc") or ()
        if item.get("type") == "missing" and loc:
            missing.append(labels.get(str(loc[0]), str(loc[0])))

    if tool == "create_expense_report" and not raw_fields.get("employee_name") and not raw_fields.get("employee_code"):
        missing.append("employee_name 或 employee_code")

    return sorted(set(missing))


def fallback_extract_db_write(message: str) -> DBWriteExtraction | None:
    date_match = re.search(r"\d{4}-\d{2}-\d{2}", message)
    amount_match = re.search(r"(?:金額\s*)?(\d+(?:\.\d+)?)\s*元?", message)

    if "發票" in message:
        number_match = re.search(r"(?:號碼|發票號碼)\s*([A-Za-z]{2}\d{8}|\w[\w-]+)", message)
        seller_match = re.search(r"賣方統編\s*(\d{8})", message)
        buyer_match = re.search(r"買方統編\s*(\d{8})", message)
        fields = {
            "invoice_number": number_match.group(1) if number_match else None,
            "invoice_date": date_match.group(0) if date_match else None,
            "seller_tax_id": seller_match.group(1) if seller_match else None,
            "buyer_tax_id": buyer_match.group(1) if buyer_match else None,
            "total_amount": amount_match.group(1) if amount_match else None,
            "raw_text": message,
        }
        return DBWriteExtraction(tool="create_invoice", fields={key: value for key, value in fields.items() if value})

    employee_match = re.search(r"幫\s+(.+?)\s+新增", message)
    vendor_match = re.search(r"廠商是\s*([^，,。]+)", message)
    category_match = re.search(r"類別\s*([^，,。]+)", message)
    description_match = re.search(r"說明是\s*([^。]+)", message)
    fields = {
        "employee_name": employee_match.group(1).strip() if employee_match else None,
        "vendor_name": vendor_match.group(1).strip() if vendor_match else None,
        "expense_date": date_match.group(0) if date_match else None,
        "category": category_match.group(1).strip() if category_match else None,
        "amount": amount_match.group(1) if amount_match else None,
        "description": description_match.group(1).strip() if description_match else None,
    }
    if any(fields.values()):
        return DBWriteExtraction(tool="create_expense_report", fields={key: value for key, value in fields.items() if value})

    return None


def extract_db_write_fields(*, message: str, model: str) -> tuple[DBWriteExtraction, bool]:
    system_prompt = """
你是 DB Agent Chat 的受控 DB Write 欄位抽取器。

你不能產生 SQL，也不能建議使用 INSERT / UPDATE / DELETE。
你只能根據使用者最新訊息，選擇一個白名單工具並抽取欄位。

可用工具：
1. create_expense_report
   - employee_name 或 employee_code
   - vendor_name nullable
   - expense_date: YYYY-MM-DD
   - category
   - amount
   - currency 預設 TWD
   - description
   - status 預設 pending

2. create_invoice
   - vendor_name nullable
   - invoice_number
   - invoice_date: YYYY-MM-DD
   - buyer_tax_id
   - seller_tax_id
   - total_amount
   - raw_text nullable
   - source_image_path nullable

只能輸出合法 JSON，不要 markdown，不要多餘文字。未知欄位請用 null 或省略。

JSON schema：
{
  "tool": "create_expense_report | create_invoice",
  "fields": {
    "...": "..."
  }
}
""".strip()

    try:
        client = get_openai_client()
        response = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message},
            ],
            temperature=0,
        )
        raw_text = (getattr(response, "output_text", "") or "").strip()
        return DBWriteExtraction.model_validate(extract_json_object(raw_text)), False
    except (LLMConfigurationError, OpenAIError, ValidationError, json.JSONDecodeError, ValueError, TypeError):
        fallback = fallback_extract_db_write(message)
        if fallback is None:
            raise DBWriteAgentError("無法從訊息中抽取可寫入的資料欄位。請補充要新增的是費用或發票。")
        return fallback, True


def build_followup_message(tool: ToolName, missing_fields: list[str], warnings: list[str] | None = None) -> str:
    tool_label = "費用資料" if tool == "create_expense_report" else "發票資料"
    field_list = "、".join(missing_fields)
    warning_text = f"\n\n另外需要注意：{'；'.join(warnings)}" if warnings else ""
    return f"我還不能建立{tool_label}，請補充：{field_list}。{warning_text}"


def prepare_db_write_request(*, session, message: str, model: str) -> dict[str, Any]:
    extraction, used_fallback = extract_db_write_fields(message=message, model=model)
    raw_fields = extraction.fields or {}

    try:
        if extraction.tool == "create_expense_report":
            fields = CreateExpenseReportFields.model_validate(raw_fields)
            employee = find_employee(
                session,
                employee_name=fields.employee_name,
                employee_code=fields.employee_code,
            )
            warnings = []
            if employee is None:
                return {
                    "source": "db-write-needs-more-info",
                    "assistant_content": build_followup_message(
                        extraction.tool,
                        ["可對應到現有員工的 employee_name 或 employee_code"],
                    ),
                    "metadata": {
                        "status": "needs_more_info",
                        "tool": extraction.tool,
                        "fields": jsonable(fields.model_dump(mode="python")),
                        "missing_fields": ["employee_name 或 employee_code"],
                        "warnings": [],
                        "fallback": used_fallback,
                    },
                }

            vendor = find_vendor(session, fields.vendor_name)
            if fields.vendor_name and vendor is None:
                warnings.append(f"找不到廠商「{fields.vendor_name}」，確認後會以 vendor_id=null 寫入。")

            payload = fields.model_dump(mode="python")
            return {
                "source": "db-write-pending",
                "assistant_content": "我已整理出一筆待確認寫入資料。請確認內容後，再按「確認寫入」。",
                "metadata": {
                    "status": "pending_confirmation",
                    "tool": extraction.tool,
                    "fields": jsonable(payload),
                    "resolved": {
                        "employee_id": employee.id,
                        "employee_name": employee.name,
                        "employee_code": employee.employee_code,
                        "vendor_id": vendor.id if vendor else None,
                        "vendor_name": vendor.name if vendor else fields.vendor_name,
                    },
                    "warnings": warnings,
                    "fallback": used_fallback,
                },
            }

        fields = CreateInvoiceFields.model_validate(raw_fields)
        vendor = find_vendor(session, fields.vendor_name)
        warnings = []
        if fields.vendor_name and vendor is None:
            warnings.append(f"找不到廠商「{fields.vendor_name}」，確認後會以 vendor_id=null 寫入。")

        return {
            "source": "db-write-pending",
            "assistant_content": "我已整理出一張待確認寫入的發票資料。請確認內容後，再按「確認寫入」。",
            "metadata": {
                "status": "pending_confirmation",
                "tool": extraction.tool,
                "fields": jsonable(fields.model_dump(mode="python")),
                "resolved": {
                    "vendor_id": vendor.id if vendor else None,
                    "vendor_name": vendor.name if vendor else fields.vendor_name,
                },
                "warnings": warnings,
                "fallback": used_fallback,
            },
        }
    except ValidationError as exc:
        missing_fields = extract_missing_fields(exc, extraction.tool, raw_fields)
        if not missing_fields:
            missing_fields = ["欄位格式需要修正"]
        return {
            "source": "db-write-needs-more-info",
            "assistant_content": build_followup_message(extraction.tool, missing_fields),
            "metadata": {
                "status": "needs_more_info",
                "tool": extraction.tool,
                "fields": jsonable(raw_fields),
                "missing_fields": missing_fields,
                "warnings": [],
                "fallback": used_fallback,
            },
        }


def execute_confirmed_db_write(*, session, db_write: dict[str, Any], source_message_id: int) -> dict[str, Any]:
    if db_write.get("status") != "pending_confirmation":
        raise DBWriteExecutionError("這筆寫入請求不是待確認狀態，無法執行。")

    tool = db_write.get("tool")
    fields = db_write.get("fields") or {}
    resolved = db_write.get("resolved") or {}

    try:
        if tool == "create_expense_report":
            payload = CreateExpenseReportFields.model_validate(fields)
            employee = session.get(Employee, resolved.get("employee_id"))
            if employee is None:
                employee = find_employee(
                    session,
                    employee_name=payload.employee_name,
                    employee_code=payload.employee_code,
                )
            if employee is None:
                raise DBWriteExecutionError("找不到可寫入費用的員工資料。")

            vendor = session.get(Vendor, resolved.get("vendor_id")) if resolved.get("vendor_id") else None
            expense = ExpenseReport(
                employee_id=employee.id,
                vendor_id=vendor.id if vendor else None,
                expense_date=payload.expense_date,
                category=payload.category,
                amount=payload.amount,
                currency=payload.currency,
                status=payload.status,
                description=payload.description,
            )
            session.add(expense)
            session.flush()

            result = {
                "entity_type": "expense_reports",
                "entity_id": expense.id,
                "tool": tool,
                "summary": f"已新增費用資料 ID：{expense.id}",
                "record": {
                    "id": expense.id,
                    "employee_id": employee.id,
                    "employee_name": employee.name,
                    "vendor_id": vendor.id if vendor else None,
                    "vendor_name": vendor.name if vendor else resolved.get("vendor_name"),
                    "expense_date": payload.expense_date.isoformat(),
                    "category": payload.category,
                    "amount": float(payload.amount),
                    "currency": payload.currency,
                    "status": payload.status,
                    "description": payload.description,
                },
            }
        elif tool == "create_invoice":
            payload = CreateInvoiceFields.model_validate(fields)
            existing_invoice = (
                session.query(Invoice)
                .filter(Invoice.invoice_number == payload.invoice_number)
                .one_or_none()
            )
            if existing_invoice:
                raise DBWriteExecutionError(f"發票號碼 {payload.invoice_number} 已存在，未重複寫入。")

            vendor = session.get(Vendor, resolved.get("vendor_id")) if resolved.get("vendor_id") else None
            invoice = Invoice(
                vendor_id=vendor.id if vendor else None,
                invoice_number=payload.invoice_number,
                invoice_date=payload.invoice_date,
                buyer_tax_id=payload.buyer_tax_id,
                seller_tax_id=payload.seller_tax_id,
                total_amount=payload.total_amount,
                raw_text=payload.raw_text or "",
                source_image_path=payload.source_image_path,
            )
            session.add(invoice)
            session.flush()

            result = {
                "entity_type": "invoices",
                "entity_id": invoice.id,
                "tool": tool,
                "summary": f"已新增發票資料 ID：{invoice.id}",
                "record": {
                    "id": invoice.id,
                    "vendor_id": vendor.id if vendor else None,
                    "vendor_name": vendor.name if vendor else resolved.get("vendor_name"),
                    "invoice_number": payload.invoice_number,
                    "invoice_date": payload.invoice_date.isoformat(),
                    "buyer_tax_id": payload.buyer_tax_id,
                    "seller_tax_id": payload.seller_tax_id,
                    "total_amount": float(payload.total_amount),
                    "raw_text": payload.raw_text,
                    "source_image_path": payload.source_image_path,
                },
            }
        else:
            raise DBWriteExecutionError("不支援的 DB Write 工具。")

        audit_detail = {
            "source_message_id": source_message_id,
            "tool": tool,
            "fields": fields,
            "resolved": resolved,
            "result": result,
        }
        session.add(
            AuditLog(
                action=tool,
                entity_type=result["entity_type"],
                entity_id=result["entity_id"],
                detail=json.dumps(audit_detail, ensure_ascii=False),
            )
        )
        return result
    except SQLAlchemyError as exc:
        root_error = exc.__cause__ or exc
        raise DBWriteExecutionError(f"資料庫寫入失敗：{root_error}") from exc
