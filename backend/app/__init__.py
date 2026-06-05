from decimal import Decimal

from flask import Flask, jsonify, request
from flask_cors import CORS
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import SQLAlchemyError

from app.db import check_database_connection, create_session, get_engine
from app.models import Department, Employee, ExpenseReport, Invoice, Vendor


def decimal_to_float(value):
    if value is None:
        return 0
    if isinstance(value, Decimal):
        return float(value)
    return value


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": [
                    "http://localhost:5173",
                    "http://127.0.0.1:5173",
                ]
            }
        },
    )

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "service": "backend"})

    @app.get("/api/db/health")
    def db_health():
        result = check_database_connection()

        if result["ok"]:
            return jsonify(
                {
                    "status": "ok",
                    "database": {
                        "connected": True,
                        "version": result["version"],
                        "url": result["database_url"],
                    },
                }
            )

        return (
            jsonify(
                {
                    "status": "error",
                    "database": {
                        "connected": False,
                        "url": result["database_url"],
                    },
                    "message": result["message"],
                    "error": result["error"],
                }
            ),
            503,
        )

    @app.get("/api/db/tables")
    def db_tables():
        try:
            inspector = inspect(get_engine())
            table_names = inspector.get_table_names()

            with get_engine().connect() as connection:
                tables = []
                for table_name in table_names:
                    columns = inspector.get_columns(table_name)
                    row_count = connection.exec_driver_sql(f"SELECT COUNT(*) FROM `{table_name}`").scalar_one()
                    tables.append(
                        {
                            "name": table_name,
                            "row_count": int(row_count),
                            "columns": [column["name"] for column in columns],
                        }
                    )

            return jsonify({"status": "ok", "tables": tables})
        except SQLAlchemyError as exc:
            return jsonify({"status": "error", "message": "Unable to inspect database tables.", "error": str(exc)}), 503

    @app.get("/api/db/summary")
    def db_summary():
        session = create_session()

        try:
            expense_total = session.scalar(select(func.coalesce(func.sum(ExpenseReport.amount), 0)))
            approved_expense_total = session.scalar(
                select(func.coalesce(func.sum(ExpenseReport.amount), 0)).where(ExpenseReport.status == "approved")
            )
            pending_expense_total = session.scalar(
                select(func.coalesce(func.sum(ExpenseReport.amount), 0)).where(ExpenseReport.status == "pending")
            )
            invoice_total = session.scalar(select(func.coalesce(func.sum(Invoice.total_amount), 0)))

            category_rows = session.execute(
                select(ExpenseReport.category, func.count(), func.coalesce(func.sum(ExpenseReport.amount), 0))
                .group_by(ExpenseReport.category)
                .order_by(ExpenseReport.category)
            ).all()

            status_rows = session.execute(
                select(ExpenseReport.status, func.count(), func.coalesce(func.sum(ExpenseReport.amount), 0))
                .group_by(ExpenseReport.status)
                .order_by(ExpenseReport.status)
            ).all()

            return jsonify(
                {
                    "status": "ok",
                    "summary": {
                        "department_count": session.scalar(select(func.count()).select_from(Department)),
                        "employee_count": session.scalar(select(func.count()).select_from(Employee)),
                        "vendor_count": session.scalar(select(func.count()).select_from(Vendor)),
                        "expense_count": session.scalar(select(func.count()).select_from(ExpenseReport)),
                        "invoice_count": session.scalar(select(func.count()).select_from(Invoice)),
                        "expense_total": decimal_to_float(expense_total),
                        "approved_expense_total": decimal_to_float(approved_expense_total),
                        "pending_expense_total": decimal_to_float(pending_expense_total),
                        "invoice_total": decimal_to_float(invoice_total),
                        "currency": "TWD",
                        "expenses_by_category": [
                            {"category": category, "count": count, "total": decimal_to_float(total)}
                            for category, count, total in category_rows
                        ],
                        "expenses_by_status": [
                            {"status": status, "count": count, "total": decimal_to_float(total)}
                            for status, count, total in status_rows
                        ],
                    },
                }
            )
        except SQLAlchemyError as exc:
            return jsonify({"status": "error", "message": "Unable to load database summary.", "error": str(exc)}), 503
        finally:
            session.close()

    @app.get("/api/employees")
    def employees():
        session = create_session()

        try:
            rows = (
                session.query(Employee)
                .join(Employee.department)
                .order_by(Employee.employee_code)
                .all()
            )
            return jsonify(
                {
                    "status": "ok",
                    "employees": [
                        {
                            "id": employee.id,
                            "employee_code": employee.employee_code,
                            "name": employee.name,
                            "department_id": employee.department_id,
                            "department_name": employee.department.name,
                            "title": employee.title,
                            "email": employee.email,
                            "location": employee.location,
                            "hire_date": employee.hire_date.isoformat(),
                        }
                        for employee in rows
                    ],
                }
            )
        finally:
            session.close()

    @app.get("/api/expenses")
    def expenses():
        session = create_session()

        try:
            limit = min(int(request.args.get("limit", 100)), 500)
            rows = (
                session.query(ExpenseReport)
                .join(ExpenseReport.employee)
                .outerjoin(ExpenseReport.vendor)
                .order_by(ExpenseReport.expense_date.desc(), ExpenseReport.id.desc())
                .limit(limit)
                .all()
            )
            return jsonify(
                {
                    "status": "ok",
                    "expenses": [
                        {
                            "id": expense.id,
                            "employee_id": expense.employee_id,
                            "employee_name": expense.employee.name,
                            "employee_code": expense.employee.employee_code,
                            "vendor_id": expense.vendor_id,
                            "vendor_name": expense.vendor.name if expense.vendor else None,
                            "expense_date": expense.expense_date.isoformat(),
                            "category": expense.category,
                            "amount": decimal_to_float(expense.amount),
                            "currency": expense.currency,
                            "status": expense.status,
                            "description": expense.description,
                        }
                        for expense in rows
                    ],
                }
            )
        finally:
            session.close()

    @app.get("/api/invoices")
    def invoices():
        session = create_session()

        try:
            rows = (
                session.query(Invoice)
                .outerjoin(Invoice.vendor)
                .order_by(Invoice.invoice_date.desc(), Invoice.id.desc())
                .all()
            )
            return jsonify(
                {
                    "status": "ok",
                    "invoices": [
                        {
                            "id": invoice.id,
                            "vendor_id": invoice.vendor_id,
                            "vendor_name": invoice.vendor.name if invoice.vendor else None,
                            "invoice_number": invoice.invoice_number,
                            "invoice_date": invoice.invoice_date.isoformat(),
                            "buyer_tax_id": invoice.buyer_tax_id,
                            "seller_tax_id": invoice.seller_tax_id,
                            "total_amount": decimal_to_float(invoice.total_amount),
                            "raw_text": invoice.raw_text,
                            "source_image_path": invoice.source_image_path,
                            "created_at": invoice.created_at.isoformat(),
                        }
                        for invoice in rows
                    ],
                }
            )
        finally:
            session.close()

    @app.post("/api/chat")
    def chat():
        payload = request.get_json(silent=True) or {}
        message = str(payload.get("message", "")).strip()
        model = str(payload.get("model", "gpt-4o")).strip() or "gpt-4o"

        if not message:
            return jsonify({"status": "error", "message": "Message is required."}), 400

        return jsonify(
            {
                "status": "ok",
                "model": model,
                "reply": f"我收到你的訊息了：{message}。下一階段會串接後端與 LLM。",
            }
        )

    return app
