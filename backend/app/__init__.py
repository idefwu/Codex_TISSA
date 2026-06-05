from decimal import Decimal
from datetime import datetime

from flask import Flask, jsonify, request
from flask_cors import CORS
from sqlalchemy import desc, func, inspect, select
from sqlalchemy.exc import SQLAlchemyError

from app.db import check_database_connection, create_session, get_engine
from app.llm import (
    LLMConfigurationError,
    LLMRequestError,
    check_llm_connection,
    clamp_temperature,
    generate_llm_reply,
    normalize_model,
    normalize_system_prompt,
)
from app.models import ChatMessage, ChatRoom, Department, Employee, ExpenseReport, Invoice, Vendor


def decimal_to_float(value):
    if value is None:
        return 0
    if isinstance(value, Decimal):
        return float(value)
    return value


def serialize_chat_message(message):
    return {
        "id": message.id,
        "room_id": message.room_id,
        "role": message.role,
        "content": message.content,
        "metadata_json": message.metadata_json,
        "model": message.model,
        "created_at": message.created_at.isoformat(),
    }


def serialize_chat_room(room):
    return {
        "id": room.id,
        "title": room.title,
        "created_at": room.created_at.isoformat(),
        "updated_at": room.updated_at.isoformat(),
        "message_count": len(room.messages),
    }


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

    @app.get("/api/llm/health")
    def llm_health():
        result = check_llm_connection()

        if result["ok"]:
            return jsonify(
                {
                    "status": "ok",
                    "llm": {
                        "configured": True,
                        "reachable": True,
                        "masked_key": result["masked_key"],
                        "sample_model": result.get("sample_model"),
                    },
                    "message": result["message"],
                }
            )

        status_code = 503 if result["status"] == "api_error" else 400
        return (
            jsonify(
                {
                    "status": "error",
                    "llm": {
                        "configured": bool(result.get("masked_key")),
                        "reachable": False,
                        "masked_key": result.get("masked_key", ""),
                    },
                    "message": result["message"],
                    "error": result.get("error", result["message"]),
                }
            ),
            status_code,
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

    @app.get("/api/chat/rooms")
    def chat_rooms():
        session = create_session()

        try:
            rooms = session.query(ChatRoom).order_by(ChatRoom.updated_at.desc(), ChatRoom.id.desc()).all()
            return jsonify({"status": "ok", "rooms": [serialize_chat_room(room) for room in rooms]})
        except SQLAlchemyError as exc:
            return jsonify({"status": "error", "message": "Unable to load chat rooms.", "error": str(exc)}), 503
        finally:
            session.close()

    @app.post("/api/chat/rooms")
    def create_chat_room():
        payload = request.get_json(silent=True) or {}
        title = str(payload.get("title", "")).strip() or "新聊天室"
        session = create_session()

        try:
            room = ChatRoom(title=title)
            session.add(room)
            session.commit()
            session.refresh(room)
            return jsonify({"status": "ok", "room": serialize_chat_room(room)}), 201
        except SQLAlchemyError as exc:
            session.rollback()
            return jsonify({"status": "error", "message": "Unable to create chat room.", "error": str(exc)}), 503
        finally:
            session.close()

    @app.patch("/api/chat/rooms/<int:room_id>")
    def update_chat_room(room_id):
        payload = request.get_json(silent=True) or {}
        title = str(payload.get("title", "")).strip()

        if not title:
            return jsonify({"status": "error", "message": "Title is required."}), 400

        session = create_session()

        try:
            room = session.get(ChatRoom, room_id)
            if room is None:
                return jsonify({"status": "error", "message": "Chat room not found."}), 404

            room.title = title
            room.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(room)
            return jsonify({"status": "ok", "room": serialize_chat_room(room)})
        except SQLAlchemyError as exc:
            session.rollback()
            return jsonify({"status": "error", "message": "Unable to update chat room.", "error": str(exc)}), 503
        finally:
            session.close()

    @app.delete("/api/chat/rooms/<int:room_id>")
    def delete_chat_room(room_id):
        session = create_session()

        try:
            room = session.get(ChatRoom, room_id)
            if room is None:
                return jsonify({"status": "error", "message": "Chat room not found."}), 404

            session.delete(room)
            session.commit()
            return jsonify({"status": "ok", "deleted_id": room_id})
        except SQLAlchemyError as exc:
            session.rollback()
            return jsonify({"status": "error", "message": "Unable to delete chat room.", "error": str(exc)}), 503
        finally:
            session.close()

    @app.get("/api/chat/rooms/<int:room_id>/messages")
    def chat_room_messages(room_id):
        session = create_session()

        try:
            room = session.get(ChatRoom, room_id)
            if room is None:
                return jsonify({"status": "error", "message": "Chat room not found."}), 404

            messages = (
                session.query(ChatMessage)
                .filter(ChatMessage.room_id == room_id)
                .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
                .all()
            )
            return jsonify(
                {
                    "status": "ok",
                    "room": serialize_chat_room(room),
                    "messages": [serialize_chat_message(message) for message in messages],
                }
            )
        except SQLAlchemyError as exc:
            return jsonify({"status": "error", "message": "Unable to load chat messages.", "error": str(exc)}), 503
        finally:
            session.close()

    @app.post("/api/chat/rooms/<int:room_id>/messages")
    def create_chat_room_message(room_id):
        payload = request.get_json(silent=True) or {}
        message = str(payload.get("message", "")).strip()
        model = normalize_model(payload.get("model"))
        temperature = clamp_temperature(payload.get("temperature"))
        system_prompt = normalize_system_prompt(payload.get("systemPrompt"))
        try:
            memory_rounds = min(max(int(payload.get("memoryRounds", 5)), 1), 10)
        except (TypeError, ValueError):
            memory_rounds = 5

        if not message:
            return jsonify({"status": "error", "message": "Message is required."}), 400

        session = create_session()

        try:
            room = session.get(ChatRoom, room_id)
            if room is None:
                return jsonify({"status": "error", "message": "Chat room not found."}), 404

            controls = {
                "model": model,
                "temperature": temperature,
                "system_prompt": system_prompt,
                "memory_rounds": memory_rounds,
                "tools": payload.get("tools", {}),
            }
            history_rows = (
                session.query(ChatMessage)
                .filter(ChatMessage.room_id == room_id)
                .order_by(desc(ChatMessage.created_at), desc(ChatMessage.id))
                .limit(memory_rounds * 2)
                .all()
            )
            history = [
                {
                    "role": history_message.role,
                    "content": history_message.content,
                }
                for history_message in reversed(history_rows)
            ]
            user_message = ChatMessage(
                room_id=room.id,
                role="user",
                content=message,
                metadata_json={"source": "frontend", "controls": controls, "llm_status": "submitted"},
                model=model,
            )

            room.updated_at = datetime.utcnow()
            session.add(user_message)
            session.commit()
            session.refresh(room)
            session.refresh(user_message)

            try:
                llm_reply = generate_llm_reply(
                    history=history,
                    message=message,
                    model=model,
                    system_prompt=system_prompt,
                    temperature=temperature,
                )
            except LLMConfigurationError as exc:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": "OpenAI API key is not configured.",
                            "error": str(exc),
                            "room": serialize_chat_room(room),
                            "messages": [serialize_chat_message(user_message)],
                        }
                    ),
                    400,
                )
            except LLMRequestError as exc:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": "OpenAI API request failed.",
                            "error": str(exc),
                            "room": serialize_chat_room(room),
                            "messages": [serialize_chat_message(user_message)],
                        }
                    ),
                    502,
                )

            assistant_message = ChatMessage(
                room_id=room.id,
                role="assistant",
                content=llm_reply.content,
                metadata_json={"source": "openai", "controls": controls},
                model=llm_reply.model,
            )
            room.updated_at = datetime.utcnow()
            session.add(assistant_message)
            session.commit()
            session.refresh(room)
            session.refresh(assistant_message)

            return jsonify(
                {
                    "status": "ok",
                    "room": serialize_chat_room(room),
                    "messages": [
                        serialize_chat_message(user_message),
                        serialize_chat_message(assistant_message),
                    ],
                }
            ), 201
        except SQLAlchemyError as exc:
            session.rollback()
            return jsonify({"status": "error", "message": "Unable to save chat message.", "error": str(exc)}), 503
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
                "reply": f"後端已收到你的訊息：{message}。下一階段會由 LLM 回覆。",
            }
        )

    return app
