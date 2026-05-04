"""
index.py — Vercel Serverless Entry Point
Complete rebuild: returns full normalized BI payload for all 15 dashboard tabs.
"""

import os, sys, uuid, json, base64, traceback
from datetime import datetime
sys.path.insert(0, os.path.join(os.getcwd(), 'api'))

from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename

from database import init_db, get_db
from parser import parse_workbook_json, detect_payroll_schedule_groups
from kpi_engine import (
    compute_portfolio_kpis, compute_same_facility_trend,
    compute_labor_pressure_scores, compute_region_kpis,
    compute_acq_group_kpis, run_reconciliation,
    compute_facility_flat_metrics, compute_pay_cycle_mapping,
    compute_employee_review, compute_bonus_by_type_summary,
    compute_data_quality_report
)
from export import create_excel_export

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
init_db()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/upload', methods=['POST'])
def upload_file():
    wb_data = request.get_json()
    if not wb_data or 'sheets' not in wb_data:
        return jsonify({'error': 'No JSON data received'}), 400

    batch_uuid = str(uuid.uuid4())
    secure_name = secure_filename(wb_data.get('filename', 'upload.xlsx'))

    try:
        parsed = parse_workbook_json(wb_data['sheets'])
        schedule_groups = detect_payroll_schedule_groups(parsed)

        db = get_db()
        cur = db.cursor()

        cur.execute("""
            INSERT INTO upload_batches (batch_uuid, filename, pay_periods_detected, facilities_detected, sheets_detected, status)
            VALUES (?, ?, ?, ?, ?, 'active')
        """, (
            batch_uuid, secure_name,
            json.dumps(parsed['pay_periods']),
            len(parsed['facilities']),
            json.dumps(parsed.get('sheets_found', []))
        ))
        batch_id = cur.lastrowid

        # Store schedule groups / facilities — also set acquisition_group from OT data
        fac_acq_map = {}
        for ot in parsed.get('ot_detail', []):
            if ot.get('acquisition_group'):
                fac_acq_map[ot['facility_name']] = ot['acquisition_group']

        for fac_name, fac_info in schedule_groups.items():
            grp = fac_info.get('schedule_group', 'Unknown')
            acq = fac_acq_map.get(fac_name, 'Unknown')
            cur.execute("INSERT OR IGNORE INTO payroll_schedule_groups (name) VALUES (?)", (grp,))
            cur.execute("""
                INSERT INTO facilities (name, payroll_schedule_group, acquisition_group, region)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    payroll_schedule_group=excluded.payroll_schedule_group,
                    acquisition_group=COALESCE(excluded.acquisition_group, facilities.acquisition_group)
            """, (fac_name, grp, acq, acq))

        # OT detail (Batch insert)
        ot_rows = [
            (batch_id, ot.get('acquisition_group'), ot['facility_name'],
             ot.get('department'), ot.get('position'), ot.get('employee_name'),
             ot['period_date'], ot.get('value'), ot.get('metric_group'))
            for ot in parsed.get('ot_detail', [])
        ]
        cur.executemany("""
            INSERT INTO ot_detail_lines
            (batch_id, acquisition_group, facility_name, department, position, employee_name, period_date, value, metric_group)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ot_rows)

        # Bonus detail (Batch insert)
        bonus_rows = [
            (batch_id, b.get('acquisition_group'), b['facility_name'],
             b.get('bonus_type'), b.get('position'), b.get('employee_name'),
             b['period_date'], b.get('bonus_dollars'))
            for b in parsed.get('bonus_by_ppe', [])
        ]
        cur.executemany("""
            INSERT INTO bonus_detail_lines
            (batch_id, acquisition_group, facility_name, bonus_type, position, employee_name, period_date, bonus_dollars)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, bonus_rows)

        # PPD metrics (Batch insert)
        ppd_rows = [
            (batch_id, p.get('metric_type'), p.get('acquisition_group'),
             p['facility_name'], p['period_date'], p.get('value'))
            for p in parsed.get('ppd_metrics', [])
        ]
        cur.executemany("""
            INSERT INTO ppd_metric_lines
            (batch_id, metric_type, acquisition_group, facility_name, period_date, value)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ppd_rows)

        # Build facility_period_metrics summary
        cur.execute("""
            INSERT INTO facility_period_metrics
            (batch_id, facility_name, acquisition_group, period_date, ot_dollars, ot_hours, bonus_dollars, direct_care_hppd, direct_care_ppd)
            SELECT
                ? as batch_id,
                f.name as facility_name,
                MAX(ot.acquisition_group) as acquisition_group,
                p.period_date,
                SUM(CASE WHEN ot.metric_group = 'OT Dollars ($)' THEN ot.value ELSE 0 END) as ot_dollars,
                SUM(CASE WHEN ot.metric_group = 'OT Hours' THEN ot.value ELSE 0 END) as ot_hours,
                (SELECT SUM(bonus_dollars) FROM bonus_detail_lines WHERE batch_id=? AND facility_name=f.name AND period_date=p.period_date) as bonus_dollars,
                (SELECT value FROM ppd_metric_lines WHERE batch_id=? AND facility_name=f.name AND period_date=p.period_date AND metric_type='Direct Care HPPD' LIMIT 1) as hppd,
                (SELECT value FROM ppd_metric_lines WHERE batch_id=? AND facility_name=f.name AND period_date=p.period_date AND metric_type='Direct Care PPD' LIMIT 1) as ppd
            FROM facilities f
            CROSS JOIN (SELECT DISTINCT period_date FROM ot_detail_lines WHERE batch_id=?) p
            LEFT JOIN ot_detail_lines ot ON ot.facility_name=f.name AND ot.period_date=p.period_date AND ot.batch_id=?
            GROUP BY f.name, p.period_date
            HAVING ot_dollars > 0 OR bonus_dollars > 0 OR hppd IS NOT NULL
        """, (batch_id, batch_id, batch_id, batch_id, batch_id, batch_id))

        # ── Populate Rollup Tables ────────────────────────────────────────────
        # Filter out NULL groups/regions to avoid NOT NULL constraint violations
        cur.execute("""
            INSERT OR IGNORE INTO acq_group_period_metrics (batch_id, acquisition_group, metric_type, period_date, value)
            SELECT batch_id, COALESCE(acquisition_group, 'Unknown'), metric_group, period_date, SUM(value)
            FROM ot_detail_lines WHERE batch_id=?
            GROUP BY COALESCE(acquisition_group, 'Unknown'), metric_group, period_date
        """, (batch_id,))
        
        cur.execute("""
            INSERT OR IGNORE INTO region_period_metrics (batch_id, region, metric_type, period_date, value)
            SELECT fpm.batch_id, COALESCE(f.region, f.acquisition_group, 'Unknown'), 'OT Dollars', fpm.period_date, SUM(fpm.ot_dollars)
            FROM facility_period_metrics fpm
            JOIN facilities f ON fpm.facility_name = f.name
            WHERE fpm.batch_id=?
            GROUP BY COALESCE(f.region, f.acquisition_group, 'Unknown'), fpm.period_date
        """, (batch_id,))

        db.commit()
        db.close()

        # QA Run
        run_reconciliation(batch_id)

        # ── Compute Dashboard JSON (No Excel generation yet to save time) ─────
        portfolio_trend     = compute_portfolio_kpis(batch_id)
        facility_trends     = compute_same_facility_trend(batch_id)
        labor_pressure      = compute_labor_pressure_scores(batch_id)
        region_kpis         = compute_region_kpis(batch_id)
        acq_kpis            = compute_acq_group_kpis(batch_id)
        facility_flat       = compute_facility_flat_metrics(batch_id)
        pay_cycle_mapping   = compute_pay_cycle_mapping(batch_id, schedule_groups)
        employee_review     = compute_employee_review(batch_id)
        bonus_by_type       = compute_bonus_by_type_summary(batch_id)
        data_quality        = compute_data_quality_report(batch_id, parsed)

        db3 = get_db()
        qa_results = [dict(r) for r in db3.execute(
            "SELECT * FROM reconciliation_results WHERE batch_id=?", (batch_id,)).fetchall()]
        history = [dict(r) for r in db3.execute(
            "SELECT * FROM upload_batches ORDER BY uploaded_at DESC LIMIT 5").fetchall()]
        db3.close()

        return jsonify({
            'message': 'File processed successfully',
            'batch_id': batch_id,
            'facilities_detected': len(parsed['facilities']),
            'pay_periods': parsed['pay_periods'],
            'facilities': parsed['facilities'],
            'regions': sorted(set(r.get('region') or r.get('acquisition_group') or 'Unknown' for r in labor_pressure)),
            'acquisition_groups': sorted(set(r.get('acquisition_group') or 'Unknown' for r in labor_pressure)),
            'dashboard_data': {
                'portfolio_trend':   portfolio_trend,
                'facility_trends':   facility_trends,
                'labor_pressure':    labor_pressure,
                'region_kpis':       region_kpis,
                'acq_kpis':          acq_kpis,
                'facility_flat':     facility_flat,
                'pay_cycle_mapping': pay_cycle_mapping,
                'employee_review':   employee_review,
                'bonus_by_type':     bonus_by_type,
                'data_quality':      data_quality,
                'qa_results':        qa_results,
                'history':           history,
            }
        })

    except Exception as e:
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500


@app.route('/api/facility/<path:facility_name>', methods=['GET'])
def get_facility_detail(facility_name):
    """Return employee/dept/period detail for a single facility drilldown."""
    batch_id = request.args.get('batch_id')
    if not batch_id:
        return jsonify({'error': 'batch_id required'}), 400
    db = get_db()
    ot_rows = [dict(r) for r in db.execute("""
        SELECT employee_name, department, position, period_date,
               SUM(CASE WHEN metric_group='OT Dollars ($)' THEN value END) as ot_dollars,
               SUM(CASE WHEN metric_group='OT Hours' THEN value END) as ot_hours
        FROM ot_detail_lines
        WHERE batch_id=? AND facility_name=?
        GROUP BY employee_name, department, position, period_date ORDER BY ot_dollars DESC
    """, (batch_id, facility_name)).fetchall()]
    bonus_rows = [dict(r) for r in db.execute("""
        SELECT employee_name, bonus_type, position, period_date, SUM(bonus_dollars) as bonus_dollars
        FROM bonus_detail_lines WHERE batch_id=? AND facility_name=?
        GROUP BY employee_name, bonus_type, position, period_date ORDER BY bonus_dollars DESC
    """, (batch_id, facility_name)).fetchall()]
    db.close()
    return jsonify({'ot_detail': ot_rows, 'bonus_detail': bonus_rows})


@app.route('/api/export/excel', methods=['GET'])
def export_excel():
    batch_id = request.args.get('batch_id')
    try:
        filepath = create_excel_export(batch_id)
        with open(filepath, 'rb') as f:
            data = base64.b64encode(f.read()).decode('utf-8')
        return jsonify({'filename': os.path.basename(filepath), 'data_base64': data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)
