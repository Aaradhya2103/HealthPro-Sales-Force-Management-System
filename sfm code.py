import mysql.connector
import hashlib
import os
import math
import random
from dotenv import load_dotenv
from tabulate import tabulate 
import getpass
import smtplib
from datetime import datetime
import calendar
from scipy.stats import linregress as regression

load_dotenv(os.path.join(os.path.expanduser('~'),".env"))

def open_connection():
    global mydb,mycursor
    mydb = mysql.connector.connect(host="localhost", user="root", database="salesforce", passwd=os.getenv("DBPASS"))
    mycursor = mydb.cursor()

def close_connection(): #CAUTION: ALWAYS USE mydb.commit() BEFORE THIS FUNCTION FOR SAVING CHANGES.
    global mydb,mycursor
    if mycursor:
        mycursor.close()
    mydb.close()
    mydb,mycursor = None,None

def send_email(email_id, subject, text):
    sender_email =os.getenv("SENDING_EMAIL")
    email_id = os.getenv("TEST_EMAIL") #For testing
    raw_email = (
        f"From: {sender_email}\n"
        f"To: {email_id}\n"
        f"Subject: {subject}\n\n"  # Double newline here
        f"{text}"
    )
    smtp_server=os.getenv("SMTP_SERVER")
    port = os.getenv("SMTP_PORT")
    try:
        with smtplib.SMTP(smtp_server, port) as server:
            server.starttls()
            server.login(sender_email, os.getenv("EMAIL_PASSWORD"))
            server.sendmail(sender_email, email_id, raw_email)
            print("Email sent successfully!")
    except:
        print("An error occurred in sending email.")
    del raw_email, sender_email, smtp_server, port, email_id, subject, text

def email_valid(email):
    try:
        email_checked = email.partition('@')[2]
        if '@' in email_checked:
            return "INVALID EMAIL"
        suffix=['com','edu','in','org','us','ru','eu','de','uk','fr','jp','ca','net','gov','mil','co']
        email_last_words = email_checked.split('.')
        if email_last_words[0] in suffix:
            return False
        if (email_last_words[-1] in suffix) or (email_last_words[-1] in suffix and email_last_words[-2] in suffix):
            return True
    except:
        return False

def phone_valid(phone):
    if len(phone)==10 and phone.isdigit():
        return True
    else:
        print("Invalid phone number, phone number should be of 10 digits and contain only numbers.")
        return False

def pass_eval(emp_id, input_password): #assume connection open
    mycursor.execute("SELECT password, salt FROM employee_details WHERE emp_id = %s;", (emp_id,))
    result = mycursor.fetchone()
    if not result:
        return False
    stored_hex_hash = result[0]
    stored_hex_salt = result[1]
    del result
    try:
        stored_salt_bytes = bytes.fromhex(stored_hex_salt)
    except:
        print("Stored password prerequisites corrupted, please contact admin to create a new account.")
        return False
    new_dk_hex = hashlib.pbkdf2_hmac(
        'sha256',
        input_password.encode(),
        stored_salt_bytes,
        100000 
    ).hex()
    if new_dk_hex == stored_hex_hash:
        del stored_salt_bytes,stored_hex_salt, stored_hex_hash, new_dk_hex
        return True
    else:
        del stored_salt_bytes,stored_hex_salt, stored_hex_hash, new_dk_hex
        return False

def pass_enc(emp_id, password):
    open_connection()
    salt=os.urandom(16) 
    dk= hashlib.pbkdf2_hmac('sha256',password.encode(),salt,100000)
    mycursor.execute('UPDATE employee_details SET password = %s, salt= %s WHERE emp_id = %s;',(dk.hex(),salt.hex(),emp_id))
    mydb.commit()
    close_connection()
    del salt, dk, password, emp_id


def punch_in(emp_id): #assume connection open
    _, max_days = calendar.monthrange(datetime.now().year,datetime.now().month)
    mycursor.execute('SELECT in_out FROM daywise_attendance WHERE emp_id= %s;',(emp_id,))
    status = mycursor.fetchone()
    if not status:
        mycursor.execute("INSERT INTO daywise_attendance (emp_id,in_out) VALUES (%s,'IN');",(emp_id,))
        mycursor.execute("SELECT days_present FROM monthly_attendance WHERE emp_id= %s AND month=%s AND year=%s;",(emp_id,datetime.now().month,datetime.now().year))
        days_present = mycursor.fetchone()
        if days_present:
            mycursor.execute("UPDATE monthly_attendance SET days_present= days_present+1 WHERE emp_id= %s;", (emp_id,))
        else:
            mycursor.execute("INSERT INTO monthly_attendance (emp_id,month,year,days_present,totaldays) VALUES (%s,%s,%s,%s,%s);",(emp_id, datetime.now().month, datetime.now().year, 1, max_days))
        mydb.commit()

def punch_out(emp_id):
    open_connection()
    mycursor.execute('SELECT in_out FROM daywise_attendance WHERE emp_id= %s;',(emp_id,))
    status = mycursor.fetchone()
    if status and status[0]=='IN':
        time_out = datetime.now()
        mycursor.execute("UPDATE daywise_attendance SET in_out= 'OUT',exit_time=%s WHERE emp_id= %s;",(time_out,emp_id))
        print("Logged Out successfully!")
        mydb.commit()
    close_connection()

def employee_details(emp_id):
    open_connection()
    mycursor.execute('SELECT emp_id, designation, locked_out, emp_email FROM employee_details WHERE emp_id = %s AND is_active<>0;', (emp_id,))
    result = mycursor.fetchone()
    close_connection()
    if not result:
        print("Employee id does not exist.")
        return False
    return (True, result[1], result[2], result[3])  # Returns a tuple with existence, designation, and locked_out status

def login():
    emp_id = input('Enter Employee ID: ')
    exists = employee_details(emp_id)
    if not exists:
        print('Please contact admin.')
        return False
    if exists[2]==1:
        print("User is locked out due to multiple password attempts. Please contact IT department.")
        return False
    for i in range(1,6):
        input_pass = getpass.getpass("Enter Password: ")
        open_connection()
        if pass_eval(emp_id, input_pass):
            del input_pass
            punch_in(emp_id)
            close_connection()
            if exists[1]=='General Manager (A)':
                return ('MASTER', emp_id)
            elif exists[1]=='Area Sales Manager':
                return ('ASM', emp_id)
            elif exists[1][-3:]=='(A)':
                return ('ADMIN', emp_id)
            else:
                return ('SALES', emp_id)
        else: 
            print(f"Incorrect Password! Please try again. \nremaining tries: {6-i}")
        close_connection()
    open_connection()
    mycursor.execute('UPDATE employee_details SET locked_out= 1 WHERE emp_id= %s;',(emp_id,))
    mydb.commit()
    close_connection()
    print('User locked out due to multiple password attempts. Please contact IT department.')
    return False

def password_reset(employee_email, emp_id):
    while True:
        password=getpass.getpass('Enter the new password: ')
        re_password=getpass.getpass('Enter the new password again: ')
        if password!=re_password:
            print('Passwords do not match. Enter passwords again!')
        else:
            break
    otp = random.randint(100000,999999)
    send_email(employee_email, "OTP Verification For Password Setting to Complete Profile",
               f"Dear Employee,\nYour 6-digit OTP for setting your password is {otp}. Please do not share this OTP with anyone.")
    new_otp=int(input("Enter OTP sent via email: "))
    if otp!=new_otp:
        print("OTP entered is incorrect. Could not reset password.")
        del otp, employee_email
        return None
    pass_enc(emp_id, password)
    del otp, employee_email, password, re_password
    print('Password successfully reset!')

def new_employee_password():
    emp_id=input('Enter employee id:')
    emp_data = employee_details(emp_id)  # Get the employee's email
    if not emp_data or not emp_data[3]:
        print("Employee id or email not found. Please contact the admin.")
        return None
    password_reset(emp_data[3], emp_id)
    del emp_data
    print('Profile Completed. Go back to login page for logging in.')


def area_assigned():
    emp_id= input("Enter '1' to see all assigned area or enter '2' to see all areas: ")
    open_connection()
    if emp_id=='1':
        mycursor.execute('SELECT area.emp_id,areacode,areaname,employee_details.emp_name, population FROM area JOIN employee_details ON area.emp_id=employee_details.emp_id WHERE area.emp_id is not null ORDER BY area.emp_id;')
    elif emp_id=='2':
        mycursor.execute('SELECT area.emp_id,areacode,areaname,employee_details.emp_name, population FROM area LEFT JOIN employee_details ON area.emp_id=employee_details.emp_id ORDER BY area.emp_id;')
    areaassigned= mycursor.fetchall()
    close_connection()

    if not areaassigned:
        print("Cannot find Areas.")
    else:
        print('\n',tabulate(areaassigned,['Employee ID', 'AREA CODE', 'Area Name', 'Employee Name', 'Population'], tablefmt="simple"))       


def salesscore(emp_id):
    mycursor.execute("SELECT sales, tls, target_sales FROM targets WHERE emp_id = %s;", (emp_id,))
    emp_data = mycursor.fetchone()
    if not emp_data:
        print("Employee data not found in the targets table.")
        return 0.0
    total_sales = float(emp_data[0])
    total_lines_sold = int(emp_data[1])
    target_sales = float(emp_data[2])
    if target_sales > 0:
        perc_target_achieved = (total_sales / target_sales) * 100
    else:
        perc_target_achieved = 0.0
    mycursor.execute("SELECT COUNT(sku) FROM sku_details WHERE active_sku=1;")
    sku_data = mycursor.fetchone()
    total_skus = sku_data[0] if sku_data[0] else 1
    mycursor.execute("SELECT AVG((sales / target_sales) * 100) FROM targets WHERE tls<%s AND target_sales > 0;", (total_lines_sold,))
    avg_data = mycursor.fetchone()
    try:
        avg_lower_lines_perc = float(avg_data[0])
    except:
        avg_lower_lines_perc=0.0
    '''
    SalesScore = (total sales / total sku's) * 0.01 
                + total lines sold +(%sales target achieved
                - avg%target achieved by salesmen with lower lines sold)
    '''
    sales_core = math.floor((total_sales / total_skus) * 0.01 + total_lines_sold + (perc_target_achieved - avg_lower_lines_perc))
    return sales_core


def areapotential(areacode):
    current_month=(datetime.now().month-1)%12 if datetime.now().day<7 else datetime.now().month
    mycursor.execute("SELECT COUNT(*) FROM outlet_mapping WHERE areacode=%s AND active_outlet=1;",(areacode,))
    no_of_outlets = mycursor.fetchone()[0]
    mycursor.execute("SELECT population FROM area WHERE areacode=%s;",(areacode,))
    population = mycursor.fetchone()
    mycursor.execute("SELECT SUM(target_sales) FROM targets;")
    total_target = mycursor.fetchone()[0]
    mycursor.execute("SELECT AVG(emptystock_on_order), SUM(amount) FROM order_data NATURAL JOIN outlet_mapping WHERE areacode=%s AND order_status<>'CANCELLED' AND MONTH(date_of_order)=%s; ",(areacode, current_month))
    avg_empty_stock, sales_in_area = mycursor.fetchone()
    avg_empty_stock = math.floor(avg_empty_stock) if avg_empty_stock else 0
    mycursor.execute("SELECT COUNT(*) FROM area")
    no_of_areas = mycursor.fetchone()[0]
    try:
        pct_area_sales_achievement = float((sales_in_area/total_target)*no_of_areas*100)
    except:
        pct_area_sales_achievement = 0
    mycursor.execute("SELECT SUM(amount) FROM order_data NATURAL JOIN outlet_mapping WHERE order_status<>'CANCELLED' AND MONTH(date_of_order)=%s;",(current_month,))
    try:
        pct_avg_region_achievement = float((mycursor.fetchone()[0]/total_target)*100)
    except:
        pct_avg_region_achievement=0.0
    if population:
        population=population[0]
        outlet_density=no_of_outlets/population
    else:
        outlet_density=0.0
    '''
    area_potential = no.of outlets per 20,000 population 
    + (%sales achievement in area- avg%region sales achievement)*10
    + avg empty_stock_on order *0.1
    '''
    area_potential = math.floor(outlet_density*20000 + (pct_area_sales_achievement-pct_avg_region_achievement)*10 + avg_empty_stock*0.1)
    return area_potential


def see_erp(month, sku='all'):
    if sku == 'all':
        open_connection()
        mycursor.execute("SELECT * FROM erp WHERE MONTH(end_of_day)=%s;",(month,))
    else:
        if sku_exists(sku):
            open_connection()
            mycursor.execute("SELECT * FROM erp WHERE MONTH(end_of_day)=%s AND sku=%s;",(month,sku))
        else:
            return None
    erp_details = mycursor.fetchall()
    close_connection()
    if not erp_details:
        print("Cannot find ERP for given month.")
    else:
        print('\n',tabulate(erp_details,['DATE', 'SKU', 'UNITS PRODUCED', 'UNITS ORDERED', 'INVENTORY STOCK', 'PRODUCTION SURPLUS','TOTAL SALES','TARGET SALES','TARGET DIFF'], tablefmt="simple"))       


def insert_erp():
    while True:
        day= input("Enter date (YYYY-MM-DD): ").strip()
        try:
            end_of_day = datetime.strptime(day, "%Y-%m-%d").date()
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")
    open_connection()
    while True:
        sku=input('Enter SKU(press q to quit):')
        if sku == 'q':
            close_connection()
            break
        mycursor.execute("SELECT SUM(units) FROM order_data WHERE sku=%s;",(sku,))
        result=mycursor.fetchone()
        if not result:
            print('SKU not found in database.')
            close_connection()
            continue
        units_ordered = int(result[0]) if result and result[0] else 0
        mycursor.execute('SELECT end_of_day FROM erp WHERE end_of_day=%s AND sku=%s;',(end_of_day, sku))
        updation = False
        if mycursor.fetchone():
            ch = input(f"Entry for SKU '{sku}' on {end_of_day} already exists. Do you want to update(y/n)?").strip().lower()
            if ch =='y':
                updation=True
            else:
                close_connection()
                return None
        units_produced= int(input('Enter units produced:'))
        units_inventory= int(input('Enter units in inventory:'))
        mycursor.execute("SELECT SUM(amount) FROM order_data WHERE DATE(date_of_order)=%s AND sku=%s",(end_of_day, sku))
        sales_row = mycursor.fetchone()
        new_sales = float(sales_row[0]) if sales_row and sales_row[0] else 0.0
        mycursor.execute('SELECT total_sales FROM erp WHERE sku=%s ORDER BY end_of_day DESC LIMIT 1',(sku,))
        res = mycursor.fetchone()
        prev_sales = float(res[0]) if res else 0.0
        total_sales= new_sales+prev_sales
        mycursor.execute("SELECT target_sales FROM erp WHERE sku = %s ORDER BY end_of_day DESC LIMIT 1", (sku,))
        prev_target = mycursor.fetchone()
        if prev_target:
            change = input('Do you want to change target sales, y/n?').strip().lower()
            if change == 'y':
                target_sales = float(input("Enter new target sales: "))
            else:
                target_sales = float(prev_target[0])
        else:
            target_sales = float(input("No previous target found. Enter target sales: "))
        if updation:
            mycursor.execute("UPDATE erp SET sku=%s, units_produced=%s, units_ordered=%s, units_inventory=%s, total_sales=%s, target_sales=%s WHERE end_of_day=%s;", (sku, units_produced, units_ordered, units_inventory, total_sales,target_sales, end_of_day))
        else:
            mycursor.execute("INSERT INTO erp (end_of_day, sku, units_produced, units_ordered, units_inventory, total_sales, target_sales ) VALUES (%s, %s, %s, %s, %s, %s,%s);", (end_of_day, sku, units_produced, units_ordered, units_inventory, total_sales,target_sales))
        mydb.commit()
        close_connection()
    month=input('Enter ERP month:')
    print(see_erp(month))
    
def area_automated_allocation(emp_id):
    mycursor.execute("SELECT areacode FROM area WHERE population>0;")
    areas=list()
    for x in mycursor:
        areas.append(x[0])
    if areas:
        min_area= areas[0]
        min_score= abs(salesscore(emp_id)-areapotential(areas[0]))
        for i in areas:
            allocation_score = abs(salesscore(emp_id)-areapotential(i))
            if min_score>allocation_score:
                min_score=allocation_score
                min_area = i
        return min_area
    else:
        return 'None'

def see_order_details(orderno):
    mycursor.execute('SELECT orderno,sku,outletno,units,amount,date_of_order,order_status,status_updated FROM order_data WHERE orderno=%s;',(orderno,))
    order_details = mycursor.fetchall()
    return '\n' + tabulate(order_details, ['ORDER NO.', 'SKU', 'OUTLET NO.', 'UNITS', 'AMOUNT', 'DATE OF ORDER', 'ORDER STATUS', 'STATUS UPDATED'], tablefmt="simple")

def change_orderdetails():
    open_connection()
    orderno=int(input('Enter order number: '))
    mycursor.execute('SELECT order_status, outletno FROM order_data WHERE orderno=%s;',(orderno,))
    stat=list(mycursor.fetchall())
    if stat and stat[0][0]=='CANCELLED':
        print('Order has been cancelled.')
    elif stat:
        ch=input('Enter order status(enter 1 for DISPATCHED or 2 for DELIVERED or 3 for CANCELLED): ').strip()
        if ch=='1':
            status='DISPATCHED'
        elif ch=='2':
            status='DELIVERED'
        elif ch=='3':
            status='CANCELLED'
            mycursor.execute("SELECT email FROM crm WHERE outletno=%s;",(stat[0][1],))
            send_email(str(mycursor.fetchone()[0]), "Information Regarding Order Cancellation",
                       f"Dear Customer, \nYour order number {orderno} was cancelled on {datetime.now()}. Sorry for the inconvenience.\nThanks and Regards,\nHealthPro and Team")
        else:
            print('Wrong Input')
            close_connection()
            return None
        mycursor.execute('UPDATE order_data SET order_status=%s WHERE orderno=%s;',(status,orderno))
        mydb.commit()
        print(see_order_details(orderno))
    else:
        print("Invalid Order Number")
    close_connection()



def check_daywise_attendence():
    open_connection()
    mycursor.execute('SELECT emp_id, entry_time, exit_time, in_out FROM daywise_attendance ORDER BY emp_id')
    attendence= mycursor.fetchall()
    close_connection()
    if not attendence:
        print('Attendence records not found.')
        return None
    else:
        headers = ["Employee ID", "Entry Time", "Exit Time", "IN/OUT/AB"]
        print('\n', tabulate(attendence, headers, tablefmt="simple"))

def check_monthly_attendence(emp_id):
    open_connection()
    mycursor.execute('SELECT monthly_attendance.emp_id, employee_details.emp_name, employee_details.designation, employee_details.emp_email, monthly_attendance.month, monthly_attendance.year, monthly_attendance.days_present, monthly_attendance.totaldays FROM monthly_attendance JOIN employee_details ON monthly_attendance.emp_id=employee_details.emp_id WHERE monthly_attendance.emp_id=%s ORDER BY monthly_attendance.year, monthly_attendance.month;',(emp_id,))
    attendence= mycursor.fetchall()
    close_connection()
    if not attendence:
        print('Attendence records not found.')
        return None
    else:
        headers = ["Emp ID", "Name", "Designation", "Email", "Month", "Year", "Days Present", "Total Days"]
        print('\n', tabulate(attendence, headers, tablefmt="simple"))

def neworder(employee_id,outletno):
    if not outlet_exists(outletno):
        return None
    lines_sold=0
    sales=0.0
    open_connection()
    mycursor.execute('SELECT MAX(orderno) FROM order_data;')
    prev_orderno= mycursor.fetchone()[0]
    orderno= (prev_orderno or 710001)+1
    while True:
        sku=input('Enter SKU number(enter q to stop):').strip()
        if sku.lower()=='q':
            break
        mycursor.execute('SELECT wholesale_price FROM sku_details WHERE sku=%s AND active_sku<>0;',(sku,))
        sku_details= mycursor.fetchone()
        if not sku_details:
            continue
        price = sku_details[0]
        mycursor.execute('SELECT emptystock FROM outlet_wise_stock WHERE outletno=%s AND sku=%s;',(outletno,sku))
        emptystock=mycursor.fetchone()
        if not emptystock:
            print('No empty stock.')
            emptystock=0
        else:
            print(f'Empty Stock={emptystock[0]}')
            emptystock=emptystock[0]
        print("Empty stock will serve as a metric for you to decide order required to be pitched to the retailer.")
        units=int(input('Enter number of units you want to order:'))
        amount=float(price*units)

        sales+=amount
        lines_sold+=1

        mycursor.execute('INSERT INTO order_data (orderno, sku, outletno, emp_id, emptystock_on_order, units, amount) VALUES (%s,%s,%s,%s,%s,%s,%s)',(orderno, sku, outletno, employee_id, emptystock, units, amount))
        mycursor.execute("UPDATE outlet_mapping SET billing_status_recent='P' WHERE outletno=%s AND billing_status_recent<>'P';",(outletno,))
        mydb.commit()
    mycursor.execute("SELECT orderno FROM order_data WHERE orderno=%s;",(orderno))
    if mycursor.fetchone():
        print('Order successfully placed')
        invoice=see_order_details(orderno)
        print('\n',invoice)
        mycursor.execute("UPDATE targets SET sales=sales+%s, tls=tls+%s WHERE emp_id=%s;",(sales,lines_sold,employee_id))
        mycursor.execute("UPDATE incentive_eligibility SET salescore=%s WHERE emp_id=%s AND month=%s AND year=%s;",(salesscore(employee_id),employee_id,datetime.now().month,datetime.now().year))
        mydb.commit()
        incentive_evaluation(employee_id)
        mycursor.execute("SELECT email FROM crm WHERE outletno=%s AND email IS NOT NULL",(outletno,))
        email_retailer = mycursor.fetchone()
        mydb.commit()
        close_connection()
        if not email_retailer:
            print("Email does not exist for the outlet, could not send invoice, add email as soon as possible. Show the reciept to retailer.")
            return None
        send_email(email_retailer[0], f"Invoice for HealthPro Order on {datetime.now().date()}",
                f"Dear Customer,\n The following are the order details:\n {invoice}\nThank you for chosing HealthPro! If this order is not yours, or you have any queries regarding the order, contact help.healthprohealthmatters@gmail.com\n\nThanks and Regards,\nHealthPro and Team")
    else:
        print("Order not placed.")
        close_connection()    

def sales_counting(outletno):
    open_connection()
    mycursor.execute("SELECT outletno FROM outlet_mapping WHERE outletno = %s AND active_outlet<>0;", (outletno,))
    outlet_exists = mycursor.fetchone()
    if not outlet_exists:
        print("Outlet Number does not exist in the database.")
        close_connection()
        return None 
    print(f"\nOutlet {outletno} verified. You can now enter multiple SKUs.")
    while True:
        print("\n--- Enter SKU Details (or type '0' to finish) ---")
        sku = input("Enter SKU: ")
        if sku == '0':
            break 
        mycursor.execute("SELECT sku FROM sku_details WHERE sku = %s AND active_sku<>0;", (sku,))
        sku_exists = mycursor.fetchone()
        if not sku_exists:
            print(f"SKU '{sku}' does not exist. Please try again.")
            continue
        new_stock_qty = int(input(f"Enter the current stock quantity for {sku}: "))
        new_max_capacity = int(input(f"Enter the max capacity for {sku}: "))
        mycursor.execute("UPDATE outlet_wise_stock SET stock=%s, max_capacity=%s WHERE outletno=%s AND sku=%s;", (new_stock_qty, new_max_capacity, outletno, sku))
        if mycursor.rowcount == 0:
            print(f"No previous record found. Creating new stock entry for {sku}...")
            mycursor.execute("INSERT INTO outlet_wise_stock (outletno, sku, stock, max_capacity) VALUES (%s, %s, %s, %s);", (outletno, sku, new_stock_qty, new_max_capacity))
        mydb.commit() 
        print(f"Successfully recorded {sku}.")
    print(f"\nAll stock counting completed for Outlet {outletno}.")
    mycursor.execute("UPDATE outlet_mapping SET billing_status_recent='U' WHERE outletno=%s;",(outletno,))
    mydb.commit()
    close_connection()

def outlet_exists(outletno):
    open_connection()
    mycursor.execute("SELECT outletno FROM outlet_mapping WHERE outletno = %s AND active_outlet<>0;", (outletno,))
    outlet_exists = mycursor.fetchone()
    close_connection()
    if not outlet_exists:
        print("Outlet Number does not exist in the database.")
    return bool(outlet_exists)

def change_outlet_details_onfield(outletno):
    if not outlet_exists(outletno):
        return None
    open_connection()
    print("Enter the changed details(enter 0 if unchanged):")
    name = input("Enter changed Outlet Name: ").strip()
    if name!='0':
        mycursor.execute("UPDATE outlet_mapping SET outletname=%s WHERE outletno=%s;",(name,outletno))
    outlet_address = input("Enter changed Address: ").strip()
    if outlet_address!='0':
        mycursor.execute("UPDATE outlet_mapping SET outlet_address=%s WHERE outletno=%s;",(outlet_address,outletno))
    area_exists = tuple()
    for i in range(3):
        areacode = input("Enter changed Area Code:").strip()
        if areacode=='0':
            break
        mycursor.execute("SELECT areacode FROM area WHERE areacode=%s;",(areacode,))
        area_exists=mycursor.fetchone()
        if not area_exists:
            print(f"Area Code does not exist, contact Admin to add it or enter 0. Remaining tries {2-i}.")
            continue
        mycursor.execute("UPDATE outlet_mapping SET areacode=%s WHERE outletno=%s;",(areacode,outletno))
    if not area_exists and areacode!=0:
        print("Could not change Area Code.")
    owner_name = input("Enter Owner Name: ").strip()
    if owner_name!='0':
        mycursor.execute("UPDATE crm SET owner_name=%s WHERE outletno=%s;",(owner_name,outletno))
    email = input("Enter email of owner: ").strip()
    if (email!='0') and (not email_valid(email)):
        print("Invalid Email, email could not be added to database.")
    elif email!='0':
        mycursor.execute("UPDATE crm SET email=%s WHERE outletno=%s;",(email,outletno))
    phone = input("Enter phone number of owner: ").strip()
    if phone!='0' and phone_valid(phone):
        mycursor.execute("UPDATE crm SET phone=%s WHERE outletno=%s;",(phone,outletno))
    mydb.commit()
    close_connection()
    print("Changed Outlet details Successfully!")
    
def delete_outlet(outletno):
    open_connection()
    mycursor.execute("UPDATE outlet_mapping SET active_outlet=0 WHERE outletno=%s AND active_outlet<>0;",(outletno,))
    print("Successfully deleted outlet.")
    mydb.commit()
    close_connection()

def create_outlet():
    open_connection()
    mycursor.execute("SELECT MAX(outletno) FROM outlet_mapping;")
    outletno = mycursor.fetchone()
    prev_outlet = outletno[0] if outletno[0] else 'HPOT000000'
    outletno = prev_outlet[:4]+f"{int(prev_outlet[4:])+1:06}"
    print("Enter the details:-")
    name = input("Enter Outlet Name(Enter if not applicable): ").strip()
    outlet_address = input("Enter Address: ").strip()
    area_exists = tuple()
    areacode =''
    area_exists = True
    for i in range(3):
        areacode = input("Enter Area Code:").strip()
        if not areacode:
            break
        mycursor.execute("SELECT areacode FROM area WHERE areacode=%s;",(areacode,))
        area_exists=mycursor.fetchone()
        if not area_exists:
            print(f"Area Code does not exist, contact Admin to add it, else it will be assigned to ZZ001. Remaining tries: {2-i}.")
            areacode = 'ZZ001' #Admin Areas(0 population, filler zones, unassigned outlets)
    mycursor.execute("INSERT INTO outlet_mapping (outletno, outletname, outlet_address, areacode) VALUES (%s,%s,%s,%s);",(outletno,name, outlet_address,areacode))
    owner_name = input("Enter Owner Name(press enter if not applicable): ").strip()
    email = input("Enter email of owner(press enter if not applicable): ").strip()
    if not email_valid(email):
        print("Invalid Email, email could not be added to database.")
        email=None
    phone = input("Enter phone number of owner(press enter if not applicable): ").strip()
    if phone!='0':
        if len(phone)!=10:
            print("Phone number not of correct length, could not add phone number.")
            phone = ''
    mycursor.execute("INSERT INTO crm VALUES (%s,%s,%s,%s);",(outletno, owner_name, phone, email))
    mydb.commit()
    close_connection()
    print("Successfully added outlet!")
    del area_exists, name, outlet_address, areacode,owner_name, email, phone

def sku_exists(sku):
    open_connection()
    mycursor.execute("SELECT sku FROM sku_details WHERE sku = %s AND active_sku<>0;", (sku,))
    sku_exists = mycursor.fetchone()
    close_connection()
    if not sku_exists:
        print("SKU does not exist in the database.")
    return bool(sku_exists)

def add_sku():
    sku = input("Enter new SKU number: ").strip()
    if not sku:
        print("SKU cannot be empty.")
        return None
    elif sku_exists(sku):
        print("SKU already exists, cannot add duplicate SKU.")
        return None
    name = input("Enter name of the SKU: ").strip()
    net_weight = round(float(input("Enter net weight of the SKU in grams: "))/1000, 3)
    wholesale_price = round(float(input("Enter wholesale price of the SKU: ")), 2)
    open_connection()
    mycursor.execute("INSERT INTO sku_details (sku, sku_name, netwt, wholesale_price) VALUES (%s, %s, %s, %s);",(sku, name, net_weight, wholesale_price))
    mydb.commit()
    close_connection()
    print("Successfully added SKU.")
    sku_details_display()

def update_sku():
    sku = input("Enter SKU to update: ").strip()
    if not sku_exists(sku):
        return None
    name = input("Enter new name of the SKU(press enter if not applicable): ").strip()
    open_connection()
    if name:
        mycursor.execute("UPDATE sku_details SET sku_name=%s WHERE sku=%s;",(name,sku))
    net_weight_input = input("Enter new net weight of the SKU in grams(press enter if not applicable): ").strip()
    if net_weight_input:
        net_weight = round(float(net_weight_input)/1000,3)
        mycursor.execute("UPDATE sku_details SET netwt=%s WHERE sku=%s;",(net_weight,sku))
    wholesale_price_input = input("Enter new wholesale price of the SKU(press enter if not applicable): ").strip()
    if wholesale_price_input:
        wholesale_price = round(float(wholesale_price_input),2)
        mycursor.execute("UPDATE sku_details SET wholesale_price=%s WHERE sku=%s;",(wholesale_price,sku))
    mydb.commit()
    close_connection()
    sku_details_display()

def delete_sku():
    sku = input("Enter SKU to delete: ").strip()
    open_connection()
    mycursor.execute("UPDATE sku_details SET active_sku=0 WHERE sku=%s;",(sku,))
    mydb.commit()
    close_connection()
    sku_details_display()

def visual_leaderboard():
    open_connection()
    mycursor.execute("SELECT employee_details.emp_id, employee_details.emp_name, incentive_eligibility.salescore FROM employee_details JOIN incentive_eligibility ON employee_details.emp_id = incentive_eligibility.emp_id WHERE incentive_eligibility.month=%s AND incentive_eligibility.year=%s ORDER BY incentive_eligibility.salescore DESC;",(datetime.now().month, datetime.now().year))
    raw_leaderboard = list(mycursor.fetchall())
    close_connection() 
    if not raw_leaderboard:
        print("Error: No records found to generate a leaderboard.")
        return None
    final_leaderboard_display = list()
    rank = 1
    for rank in range(1, len(raw_leaderboard)+1):
        emp_id = raw_leaderboard[rank-1][0]
        emp_name = raw_leaderboard[rank-1][1]
        score = raw_leaderboard[rank-1][2]
        final_leaderboard_display.append((rank, emp_id, emp_name, score))
    print("\n==========================================================================================")
    print("                        SALES FORCE PERFORMANCE LEADERBOARD                        ")
    print("==========================================================================================")
    print('\n', tabulate(final_leaderboard_display, ["Rank", "Employee ID", "Employee Name", "Sales Score"], tablefmt="simple"))
    print("\n==========================================================================================\n")
    

def update_emp_details():
    emp_id=input('Enter Employee id: ').strip()
    if not employee_details(emp_id):
        print("Employee id does not exist, cannot update non-existent employee.")
        return None
    open_connection()
    designation = input("Enter the new designation of employee(press enter if not applicable): ").strip()
    if designation:
        mycursor.execute("UPDATE employee_details SET designation=%s WHERE emp_id=%s;",(designation,emp_id))
    emp_email = input("Enter the new mail of employee(press enter if not applicable): ").strip()
    if emp_email:
        mycursor.execute("UPDATE employee_details SET emp_email=%s WHERE emp_id=%s;",(emp_email,emp_id))
    emp_phone = input("Enter employee's new phone number(press enter if not applicable): ").strip()
    if emp_phone:
        mycursor.execute("UPDATE employee_details SET emp_phone=%s WHERE emp_id=%s;",(emp_phone,emp_id))
    locked=input('enter 0 to reset locked out state(press enter if not applicable): ').strip()
    if locked=='0':
        mycursor.execute("UPDATE employee_details SET locked_out=0 WHERE emp_id=%s AND locked_out=1;",(emp_id,))
    mydb.commit()
    close_connection()

def delete_emp(emp_id):
    active=input('Enter 0 if employee is no longer working at the company: ').strip()
    open_connection()
    if active=='0':
        mycursor.execute("UPDATE employee_details SET is_active=0 WHERE emp_id=%s AND is_active=1;",(emp_id,))
    mydb.commit()
    close_connection()

def see_target_achievement(emp_id):
    open_connection()
    mycursor.execute("SELECT sales, tls, target_sales, target_ls, ls_diff, sales_diff FROM targets WHERE emp_id = %s;", (emp_id,))
    emp_target = mycursor.fetchone()
    mycursor.execute("SELECT incentive_eligible, admin_approval FROM incentive_eligibility WHERE emp_id = %s AND month=%s AND year=%s;",(emp_id, datetime.now().month, datetime.now().year))
    emp_incentive = mycursor.fetchone()
    emp_incentive = emp_incentive if emp_incentive else (0.0, None)
    if not emp_target:
        print("Employee data not found in the targets table.")
        close_connection()
        return None
    close_connection()
    incentive_amount = float(emp_incentive[0])
    admin_approval = emp_incentive[1]
    total_sales = float(emp_target[0])
    target_sales = float(emp_target[2])
    if target_sales > 0:
        perc_target_achieved = (total_sales / target_sales) * 100
    else:
        perc_target_achieved = 0.0
    print(f"Employee ID: {emp_id}\nTotal Sales: {total_sales}\nTotal Lines Sold: {int(emp_target[1])}\nTarget Sales: {target_sales}\nTarget Lines Sold: {int(emp_target[3])}\nDifference in Lines Sold from Target: {int(emp_target[4])}\nDifference in Sales from Target: {float(emp_target[5])}\nPercentage of Sales Target Achieved: {perc_target_achieved:.2f}%")
    if incentive_amount > 0:
        print(f"Incentive Eligible: Yes\nIncentive Amount: {incentive_amount}")
        if admin_approval == "Y":
            print("Admin Approval: Approved")
        elif admin_approval == "N":
            print("Admin Approval: Not Approved")
        else:
            print("Admin Approval: Pending")

def see_profile(emp_id):
    if not employee_details(emp_id):
        print("Employee id does not exist, cannot display profile of non-existent employee.")
        return None
    open_connection()
    mycursor.execute("SELECT emp_id, emp_name, dob, designation, emp_email, emp_phone FROM employee_details WHERE emp_id = %s;", (emp_id,))
    emp_profile = mycursor.fetchone()
    close_connection()
    print(f"Employee ID: {emp_profile[0]}\nEmployee Name: {emp_profile[1]}\nDate of Birth: {emp_profile[2]}\nDesignation: {emp_profile[3]}\nEmail: {emp_profile[4]}\nPhone: {emp_profile[5]}")

def update_profile(emp_id):
    open_connection()
    mycursor.execute("SELECT emp_id FROM employee_details WHERE emp_id = %s;", (emp_id,))
    if not mycursor.fetchone():
        print("Employee id does not exist, cannot update non-existent employee.")
        close_connection()
        return None
    new_email = input("Enter new email (press enter to skip): ").strip()
    if new_email:
        if email_valid(new_email):
            mycursor.execute("UPDATE employee_details SET emp_email=%s WHERE emp_id=%s;", (new_email, emp_id))
        else:
            print("Invalid email format. Email not updated.")
    new_phone = input("Enter new phone number (press enter to skip): ").strip()
    if new_phone:
        if len(new_phone) == 10 and new_phone.isdigit():
            mycursor.execute("UPDATE employee_details SET emp_phone=%s WHERE emp_id=%s;", (new_phone, emp_id))
        else:
            print("Invalid phone number. Phone not updated.")
    mydb.commit()
    close_connection()
    update_password = input("Do you want to update your password? (y/n): ").strip().lower()
    if update_password == 'y':
        current_email = employee_details(emp_id)[3]  # Assuming employee_details returns a tuple where index 3 is the email
        current_password = getpass.getpass('Enter current password: ')
        open_connection()
        if not pass_eval(emp_id,current_password):
            close_connection()
            del current_password, current_email
            print("Current Password does not match, cannot change password.")
        else:
            close_connection()
            password_reset(current_email, emp_id)
    print("Profile Updated.")

def area_allocation_by_admin():
    while True:
        emp_id = input("Enter Employee ID to allocate area(enter q to finish): ").strip()
        if emp_id.lower()=='q':
            break
        open_connection()
        mycursor.execute("SELECT emp_id FROM employee_details WHERE emp_id=%s;",(emp_id,))
        if not mycursor.fetchone():
            print("Employee id does not exist, cannot allocate area to non-existent employee.")
            close_connection()
            return None

        suggested_allocated_area = area_automated_allocation(emp_id)
        print(f"Suggested area to allocate based on sales score and area potential is {suggested_allocated_area}.")
        allocated_area = input("Enter area code to allocate: ").strip()
        mycursor.execute("SELECT areacode FROM area WHERE areacode=%s;",(allocated_area,))
        if not mycursor.fetchone():
            print("Area code does not exist, cannot allocate non-existent area.")
            close_connection()
            return None
        mycursor.execute("SELECT areacode FROM area WHERE emp_id=%s AND areacode<>%s;",(emp_id, allocated_area))
        previously_allocated_area = mycursor.fetchone()
        if previously_allocated_area:
            mycursor.execute("UPDATE area SET emp_id=NULL WHERE areacode=%s;",(previously_allocated_area[0],))
        mycursor.execute("UPDATE area SET emp_id=%s WHERE areacode=%s;",(emp_id, allocated_area))
        mydb.commit()
        close_connection()
        print(f"Area {allocated_area} has been allocated to Employee {emp_id}.")
    area_assigned()


def sales_forcast():
    ch = input("Sales forcasting is done using Linear Regression model. It may not be realistic and does not account for real-world conditions.\nERP data can be taken for:\n1.Last 7 days\n2.Last 30 days\n3.Last 3 months\n4.Last 12 months\n5.Last 3 years\n\nPlease enter what dataset you want to chose(0 if all available data): ")
    if ch=='1':
        days_counted=7
    elif ch=='2':
        days_counted=30
    elif ch=='3':
        days_counted=3*30
    elif ch=='4':
        days_counted=365
    elif ch=='5':
        days_counted=365*3
    elif ch=='0':
        days_counted=0
    else:
        print("Invalid Input")
        return None
    sku_predict=input("Enter SKU number to be predicted: ")
    if not sku_exists(sku_predict):
        return None
    open_connection()
    if days_counted:
        mycursor.execute("SELECT MONTH(end_of_day), total_sales FROM erp WHERE sku=%s ORDER BY end_of_day ASC LIMIT %s;",(sku_predict, days_counted))
    else:
        mycursor.execute("SELECT MONTH(end_of_day), total_sales FROM erp WHERE sku=%s ORDER BY end_of_day ASC;",(sku_predict,))
    cumulative_sales = mycursor.fetchall()
    close_connection()
    n = len(cumulative_sales)
    if n<3:
        print("Not enough data for forcasting.")
        return None
    sales_per_day = list()
    for entry in range(n):
        if entry>1:
            if cumulative_sales[entry][0] == cumulative_sales[entry-1][0]:
                sales_per_day.append(float(cumulative_sales[entry][1]-cumulative_sales[entry-1][1]))
            else:
                sales_per_day.append(float(cumulative_sales[entry][1]))
        else:
            sales_per_day.append(float(cumulative_sales[entry][1]))

    index_sales = list(range(n))
    print("Evaluating model...")
    slope, intercept, _,_,_ = regression(index_sales,sales_per_day)
    print(f"Model:\n sales on a day = {slope}*(days after today) + ({intercept})")
    sum_squared_errors = 0.0
    for i in index_sales:
        y_fitted = (slope * i) + intercept
        error = sales_per_day[i] - y_fitted
        sum_squared_errors+= error**2
    standard_deviation = math.sqrt(sum_squared_errors /(n-2)) #only (n-2) degrees of freedom in LR(2 points are needed to form a line)
    print("Standard error of estimate = ", standard_deviation)
    ch = input("Enter sales to be predicted in:\n1.Next day\n2.Next 30 days\n3.Next 12 months\nEnter your choice: ")
    if ch=='1':
        days_predicted = 1
    elif ch=='2':
        days_predicted=30
    elif ch=='3':
        days_predicted=360
    else:
        print("Invalid Input")
        return None
    total_sales_predicted = 0.0
    for i in range(1, days_predicted+1):
        total_sales_predicted+= (slope * (n+i)) + intercept
    print("Sales Predicted: Rs.",total_sales_predicted)

def incentive_evaluation(emp_id):
    """Evaluate incentive for an employee based on orders and target achievement.
    Criteria:
    - If distinct order count in the month by the employee is greater than 700, award Rs.1000.
    - If sales target achievement is 100% or more, award Rs.2000.
    - If Sales Score >500 incentive is Rs. (Salescore - 500)
    """
    mycursor.execute("SELECT sales, target_sales FROM targets WHERE emp_id = %s;",(emp_id,))
    target_row = mycursor.fetchone()
    
    if not target_row:
        print('Target record not found for employee. Incentive cannot be calculated')
        return None

    total_sales = float(target_row[0])
    target_sales = float(target_row[1])

    mycursor.execute("SELECT COUNT(DISTINCT orderno) FROM order_data WHERE emp_id = %s AND MONTH(date_of_order) = %s AND YEAR(date_of_order) = %s AND order_status<>'CANCELLED';",(emp_id, datetime.now().month, datetime.now().year))
    
    order_count = mycursor.fetchone()[0]

    incentive_amount = 0.0
    if order_count > 700:
        incentive_amount += 1000.0
    if target_sales > 0 and total_sales >= target_sales:
        incentive_amount += 2000.0
    

    mycursor.execute("SELECT emp_id, salescore FROM incentive_eligibility WHERE emp_id = %s AND month = %s AND year = %s;",(emp_id, datetime.now().month, datetime.now().year))
    incentive_record = mycursor.fetchone()
    eligibility_exists, sales_score_of_employee = incentive_record if incentive_record else (None, 0.0)
    
    if sales_score_of_employee > 500:
        incentive_amount += (sales_score_of_employee - 500)

    if eligibility_exists is not None:
        mycursor.execute("UPDATE incentive_eligibility SET incentive_eligible = %s WHERE emp_id = %s AND month = %s AND year = %s;",(incentive_amount, emp_id, datetime.now().month, datetime.now().year))
    else:
        mycursor.execute("INSERT INTO incentive_eligibility (emp_id, month, year, incentive_eligible) VALUES (%s, %s, %s, %s);",(emp_id, datetime.now().month, datetime.now().year, incentive_amount))
    mydb.commit()

def incentive_table_display():
    open_connection()
    mycursor.execute("SELECT emp_id, incentive_eligible, admin_approval FROM incentive_eligibility WHERE month = %s AND year = %s;",(datetime.now().month, datetime.now().year))
    incentive_records = mycursor.fetchall()
    close_connection()
    if not incentive_records:
        print("No incentive records found for the current month and year.")
        return None
    headers = ["Employee ID", "Incentive Eligible (Rs.)", "Admin Approval"]
    print('\n', tabulate(incentive_records, headers, tablefmt="simple"))

def show_targets_table():
    open_connection()
    mycursor.execute("SELECT emp_id, sales, tls, target_sales, target_ls FROM targets;")
    target_records = mycursor.fetchall()
    close_connection()
    if not target_records:
        print("No target records found.")
        return None
    headers = ["Employee ID", "Sales", "Lines Sold", "Target Sales", "Target Lines Sold"]
    print('\n', tabulate(target_records, headers, tablefmt="simple"))

def show_outlets(areacode):
    open_connection()
    mycursor.execute("SELECT outletno, outletname, outlet_address, billing_status_recent FROM outlet_mapping WHERE areacode = %s AND active_outlet<>0;",(areacode,))
    outlets = mycursor.fetchall()
    close_connection()
    if not outlets:
        print("No active outlets found in this area.")
        return None
    headers = ["Outlet Number", "Outlet Name", "Outlet Address", "Recent Billing Status"]
    print('\n', tabulate(outlets, headers, tablefmt="simple"))

def sku_details_display():
    open_connection()
    mycursor.execute("SELECT sku, sku_name, netwt, wholesale_price, active_sku FROM sku_details;")
    sku_records = mycursor.fetchall()
    close_connection()
    if not sku_records:
        print("No SKU records found.")
        return None
    headers = ["SKU", "SKU Name", "Net Weight (kg)", "Wholesale Price (Rs.)", "Active Status"]
    print('\n', tabulate(sku_records, headers, tablefmt="simple"))

def admin_approval_for_incentive(emp_id):
    open_connection()
    mycursor.execute("SELECT incentive_eligible FROM incentive_eligibility WHERE emp_id = %s AND month = %s AND year = %s;",(emp_id, datetime.now().month, datetime.now().year))
    incentive_row = mycursor.fetchone()
    
    if not incentive_row:
        print('Incentive eligibility record not found for employee.')
        close_connection()
        return None

    incentive_amount = float(incentive_row[0])
    if incentive_amount <= 0:
        print('Employee is not eligible for any incentive.')
        close_connection()
        return None

    approval_input = input(f"Employee {emp_id} is eligible for an incentive of Rs.{incentive_amount}. Approve this incentive? (y/n): ").strip().lower()
    
    if approval_input == 'y':
        mycursor.execute("UPDATE incentive_eligibility SET admin_approval = 'Y' WHERE emp_id = %s AND month = %s AND year = %s;",(emp_id, datetime.now().month, datetime.now().year))
        print('Incentive approved.')
        mydb.commit()
        close_connection()
        send_email(employee_details(emp_id)[3], f"Incentive Approved for {datetime.now().strftime('%B %Y')}", f"Dear {employee_details(emp_id)[1]},\n\nYour incentive of Rs.{incentive_amount} for {datetime.now().strftime('%B %Y')} has been approved by the admin.\n\nBest regards,\nHealthPro Team")
    elif approval_input == 'n':
        mycursor.execute("UPDATE incentive_eligibility SET admin_approval = 'N' WHERE emp_id = %s AND month = %s AND year = %s;",(emp_id, datetime.now().month, datetime.now().year))
        print('Incentive not approved.')
        mydb.commit()
        close_connection()
        send_email(employee_details(emp_id)[3], f"Incentive Not Approved for {datetime.now().strftime('%B %Y')}", f"Dear {employee_details(emp_id)[1]},\n\nYour incentive of Rs.{incentive_amount} for {datetime.now().strftime('%B %Y')} has been rejected by the admin.\n\nBest regards,\nHealthPro Team")
    else:
        print('Invalid input. Incentive approval status not updated.')
        mydb.commit()
        close_connection()
    show_targets_table()

def new_employee():
    name=input('Enter name of employee: ').strip().title()
    dob=input('Enter date of birth of employee in the format YYYY-MM-DD: ').strip()
    while True:
        emp_phone=input('Enter phone number of employee: ').strip()
        if phone_valid(emp_phone):
            break
    firstname,lastname=name.lower().split()[0],name.lower().split()[-1]
    designation=input('Enter designation of employee: ').strip().title()
    role=input("Enter 'A' if employee is an admin and enter 'S' if employee is salesmen: ").strip().upper()
    if role=='A':
        designation=designation+' (A)'
        prefix_id = 'HP02'
    else:
        prefix_id='HP01'
    emp_email=f'{firstname}.{lastname}@healthpro.in'
    print(f"Generated email for employee is {emp_email}.")
    open_connection()
    mycursor.execute("SELECT emp_id FROM employee_details WHERE emp_id LIKE %s ORDER BY emp_id DESC LIMIT 1",((prefix_id+'%'),))
    id=mycursor.fetchone()
    if not id:
        print('No records in table.')
        close_connection()
        return None
    emp_id= 'HP0' + str(int(id[0][3:])+1)
    mycursor.execute('INSERT INTO employee_details (emp_id,emp_name,dob,designation,emp_email,emp_phone) VALUES (%s,%s,%s,%s,%s,%s)',(emp_id,name,dob,designation,emp_email,emp_phone))
    mydb.commit()
    close_connection()
    print('Details successfully inserted.')
    print('Switch to login page to enter employee password.')    

def target_allocation():
    try:
        ch = input("Do you want to delete previous targets?(y/n): ").strip()
        if ch.lower()=='y':
            open_connection()
            mycursor.execute("DELETE FROM targets;")
            mydb.commit()
            close_connection()
            print("Existing targets cleared.")
        total_target_sales =0.0
        total_target_lines=0
        while True:
            sku = input("Enter SKU number to target (press Q to finish SKU entry): ").strip()
            if sku.lower() == 'q':
                break
            if not sku_exists(sku):
                continue
            while True:
                try:
                    target_sales = float(input("Enter target sales for this SKU: "))
                    break
                except ValueError:
                    print("Invalid sales value. Enter a numeric target sales.")
            while True:
                try:
                    target_lines = int(input("Enter target lines sold for this SKU: "))
                    break
                except ValueError:
                    print("Invalid lines value. Enter an integer target lines sold.")
            today = datetime.now().date()
            open_connection()
            mycursor.execute("SELECT sku FROM erp WHERE sku=%s AND end_of_day=%s;", (sku, today))
            if mycursor.fetchone():
                mycursor.execute("UPDATE erp SET target_sales=%s WHERE sku=%s AND end_of_day=%s;",(target_sales, sku, today))
            else:
                mycursor.execute("INSERT INTO erp (end_of_day, sku, units_produced, units_ordered, units_inventory, total_sales, target_sales) VALUES (%s, %s, %s, %s, %s, %s, %s);",(today, sku, 0, 0, 0, 0.0, target_sales))
            mydb.commit()
            close_connection()
            total_target_sales+=target_sales
            total_target_lines+=target_lines
            print(f"Target saved for SKU {sku}: sales={target_sales}, lines={target_lines}.")

        if not total_target_lines:
            print("No SKU targets were entered.")
            return None
        print(f"\nCumulative SKU target sales: {total_target_sales}\nCumulative SKU target lines sold: {total_target_lines}\n")

        while True:
            emp_id = input("Enter Employee ID to allocate targets to (press Q to stop): ").strip()
            if emp_id.lower() == 'q':
                break
            elif not employee_details(emp_id):
                continue
            open_connection()
            mycursor.execute("SELECT SUM(salescore) FROM incentive_eligibility WHERE month=%s AND year=%s;",(emp_id, (datetime.now().month -1)%12, datetime.now().year))
            total_sales_score = mycursor.fetchone()[0]
            mycursor.execute("SELECT salescore FROM incentive_eligibility WHERE emp_id=%s AND month=%s AND year=%s;",(emp_id, (datetime.now().month -1)%12, datetime.now().year))
            score_row = mycursor.fetchone()
            if score_row and score_row[0] and total_sales_score:
                sales_score_contribution = float(score_row[0])/total_sales_score
            else:
                sales_score_contribution=0
            suggested_sales = round(total_target_sales * (sales_score_contribution*1.2),2)
            suggested_lines = int(total_target_lines * sales_score_contribution)
            print(f"Suggested allocation for {emp_id}:\n  Sales target: {suggested_sales:.2f}\n  Lines sold target: {suggested_lines}\n")
            final_sales = float(input("Enter final target sales to assign(in Rs.): "))
            final_lines = int(input("Enter final target lines sold to assign(it is a whole number only): "))
            mycursor.execute("SELECT emp_id FROM targets WHERE emp_id=%s;", (emp_id,))
            if mycursor.fetchone():
                mycursor.execute("UPDATE targets SET target_sales=%s, target_ls=%s WHERE emp_id=%s;",(final_sales, final_lines, emp_id))
            else:
                mycursor.execute("INSERT INTO targets (emp_id, sales, tls, target_sales, target_ls) VALUES (%s, %s, %s, %s, %s);",(emp_id, 0.0, 0, final_sales, final_lines))
            mydb.commit()
            close_connection()
            print(f"Target allocation recorded for employee {emp_id}.\n")
    finally:
        show_targets_table()

def clear_daywise_attendance():
    open_connection()
    mycursor.execute("DELETE FROM daywise_attendance")
    mydb.commit()
    close_connection()
    print("Daywise attendance cleared for next day.")


def salesperson(emp_id):
    open_connection()
    mycursor.execute("SELECT areacode FROM area WHERE emp_id=%s;",(emp_id,))
    area_code = mycursor.fetchone()
    if not area_code:
        print("No area allocated to this employee. Contact Admin.")
    else:
        print(f"Area allocated to employee {emp_id}: {area_code[0]}")
    mycursor.fetchall()
    close_connection()
    while True:
        print("\nMenu Options:\n1. View Team Members\n2. See your monthly attendance\n3. See your monthly target achievement\n4. See leaderboard\n5. See your profile\n6. See outlet details\n7. Add new outlet\n8. Update outlet details\n9. Delete outlet\n10. See SKU details\n11. Add call\n12. Punch Out\n\n")
        menu1=input("Enter your choice(press q to quit): ").strip()
        if menu1=='1':
            open_connection()
            mycursor.execute("SELECT emp_name, designation FROM employee_details WHERE is_active=1;")
            team_members = mycursor.fetchall()
            close_connection()
            if not team_members:
                print("No active sales employees found.")
                print("Returning to menu...")
                continue
            headers = ["Employee Name", "Designation"]
            print('\n', tabulate(team_members, headers, tablefmt="simple"))
        elif menu1=='2':
            check_monthly_attendence(emp_id)
        elif menu1=='3':
            see_target_achievement(emp_id)
        elif menu1=='4':
            visual_leaderboard()
        elif menu1=='5':
            see_profile(emp_id)
            menu2 = input("Do you want to update your profile? (y/n): ").strip().lower()
            if menu2 == 'y':
                update_profile(emp_id)
        elif menu1=='6':
            if not area_code:
                print("No area allocated to this employee. Contact Admin.")
                print("Returning to menu...")
                continue
            else:
                show_outlets(area_code[0])
        elif menu1=='7':
            create_outlet()
        elif menu1=='8':
            outletno = input("Enter Outlet Number to update: ").strip()
            change_outlet_details_onfield(outletno)
        elif menu1=='9':
            outletno = input("Enter Outlet Number to delete: ").strip()
            delete_outlet(outletno)
        elif menu1=='10':
            sku_details_display()
        elif menu1=='11':
            outletno=input("Enter outlet number for which order is made: ").strip()
            print("First do stock counting of each SKU in the outlet and then add the order.")
            sales_counting(outletno)
            print("Stock counting done.")
            menu3=input("Do you want to add a new order? (y/n): ").strip().lower()
            if menu3=='y':
                neworder(emp_id, outletno)
            else:
                print("Your call was recorded as Unproductive. No order was added.")
        elif menu1=='12':
            punch_out(emp_id)
            print("You have successfully punched out. Have a good day!")
            break
        elif menu1.lower()=='q':
            print("Exiting menu...")
            break
        else:
            print("Invalid choice. Please try again.")
        
        print("Returning to menu...")
    
def ASM(emp_id):
    print(f"Welcome ASM {emp_id}!")
    while True:
        print("\nMenu Options:\n1. Continue with your salesperson functions and profile\n2. See area details\n3. Allocate Area to Employee\n4. Check daywise attendance of Employees\n5. Punch Out\n\n")
        menu1=input("Enter your choice(press q to quit): ").strip()
        if menu1=='1':
            salesperson(emp_id)
        elif menu1=='2':
            area_assigned()
        elif menu1=='3':
            area_allocation_by_admin()
        elif menu1=='4':
            check_daywise_attendence()
        elif menu1=='5':
            punch_out(emp_id)
            print("You have successfully punched out. Have a good day!")
            break
        elif menu1.lower()=='q':
            print("Exiting menu...")
            break
        else:
            print("Invalid choice. Please try again.")
        
        print("Returning to menu...")

def admin(emp_id):
    print(f"Welcome Admin {emp_id}!")
    while True:
        print("\nMenu Options:\n1.Employee Details\n2. See Attendance\n3. Target Setting\n4. SKU Details\n5. See Area Details\n6.See Order Details\n7. Punch Out\n\n")
        menu1=input("Enter your choice(press q to quit): ").strip()
        if menu1=='1':
            print("\nEmployee Details Menu:\n1. Create New Employee\n2. Update Employee Details\n3. Delete Employee\n4. View Employee Details\n5.Incentive approval\n\n")
            menu2=input("Enter your choice(press enter to rollback): ").strip()
            if menu2=='1':
                new_employee()
            elif menu2=='2':
                update_emp_details()
            elif menu2=='3':
                emp_id_to_delete = input("Enter Employee ID to delete: ").strip()
                delete_emp(emp_id_to_delete)
            elif menu2=='4':
                open_connection()
                mycursor.execute("SELECT emp_id, emp_name, designation, emp_email, emp_phone FROM employee_details WHERE is_active=1;")
                employees = mycursor.fetchall()
                close_connection()
                if not employees:
                    print("No active employees found.")
                    print("Returning to menu...")
                    continue
                headers = ["Employee ID", "Employee Name", "Designation", "Email", "Phone"]
                print('\n', tabulate(employees, headers, tablefmt="simple"))
            elif menu2=='5':
                incentive_table_display()
                emp_id_to_approve = input("Enter Employee ID to approve incentive: ").strip()
                admin_approval_for_incentive(emp_id_to_approve)
        elif menu1=='2':
            menu3=input("Enter '1' to see daywise attendance of employees or enter '2' to see monthly attendance of employees or '3' to clear daywise attendance: ").strip()
            if menu3=='1':
                check_daywise_attendence()
            elif menu3=='2':
                emp_id_for_attendance = input("Enter Employee ID to see monthly attendance details: ").strip()
                check_monthly_attendence(emp_id_for_attendance)
            elif menu3=='3':
                confirm = input("Are you sure you want to clear daywise attendance for next day? (y/n): ").strip().lower()
                if confirm == 'y':
                    clear_daywise_attendance()
                else:
                    print("Daywise attendance not cleared.")
        elif menu1=='3':
            target_allocation()
        elif menu1=='4':
            print("\nSKU Details Menu:\n1. View SKU Details\n2. Add New SKU\n3. Update SKU Details\n4. Delete SKU\n\n")
            menu4=input("Enter your choice(press enter to rollback): ").strip()
            if menu4=='1':
                sku_details_display()
            elif menu4=='2':
                add_sku()
            elif menu4=='3':
                update_sku()
            elif menu4=='4':
                delete_sku()
        elif menu1=='5':
            area_assigned()
        elif menu1=='6':
            orderno=input("Enter Order Number to see details: ").strip()
            open_connection()
            print(see_order_details(orderno))
            close_connection()
            menu5=input("Want to update order details? (y/n): ").strip()
            if menu5.lower()=='y':
                change_orderdetails()
        elif menu1=='7':
            punch_out(emp_id)
            print("You have successfully punched out. Have a good day!")
            break
        elif menu1.lower()=='q':
            print("Exiting menu...")
            break
        else:
            print("Invalid choice. Please try again.")
        print("Returning to menu...")

def GM(emp_id):
    print(f"Welcome GM {emp_id}!")
    while True:
        print("\nMenu Options:\n1. Continue with your admin functions and profile\n2. See incentive table\n3. Sales Forcasting\n4. See ERP\n5. Punch Out\n\n")
        menu1=input("Enter your choice(press q to quit): ").strip()
        if menu1=='1':
            admin(emp_id)
        elif menu1=='2':
            incentive_table_display()
        elif menu1=='3':
            sales_forcast()
        elif menu1=='4':
            month=int(input("Enter month in MM format: ").strip())
            sku= input("Enter SKU number to see ERP data: ").strip()
            if sku:
                see_erp(month, sku)
            else:
                see_erp(month)
            menu2=input("Want to insert new ERP data? (y/n): ").strip()
            if menu2.lower()=='y':
                insert_erp()
        elif menu1=='5':
            punch_out(emp_id)
            print("You have successfully punched out. Have a good day!")
            break
        elif menu1.lower()=='q':
            print("Exiting menu...")
            break
        else:
            print("Invalid choice. Please try again.")
        print("Returning to menu...")

def final_flow():
    while True:
        print("===========================================================================")
        print("              Welcome to HealthPro Sales Force Management System           ")
        print("===========================================================================\n")
        print("1. Login\n2. New Employee Password/Forgot Password\n3. Exit\n")
        choice = input("Enter your choice: ").strip()
        if choice == '1':
            user = login()
            if user:
                des,id= user[0],user[1]
            else:
                print("Login failed. Exiting interface.")
                break
            if des=='MASTER':
                GM(id)
            elif des=='ADMIN':
                admin(id)
            elif des=='ASM':
                ASM(id)
            elif des=='SALES':
                salesperson(id)
        elif choice =='2':
            new_employee_password()
        elif choice =='3':
            print("Exiting the system. Goodbye!")
            break
        else:
            print("Invalid choice. Please restart the program and select a valid option.")
    print("Thank you for using HealthPro Sales Force Management System. Goodbye!")


final_flow()

