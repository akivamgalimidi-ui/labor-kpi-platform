import os
import xlsxwriter
from database import get_db
from datetime import datetime

def create_excel_export(batch_id=None):
    export_dir = os.path.join(os.getcwd(), 'exports')
    os.makedirs(export_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(export_dir, f"Avir_Labor_Analytics_{timestamp}.xlsx")
    
    wb = xlsxwriter.Workbook(filepath)
    
    # Formats
    header_fmt = wb.add_format({'bold': True, 'bg_color': '#f3f4f6', 'border': 1})
    currency_fmt = wb.add_format({'num_format': '$#,##0', 'border': 1})
    number_fmt = wb.add_format({'num_format': '#,##0.0', 'border': 1})
    pct_fmt = wb.add_format({'num_format': '0.0%', 'border': 1})
    border_fmt = wb.add_format({'border': 1})
    
    conn = get_db()
    cur = conn.cursor()

    # Get sorted periods
    query = "SELECT DISTINCT period_date FROM facility_period_metrics"
    if batch_id:
        query += f" WHERE batch_id = {batch_id}"
    query += " ORDER BY period_date"
    cur.execute(query)
    periods = [r[0] for r in cur.fetchall()]

    # 1. Executive Portfolio Dashboard
    ws_exec = wb.add_worksheet("Executive Portfolio")
    ws_exec.write(0, 0, "Executive Portfolio Dashboard", wb.add_format({'bold': True, 'size': 14}))
    ws_exec.write(2, 0, "Period", header_fmt)
    ws_exec.write(2, 1, "Total OT $", header_fmt)
    ws_exec.write(2, 2, "Total Bonus $", header_fmt)
    
    q_exec = "SELECT period_date, SUM(ot_dollars), SUM(bonus_dollars) FROM facility_period_metrics WHERE is_total_row = 0"
    if batch_id:
        q_exec += f" AND batch_id = {batch_id}"
    q_exec += " GROUP BY period_date ORDER BY period_date"
    cur.execute(q_exec)
    
    for row_idx, r in enumerate(cur.fetchall(), start=3):
        ws_exec.write(row_idx, 0, r[0], border_fmt)
        ws_exec.write(row_idx, 1, r[1] or 0, currency_fmt)
        ws_exec.write(row_idx, 2, r[2] or 0, currency_fmt)

    # 2. Portfolio Facility Trends (Flat)
    ws_trends = wb.add_worksheet("Portfolio Facility Trends")
    headers = ["Facility", "Region", "Acq Group", "Pay Cycle"]
    for p in periods:
        headers.extend([f"OT $ {p}", f"OT Hrs {p}", f"Bonus $ {p}", f"HPPD {p}", f"PPD $ {p}"])
        
    for col, h in enumerate(headers):
        ws_trends.write(0, col, h, header_fmt)
        
    q_facs = "SELECT DISTINCT name, region, acquisition_group, payroll_schedule_group FROM facilities"
    cur.execute(q_facs)
    facilities = cur.fetchall()
    
    row = 1
    for fac in facilities:
        fname = fac[0]
        ws_trends.write(row, 0, fname, border_fmt)
        ws_trends.write(row, 1, fac[1] or "Unknown", border_fmt)
        ws_trends.write(row, 2, fac[2] or "Unknown", border_fmt)
        ws_trends.write(row, 3, fac[3] or "Unknown", border_fmt)
        
        q_data = "SELECT period_date, ot_dollars, ot_hours, bonus_dollars, direct_care_hppd, direct_care_ppd FROM facility_period_metrics WHERE facility_name = ?"
        if batch_id:
            q_data += f" AND batch_id = {batch_id}"
        cur.execute(q_data, (fname,))
        data = {r[0]: r for r in cur.fetchall()}
        
        col = 4
        for p in periods:
            d = data.get(p, (None, 0, 0, 0, 0, 0))
            ws_trends.write(row, col, d[1] or 0, currency_fmt)
            ws_trends.write(row, col+1, d[2] or 0, number_fmt)
            ws_trends.write(row, col+2, d[3] or 0, currency_fmt)
            ws_trends.write(row, col+3, d[4] or 0, number_fmt)
            ws_trends.write(row, col+4, d[5] or 0, currency_fmt)
            col += 5
        row += 1

    # 3. Employee OT Detail
    ws_ot = wb.add_worksheet("Employee OT Detail")
    ot_headers = ["Facility", "Employee", "Department", "Position", "Period", "OT $", "OT Hrs"]
    for col, h in enumerate(ot_headers): ws_ot.write(0, col, h, header_fmt)
    q_ot = "SELECT facility_name, employee_name, department, position, period_date, value FROM ot_detail_lines WHERE metric_group = 'OT Dollars ($)'"
    if batch_id: q_ot += f" AND batch_id = {batch_id}"
    cur.execute(q_ot)
    for r_idx, r in enumerate(cur.fetchall(), start=1):
        ws_ot.write(r_idx, 0, r[0], border_fmt)
        ws_ot.write(r_idx, 1, r[1], border_fmt)
        ws_ot.write(r_idx, 2, r[2] or "Unknown", border_fmt)
        ws_ot.write(r_idx, 3, r[3] or "Unknown", border_fmt)
        ws_ot.write(r_idx, 4, r[4], border_fmt)
        ws_ot.write(r_idx, 5, r[5] or 0, currency_fmt)

    # 4. Employee Bonus Detail
    ws_bonus = wb.add_worksheet("Employee Bonus Detail")
    b_headers = ["Facility", "Employee", "Bonus Type", "Position", "Period", "Bonus $"]
    for col, h in enumerate(b_headers): ws_bonus.write(0, col, h, header_fmt)
    q_bonus = "SELECT facility_name, employee_name, bonus_type, position, period_date, bonus_dollars FROM bonus_detail_lines"
    if batch_id: q_bonus += f" WHERE batch_id = {batch_id}"
    cur.execute(q_bonus)
    for r_idx, r in enumerate(cur.fetchall(), start=1):
        ws_bonus.write(r_idx, 0, r[0], border_fmt)
        ws_bonus.write(r_idx, 1, r[1], border_fmt)
        ws_bonus.write(r_idx, 2, r[2] or "Unknown", border_fmt)
        ws_bonus.write(r_idx, 3, r[3] or "Unknown", border_fmt)
        ws_bonus.write(r_idx, 4, r[4], border_fmt)
        ws_bonus.write(r_idx, 5, r[5] or 0, currency_fmt)

    wb.close()
    return filepath

if __name__ == "__main__":
    create_excel_export()
