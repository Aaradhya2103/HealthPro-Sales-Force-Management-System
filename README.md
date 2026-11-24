# HealthPro Sales Force Management System

A Python and MySQL command-line Enterprise Resource Planning (ERP), CRM, and Sales Force Management system built for retail distribution operations. It combines role-based access control, inventory-driven order management, statistical demand forecasting, heuristic territory allocation, and automated incentive tracking on a normalized 12-table relational database.

## Features

* **Security & Role-Based Access Control (RBAC):** Uses salted PBKDF2-HMAC-SHA256 password hashing (100,000 iterations), automatic lockout after 5 failed login attempts, and 6-digit SMTP email OTP verification for password resets. Supports four roles: General Manager (`MASTER`), Admin (`ADMIN`), Area Sales Manager (`ASM`), and Sales Executive (`SALES`).
* **Sales Forecasting (`scipy.stats.linregress`):** Fits an ordinary least squares (OLS) linear regression model on historical ERP SKU sales across selectable time windows to project 1-day, 30-day, and 360-day demand, reporting the standard error of estimate (n - 2 degrees of freedom).
* **Automated Territory Allocation:** Recommends optimal sales territories by minimizing the gap between each representative's `SalesScore` (revenue, lines sold, and relative target achievement) and regional `AreaPotential` (outlet density per 20,000 population, relative area performance, and average empty shelf stock).
* **Tiered Incentive Engine:** Automatically calculates monthly incentives based on order volume (>700 orders: Rs. 1,000), target achievement (>=100%: Rs. 2,000), and performance score (`SalesScore > 500`), with Admin approval workflows and automated email notifications.
* **Field & ERP Operations:** Daily and monthly attendance tracking, retail outlet onboarding and stock counting, automated email invoicing on order placement, live sales leaderboards, and daily ERP production vs. inventory logging.

## Database Architecture (12 Tables)

Defined in [`schema.sql`](schema.sql) using InnoDB foreign keys and MySQL `STORED GENERATED` columns (`emptystock`, `production_diff`, `target_diff`, `ls_diff`, `sales_diff`):

* **Core & Access:** `employee_details`, `daywise_attendance`, `monthly_attendance`
* **Territories & Retail CRM:** `area`, `outlet_mapping`, `crm`, `outlet_wise_stock`
* **Products, Orders & ERP:** `sku_details`, `order_data`, `erp`
* **Performance & Incentives:** `targets`, `incentive_eligibility`

## Tech Stack

* **Language:** Python 3
* **Database:** MySQL 8.0+ (`mysql-connector-python`)
* **Libraries:** `scipy`, `tabulate`, `python-dotenv`, `hashlib`, `smtplib`

## Setup & Usage

1. **Install dependencies:** `pip install mysql-connector-python scipy tabulate python-dotenv`
2. **Initialize the database:** `mysql -u root -p < schema.sql`
3. **Configure environment variables:** Create a `.env` file in your home directory (`~/.env`) containing `DBPASS`, `SENDING_EMAIL`, `TEST_EMAIL`, `SMTP_SERVER`, `SMTP_PORT`, and `EMAIL_PASSWORD`.
4. **Run the application:** `python main.py`
