import sys
from datetime import date
from decimal import Decimal
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db import create_session
from app.models import (
    AuditLog,
    ChatMessage,
    ChatRoom,
    Department,
    Employee,
    ExpenseReport,
    Invoice,
    Vendor,
)


DEPARTMENTS = [
    {"name": "Finance", "manager_name": "Grace Huang"},
    {"name": "Human Resources", "manager_name": "Leo Chen"},
    {"name": "Sales", "manager_name": "Ivy Lin"},
    {"name": "Engineering", "manager_name": "Oscar Wang"},
]

EMPLOYEES = [
    ("E001", "Amy Chen", "Finance", "Finance Manager", "amy.chen@example.com", "Taipei", date(2020, 2, 10)),
    ("E002", "Brian Lee", "Finance", "Accountant", "brian.lee@example.com", "Taipei", date(2021, 6, 1)),
    ("E003", "Cathy Wu", "Finance", "Financial Analyst", "cathy.wu@example.com", "Hsinchu", date(2022, 3, 15)),
    ("E004", "David Lin", "Human Resources", "HR Specialist", "david.lin@example.com", "Taipei", date(2019, 8, 20)),
    ("E005", "Emily Tsai", "Human Resources", "Recruiter", "emily.tsai@example.com", "Taichung", date(2023, 1, 5)),
    ("E006", "Frank Ho", "Sales", "Sales Manager", "frank.ho@example.com", "Taipei", date(2018, 11, 12)),
    ("E007", "Gina Yang", "Sales", "Account Executive", "gina.yang@example.com", "Kaohsiung", date(2022, 7, 18)),
    ("E008", "Henry Kao", "Sales", "Sales Operations", "henry.kao@example.com", "Taipei", date(2021, 9, 9)),
    ("E009", "Irene Liu", "Engineering", "Engineering Manager", "irene.liu@example.com", "Hsinchu", date(2017, 5, 22)),
    ("E010", "Jack Chang", "Engineering", "Backend Engineer", "jack.chang@example.com", "Taipei", date(2020, 10, 6)),
    ("E011", "Kelly Hsu", "Engineering", "Frontend Engineer", "kelly.hsu@example.com", "Taichung", date(2022, 12, 1)),
    ("E012", "Mark Sun", "Engineering", "Data Engineer", "mark.sun@example.com", "Hsinchu", date(2023, 4, 17)),
]

VENDORS = [
    ("CloudHub Ltd.", "24561234", "billing@cloudhub.example.com"),
    ("TravelGo Agency", "53219876", "service@travelgo.example.com"),
    ("OfficePro Supplies", "19876543", "orders@officepro.example.com"),
    ("MealBox Catering", "30987654", "contact@mealbox.example.com"),
    ("DesignWorks Studio", "27893456", "hello@designworks.example.com"),
    ("DataSense Analytics", "66781234", "finance@datasense.example.com"),
    ("SecureIT Services", "71562398", "support@secureit.example.com"),
    ("EventSpace Co.", "88451267", "booking@eventspace.example.com"),
]

EXPENSES = [
    ("E001", "CloudHub Ltd.", date(2026, 1, 5), "Software", "12800.00", "TWD", "approved", "Monthly cloud subscription"),
    ("E002", "OfficePro Supplies", date(2026, 1, 8), "Office", "3460.00", "TWD", "approved", "Printer paper and toner"),
    ("E003", "DataSense Analytics", date(2026, 1, 12), "Software", "22000.00", "TWD", "pending", "Analytics platform trial"),
    ("E004", "MealBox Catering", date(2026, 1, 15), "Meal", "5400.00", "TWD", "approved", "Training lunch"),
    ("E005", "EventSpace Co.", date(2026, 1, 18), "Event", "18000.00", "TWD", "approved", "Recruiting event venue"),
    ("E006", "TravelGo Agency", date(2026, 1, 22), "Travel", "15600.00", "TWD", "approved", "Client visit flights"),
    ("E007", None, date(2026, 1, 24), "Transportation", "920.00", "TWD", "approved", "Taxi to client site"),
    ("E008", "DesignWorks Studio", date(2026, 1, 26), "Marketing", "30000.00", "TWD", "pending", "Sales deck redesign"),
    ("E009", "SecureIT Services", date(2026, 1, 28), "Security", "42000.00", "TWD", "approved", "Security audit"),
    ("E010", "CloudHub Ltd.", date(2026, 2, 3), "Software", "13100.00", "TWD", "approved", "Cloud usage overage"),
    ("E011", "OfficePro Supplies", date(2026, 2, 5), "Office", "2800.00", "TWD", "rejected", "Duplicate stationery claim"),
    ("E012", "DataSense Analytics", date(2026, 2, 7), "Software", "24000.00", "TWD", "approved", "Data pipeline service"),
    ("E001", "MealBox Catering", date(2026, 2, 10), "Meal", "3600.00", "TWD", "approved", "Finance team dinner"),
    ("E002", None, date(2026, 2, 11), "Transportation", "680.00", "TWD", "approved", "MRT and taxi reimbursement"),
    ("E003", "TravelGo Agency", date(2026, 2, 14), "Travel", "19200.00", "TWD", "pending", "Regional finance workshop"),
    ("E004", "EventSpace Co.", date(2026, 2, 17), "Event", "21000.00", "TWD", "approved", "Employee engagement event"),
    ("E005", "DesignWorks Studio", date(2026, 2, 20), "Marketing", "9600.00", "TWD", "approved", "Employer brand assets"),
    ("E006", "MealBox Catering", date(2026, 2, 22), "Meal", "7200.00", "TWD", "approved", "Customer lunch"),
    ("E007", "TravelGo Agency", date(2026, 2, 25), "Travel", "18400.00", "TWD", "approved", "Kaohsiung customer trip"),
    ("E008", None, date(2026, 2, 26), "Transportation", "1250.00", "TWD", "approved", "Client meeting taxi"),
    ("E009", "CloudHub Ltd.", date(2026, 3, 2), "Software", "14500.00", "TWD", "approved", "Engineering cloud credits"),
    ("E010", "SecureIT Services", date(2026, 3, 4), "Security", "36000.00", "TWD", "pending", "Penetration testing retainer"),
    ("E011", "OfficePro Supplies", date(2026, 3, 6), "Office", "4100.00", "TWD", "approved", "Monitor arms"),
    ("E012", "DataSense Analytics", date(2026, 3, 8), "Software", "26500.00", "TWD", "approved", "Data warehouse connector"),
    ("E001", "TravelGo Agency", date(2026, 3, 10), "Travel", "8800.00", "TWD", "approved", "Finance conference hotel"),
    ("E002", "MealBox Catering", date(2026, 3, 11), "Meal", "2300.00", "TWD", "approved", "Audit prep dinner"),
    ("E003", None, date(2026, 3, 13), "Training", "12000.00", "TWD", "pending", "Finance modeling course"),
    ("E004", "OfficePro Supplies", date(2026, 3, 15), "Office", "1500.00", "TWD", "approved", "HR interview supplies"),
    ("E005", "EventSpace Co.", date(2026, 3, 18), "Event", "25000.00", "TWD", "approved", "Campus recruiting booth"),
    ("E006", "DesignWorks Studio", date(2026, 3, 20), "Marketing", "16800.00", "TWD", "approved", "Customer case study layout"),
]

INVOICES = [
    ("CloudHub Ltd.", "CH-2026-001", date(2026, 1, 31), "12345678", "24561234", "25900.00", "CloudHub invoice CH-2026-001 total 25900 TWD", None),
    ("OfficePro Supplies", "OP-2026-018", date(2026, 2, 8), "12345678", "19876543", "6260.00", "OfficePro invoice for supplies total 6260 TWD", None),
    ("TravelGo Agency", "TG-2026-077", date(2026, 2, 28), "12345678", "53219876", "53200.00", "TravelGo February travel invoice total 53200 TWD", "uploads/invoices/tg-2026-077.jpg"),
    ("SecureIT Services", "SI-2026-009", date(2026, 3, 5), "12345678", "71562398", "78000.00", "SecureIT security services invoice total 78000 TWD", None),
    (None, "MANUAL-2026-001", date(2026, 3, 21), "12345678", "00000000", "3200.00", "Manual invoice entered from user provided image", "uploads/invoices/manual-2026-001.jpg"),
]


def clear_tables(session) -> None:
    for model in (AuditLog, ChatMessage, ChatRoom, Invoice, ExpenseReport, Employee, Vendor, Department):
        session.query(model).delete()
    session.flush()


def main() -> None:
    session = create_session()

    try:
        clear_tables(session)

        departments = {item["name"]: Department(**item) for item in DEPARTMENTS}
        session.add_all(departments.values())
        session.flush()

        employees = {}
        for code, name, department_name, title, email, location, hire_date in EMPLOYEES:
            employee = Employee(
                employee_code=code,
                name=name,
                department_id=departments[department_name].id,
                title=title,
                email=email,
                location=location,
                hire_date=hire_date,
            )
            employees[code] = employee
            session.add(employee)
        session.flush()

        vendors = {}
        for name, tax_id, contact_email in VENDORS:
            vendor = Vendor(name=name, tax_id=tax_id, contact_email=contact_email)
            vendors[name] = vendor
            session.add(vendor)
        session.flush()

        for employee_code, vendor_name, expense_date, category, amount, currency, status, description in EXPENSES:
            session.add(
                ExpenseReport(
                    employee_id=employees[employee_code].id,
                    vendor_id=vendors[vendor_name].id if vendor_name else None,
                    expense_date=expense_date,
                    category=category,
                    amount=Decimal(amount),
                    currency=currency,
                    status=status,
                    description=description,
                )
            )

        for vendor_name, number, invoice_date, buyer_tax_id, seller_tax_id, total_amount, raw_text, source_path in INVOICES:
            session.add(
                Invoice(
                    vendor_id=vendors[vendor_name].id if vendor_name else None,
                    invoice_number=number,
                    invoice_date=invoice_date,
                    buyer_tax_id=buyer_tax_id,
                    seller_tax_id=seller_tax_id,
                    total_amount=Decimal(total_amount),
                    raw_text=raw_text,
                    source_image_path=source_path,
                )
            )

        room = ChatRoom(title="Finance demo room")
        session.add(room)
        session.flush()
        session.add_all(
            [
                ChatMessage(
                    room_id=room.id,
                    role="user",
                    content="Show this month's expenses",
                    metadata_json={"source": "seed"},
                    model=None,
                ),
                ChatMessage(
                    room_id=room.id,
                    role="assistant",
                    content="Use /api/expenses to inspect demo rows.",
                    metadata_json={"source": "seed", "mode": "demo"},
                    model="gpt-4o",
                ),
                AuditLog(action="seed", entity_type="database", entity_id=None, detail="Inserted course demo data."),
            ]
        )

        session.commit()
        print("Seeded demo data: 4 departments, 12 employees, 8 vendors, 30 expenses, 5 invoices.")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
