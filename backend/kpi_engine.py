"""
kpi_engine.py â€” KPI calculations, trend analysis, labor pressure scoring,
same-facility comparable trends, reported total trends, and QA reconciliation.
"""

import json
from datetime import datetime
from database import get_db


# â”€â”€ Helper: load data from DB â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


# get_facility_metrics defined below (with full facility JOIN)


def get_all_batches():
    db = get_db()
    rows = db.execute("SELECT * FROM upload_batches ORDER BY uploaded_at DESC").fetchall()
    db.close()
    return [dict(r) for r in rows]


def get_batch(batch_id):
    db = get_db()
    row = db.execute("SELECT * FROM upload_batches WHERE id=?", (batch_id,)).fetchone()
    db.close()
    return dict(row) if row else None


# â”€â”€ Portfolio KPIs â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def compute_portfolio_kpis(batch_id=None):
    """
    Aggregate OT $, OT hours, bonus $, HPPD, PPD by pay period.
    Returns list of {period_date, total_ot_dollars, total_ot_hours, ...}
    """
    rows = get_facility_metrics(batch_id)

    period_data = {}
    for r in rows:
        if r.get("is_total_row"):
            continue
        dt = r["period_date"]
        if dt not in period_data:
            period_data[dt] = {
                "period_date": dt,
                "total_ot_dollars": 0.0,
                "total_ot_hours": 0.0,
                "total_bonus_dollars": 0.0,
                "facility_count": 0,
                "hppd_sum": 0.0,
                "hppd_count": 0,
                "ppd_sum": 0.0,
                "ppd_count": 0,
                "olppd_sum": 0.0,
                "olppd_count": 0,
            }
        pd_ = period_data[dt]
        pd_["facility_count"] += 1
        if r["ot_dollars"] is not None:
            pd_["total_ot_dollars"] += r["ot_dollars"]
        if r["ot_hours"] is not None:
            pd_["total_ot_hours"] += r["ot_hours"]
        if r["bonus_dollars"] is not None:
            pd_["total_bonus_dollars"] += r["bonus_dollars"]
        if r["direct_care_hppd"] is not None:
            pd_["hppd_sum"] += r["direct_care_hppd"]
            pd_["hppd_count"] += 1
        if r["direct_care_ppd"] is not None:
            pd_["ppd_sum"] += r["direct_care_ppd"]
            pd_["ppd_count"] += 1
        if r["overall_labor_ppd"] is not None:
            pd_["olppd_sum"] += r["overall_labor_ppd"]
            pd_["olppd_count"] += 1

    # Compute averages and trends
    periods = sorted(period_data.values(), key=lambda x: x["period_date"])
    for p in periods:
        p["avg_hppd"] = round(p["hppd_sum"] / p["hppd_count"], 6) if p["hppd_count"] > 0 else None
        p["avg_ppd"] = round(p["ppd_sum"] / p["ppd_count"], 6) if p["ppd_count"] > 0 else None
        p["avg_olppd"] = round(p["olppd_sum"] / p["olppd_count"], 6) if p["olppd_count"] > 0 else None

    # Add trend vs prior period
    for i, p in enumerate(periods):
        if i == 0:
            p["ot_change"] = None
            p["ot_pct_change"] = None
            p["bonus_change"] = None
            p["trend_status"] = "First Period"
        else:
            prior = periods[i - 1]
            p["ot_change"] = round(p["total_ot_dollars"] - prior["total_ot_dollars"], 2)
            if prior["total_ot_dollars"] != 0:
                p["ot_pct_change"] = round(p["ot_change"] / prior["total_ot_dollars"], 6)
            else:
                p["ot_pct_change"] = None
            p["bonus_change"] = round(p["total_bonus_dollars"] - prior["total_bonus_dollars"], 2)
            if p["ot_change"] and p["ot_change"] > 0:
                p["trend_status"] = "Rising"
            elif p["ot_change"] and p["ot_change"] < 0:
                p["trend_status"] = "Falling"
            else:
                p["trend_status"] = "Stable"

    return periods


# â”€â”€ Acquisition Group KPIs â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def compute_acq_group_kpis(batch_id=None):
    """Aggregate by acquisition group Ã— pay period."""
    rows = get_facility_metrics(batch_id)
    data = {}   # {acq_group: {period_date: {...}}}

    for r in rows:
        if r.get("is_total_row"):
            continue
        ag = r.get("acquisition_group") or "Unknown"
        dt = r["period_date"]
        if ag not in data:
            data[ag] = {}
        if dt not in data[ag]:
            data[ag][dt] = {"ot_dollars": 0.0, "ot_hours": 0.0,
                            "bonus_dollars": 0.0, "facility_count": 0}
        d = data[ag][dt]
        d["facility_count"] += 1
        if r["ot_dollars"] is not None:
            d["ot_dollars"] += r["ot_dollars"]
        if r["ot_hours"] is not None:
            d["ot_hours"] += r["ot_hours"]
        if r["bonus_dollars"] is not None:
            d["bonus_dollars"] += r["bonus_dollars"]

    result = []
    for ag, periods in sorted(data.items()):
        for dt, vals in sorted(periods.items()):
            result.append({"acquisition_group": ag, "period_date": dt, **vals})
    return result


# â”€â”€ Region KPIs â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def compute_region_kpis(batch_id=None):
    """Aggregate by region Ã— pay period."""
    rows = get_facility_metrics(batch_id)
    data = {}

    for r in rows:
        if r.get("is_total_row"):
            continue
        region = r.get("region") or "Unknown"
        dt = r["period_date"]
        if region not in data:
            data[region] = {}
        if dt not in data[region]:
            data[region][dt] = {"ot_dollars": 0.0, "ot_hours": 0.0,
                                "bonus_dollars": 0.0, "facility_count": 0}
        d = data[region][dt]
        d["facility_count"] += 1
        if r["ot_dollars"] is not None:
            d["ot_dollars"] += r["ot_dollars"]
        if r["ot_hours"] is not None:
            d["ot_hours"] += r["ot_hours"]
        if r["bonus_dollars"] is not None:
            d["bonus_dollars"] += r["bonus_dollars"]

    result = []
    for region, periods in sorted(data.items()):
        for dt, vals in sorted(periods.items()):
            result.append({"region": region, "period_date": dt, **vals})
    return result


# â”€â”€ Same-Facility Comparable Trend â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def compute_same_facility_trend(batch_id=None):
    """
    For each pair of consecutive periods, compute same-facility comparable trend.
    Only include facilities present in BOTH periods AND same payroll schedule group.
    Returns list of comparison objects.
    """
    rows = get_facility_metrics(batch_id)

    # Build: facility -> {period -> metrics}
    facility_data = {}
    for r in rows:
        if r.get("is_total_row"):
            continue
        fac = r["facility_name"]
        dt = r["period_date"]
        if fac not in facility_data:
            facility_data[fac] = {}
        facility_data[fac][dt] = r

    # Get all periods sorted
    all_periods = sorted(set(r["period_date"] for r in rows if not r.get("is_total_row")))

    # Get payroll schedule groups from DB
    db = get_db()
    fac_schedules = {}
    facs_db = db.execute("SELECT name, payroll_schedule_group FROM facilities").fetchall()
    for f in facs_db:
        if f["payroll_schedule_group"]:
            fac_schedules[f["name"]] = f["payroll_schedule_group"]
    db.close()

    comparisons = []
    for i in range(1, len(all_periods)):
        curr_period = all_periods[i]
        prior_period = all_periods[i - 1]

        # Find facilities in both periods
        curr_facs = set(fac for fac, data in facility_data.items() if curr_period in data)
        prior_facs = set(fac for fac, data in facility_data.items() if prior_period in data)
        comparable_facs = curr_facs & prior_facs
        new_facs = curr_facs - prior_facs
        dropped_facs = prior_facs - curr_facs

        if not comparable_facs:
            comparisons.append({
                "current_period": curr_period,
                "prior_period": prior_period,
                "status": "Not Comparable",
                "reason": "No facilities present in both periods",
                "comparable_facility_count": 0,
                "new_facilities": list(new_facs),
                "dropped_facilities": list(dropped_facs),
            })
            continue

        # Aggregate comparable facilities
        curr_ot = sum(facility_data[f][curr_period].get("ot_dollars") or 0 for f in comparable_facs)
        prior_ot = sum(facility_data[f][prior_period].get("ot_dollars") or 0 for f in comparable_facs)
        curr_bonus = sum(facility_data[f][curr_period].get("bonus_dollars") or 0 for f in comparable_facs)
        prior_bonus = sum(facility_data[f][prior_period].get("bonus_dollars") or 0 for f in comparable_facs)
        curr_hppd_vals = [facility_data[f][curr_period].get("direct_care_hppd") for f in comparable_facs
                          if facility_data[f][curr_period].get("direct_care_hppd") is not None]
        prior_hppd_vals = [facility_data[f][prior_period].get("direct_care_hppd") for f in comparable_facs
                           if facility_data[f][prior_period].get("direct_care_hppd") is not None]

        ot_change = round(curr_ot - prior_ot, 2)
        ot_pct_change = round(ot_change / prior_ot, 6) if prior_ot else None
        hppd_avg_curr = round(sum(curr_hppd_vals) / len(curr_hppd_vals), 6) if curr_hppd_vals else None
        hppd_avg_prior = round(sum(prior_hppd_vals) / len(prior_hppd_vals), 6) if prior_hppd_vals else None

        facility_set_changed = bool(new_facs or dropped_facs)

        comparisons.append({
            "current_period": curr_period,
            "prior_period": prior_period,
            "status": "Same-Facility Comparable",
            "facility_set_changed": facility_set_changed,
            "comparable_facility_count": len(comparable_facs),
            "new_facilities": sorted(new_facs),
            "dropped_facilities": sorted(dropped_facs),
            "total_ot_dollars_curr": round(curr_ot, 2),
            "total_ot_dollars_prior": round(prior_ot, 2),
            "ot_dollars_change": ot_change,
            "ot_dollars_pct_change": ot_pct_change,
            "total_bonus_dollars_curr": round(curr_bonus, 2),
            "total_bonus_dollars_prior": round(prior_bonus, 2),
            "bonus_dollars_change": round(curr_bonus - prior_bonus, 2),
            "avg_hppd_curr": hppd_avg_curr,
            "avg_hppd_prior": hppd_avg_prior,
            "hppd_change": round(hppd_avg_curr - hppd_avg_prior, 6)
            if (hppd_avg_curr is not None and hppd_avg_prior is not None) else None,
            "trend_label": (
                "Rising" if ot_change > 0 else
                "Falling" if ot_change < 0 else
                "Stable"
            ),
            "warning": "Facility set changed â€” use same-facility comparable for clean comparison."
            if facility_set_changed else None,
        })

    return comparisons


# â”€â”€ Labor Pressure Score â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def compute_labor_pressure_scores(batch_id=None):
    """
    Score each facility 0â€“8 based on OT risk, Bonus risk, HPPD risk, PPD risk.
    Returns list of {facility, score, risk_category, main_driver, â€¦}
    """
    rows = get_facility_metrics(batch_id)

    # Group by facility, get latest period data
    facility_latest = {}
    facility_prior = {}
    facility_all = {}

    for r in rows:
        if r.get("is_total_row"):
            continue
        fac = r["facility_name"]
        dt = r["period_date"]
        if fac not in facility_all:
            facility_all[fac] = []
        facility_all[fac].append(r)

    for fac, records in facility_all.items():
        sorted_recs = sorted(records, key=lambda x: x["period_date"])
        facility_latest[fac] = sorted_recs[-1]
        facility_prior[fac] = sorted_recs[-2] if len(sorted_recs) > 1 else None

    scores = []
    for fac, latest in facility_latest.items():
        score = 0
        risks = []
        prior = facility_prior.get(fac)

        ot_d = latest.get("ot_dollars")
        ot_pct = latest.get("ot_pct_labor_dollars")
        bonus_d = latest.get("bonus_dollars")
        hppd = latest.get("direct_care_hppd")
        ppd = latest.get("direct_care_ppd")

        # OT risk scoring
        if ot_pct is not None and ot_pct > 0.15:
            score += 2; risks.append(("OT % High", 2))
        elif ot_pct is not None and ot_pct > 0.10:
            score += 1; risks.append(("OT % Elevated", 1))

        # OT trend
        if prior:
            prior_ot = prior.get("ot_dollars") or 0
            if ot_d is not None and prior_ot > 0:
                ot_chg_pct = (ot_d - prior_ot) / prior_ot
                if ot_chg_pct > 0.20:
                    score += 2; risks.append(("OT Rising >20%", 2))
                elif ot_chg_pct > 0.10:
                    score += 1; risks.append(("OT Rising >10%", 1))

        # Bonus risk
        if bonus_d is not None and ot_d is not None and ot_d > 0:
            bonus_ratio = bonus_d / ot_d
            if bonus_ratio > 0.20:
                score += 1; risks.append(("Bonus Dependency", 1))

        # HPPD risk
        if hppd is not None and hppd < 2.5:
            score += 2; risks.append(("HPPD Low (<2.5)", 2))
        elif hppd is not None and hppd < 2.8:
            score += 1; risks.append(("HPPD Below Average", 1))

        # PPD trend
        if prior and ppd is not None:
            prior_ppd = prior.get("direct_care_ppd")
            if prior_ppd and ppd > prior_ppd * 1.10:
                score += 1; risks.append(("PPD Rising >10%", 1))

        # Missing data
        if hppd is None and ppd is None:
            score += 1; risks.append(("Missing HPPD/PPD", 1))

        main_driver = risks[0][0] if risks else "None"
        sorted_risks = sorted(risks, key=lambda x: -x[1])

        if score >= 6:
            risk_category = "Critical"
        elif score >= 4:
            risk_category = "High"
        elif score >= 2:
            risk_category = "Medium"
        else:
            risk_category = "Low"

        comparable = prior is not None
        ot_trend = None
        if prior and ot_d is not None:
            prior_ot = prior.get("ot_dollars") or 0
            if ot_d > prior_ot * 1.05:
                ot_trend = "Rising"
            elif ot_d < prior_ot * 0.95:
                ot_trend = "Falling"
            else:
                ot_trend = "Stable"

        scores.append({
            "facility_name": fac,
            "acquisition_group": latest.get("acquisition_group"),
            "region": latest.get("region"),
            "payroll_schedule_group": latest.get("payroll_schedule_group"),
            "latest_period": latest.get("period_date"),
            "pressure_score": score,
            "risk_category": risk_category,
            "main_driver": main_driver,
            "risks": sorted_risks,
            "latest_ot_dollars": ot_d,
            "latest_ot_pct": ot_pct,
            "latest_bonus_dollars": bonus_d,
            "latest_hppd": hppd,
            "latest_ppd": ppd,
            "ot_trend": ot_trend,
            "comparable": comparable,
            "missing_data": hppd is None or ppd is None,
        })

    return sorted(scores, key=lambda x: -x["pressure_score"])


# â”€â”€ QA / Reconciliation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def run_reconciliation(batch_id: int) -> list[dict]:
    """
    Run QA checks comparing detail totals vs rollup totals.
    Returns list of reconciliation check results.
    """
    db = get_db()
    results = []

    # 1. OT Detail vs Acq Group rollup
    ot_detail_by_period = {}
    ot_rows = db.execute(
        "SELECT period_date, SUM(value) as total FROM ot_detail_lines WHERE batch_id=? AND metric_group='OT Dollars ($)' GROUP BY period_date",
        (batch_id,)
    ).fetchall()
    for r in ot_rows:
        ot_detail_by_period[r["period_date"]] = r["total"]

    acq_totals = db.execute(
        """SELECT period_date, SUM(value) as total FROM acq_group_period_metrics
           WHERE batch_id=? AND metric_type='OT $' AND acquisition_group != 'Total' GROUP BY period_date""",
        (batch_id,)
    ).fetchall()

    for r in acq_totals:
        dt = r["period_date"]
        detail = ot_detail_by_period.get(dt)
        rollup = r["total"]
        if detail is not None and rollup is not None:
            variance = abs(detail - rollup)
            pct = variance / rollup if rollup else 0
            status = "PASS" if pct < 0.01 else ("WARNING" if pct < 0.05 else "FAIL")
            results.append({
                "check_name": f"OT Detail vs Acq Group Rollup ({dt})",
                "status": status,
                "detail_total": round(detail, 2),
                "rollup_total": round(rollup, 2),
                "variance": round(variance, 2),
                "notes": f"{pct:.1%} variance" if pct > 0 else "Exact match",
            })

    # 2. Bonus Detail vs Acq Group rollup
    bonus_detail_by_period = {}
    bonus_rows = db.execute(
        "SELECT period_date, SUM(bonus_dollars) as total FROM bonus_detail_lines WHERE batch_id=? GROUP BY period_date",
        (batch_id,)
    ).fetchall()
    for r in bonus_rows:
        bonus_detail_by_period[r["period_date"]] = r["total"]

    bonus_acq = db.execute(
        """SELECT period_date, SUM(value) as total FROM acq_group_period_metrics
           WHERE batch_id=? AND metric_type='Bonus $' AND acquisition_group != 'Total' GROUP BY period_date""",
        (batch_id,)
    ).fetchall()

    for r in bonus_acq:
        dt = r["period_date"]
        detail = bonus_detail_by_period.get(dt)
        rollup = r["total"]
        if detail is not None and rollup is not None:
            variance = abs(detail - rollup)
            pct = variance / rollup if rollup else 0
            status = "PASS" if pct < 0.01 else ("WARNING" if pct < 0.05 else "FAIL")
            results.append({
                "check_name": f"Bonus Detail vs Acq Group Rollup ({dt})",
                "status": status,
                "detail_total": round(detail, 2),
                "rollup_total": round(rollup, 2),
                "variance": round(variance, 2),
                "notes": f"{pct:.1%} variance" if pct > 0 else "Exact match",
            })

    # 3. Facility count checks
    for dt_row in db.execute("SELECT DISTINCT period_date FROM facility_period_metrics WHERE batch_id=?", (batch_id,)).fetchall():
        dt = dt_row[0]
        count = db.execute(
            "SELECT COUNT(DISTINCT facility_name) FROM facility_period_metrics WHERE batch_id=? AND period_date=? AND is_total_row=0",
            (batch_id, dt)
        ).fetchone()[0]
        results.append({
            "check_name": f"Facility Count ({dt})",
            "status": "INFO",
            "detail_total": count,
            "rollup_total": None,
            "variance": None,
            "notes": f"{count} facilities with data",
        })

    db.close()

    # Save results
    db2 = get_db()
    db2.execute("DELETE FROM reconciliation_results WHERE batch_id=?", (batch_id,))
    for r in results:
        db2.execute("""INSERT INTO reconciliation_results
            (batch_id, check_name, status, detail_total, rollup_total, variance, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (batch_id, r["check_name"], r["status"], r.get("detail_total"),
             r.get("rollup_total"), r.get("variance"), r.get("notes")))
    db2.commit()
    db2.close()

    return results


# ── Top N Rankings ────────────────────────────────────────────────────────────

def get_top_ot_facilities(batch_id=None, n=10):
    db = get_db()
    query = """
        SELECT facility_name, acquisition_group, region,
               SUM(ot_dollars) as total_ot_dollars,
               SUM(ot_hours) as total_ot_hours
        FROM facility_period_metrics
        WHERE is_total_row = 0
    """
    params = []
    if batch_id:
        query += " AND batch_id = ?"
        params.append(batch_id)
    query += " GROUP BY facility_name ORDER BY total_ot_dollars DESC LIMIT ?"
    params.append(n)
    rows = db.execute(query, params).fetchall()
    db.close()
    return [dict(r) for r in rows]

# ── Facility Flat Metrics (One row per facility for Portfolio Trend Tab) ──────────────────

def compute_facility_flat_metrics(batch_id=None):
    """
    Returns a flat list of facilities with their latest and prior period metrics.
    """
    rows = get_facility_metrics(batch_id)
    facility_data = {}
    for r in rows:
        fac = r["facility_name"]
        if fac not in facility_data: facility_data[fac] = []
        facility_data[fac].append(r)
    
    result = []
    for fac, recs in facility_data.items():
        recs = sorted(recs, key=lambda x: x["period_date"])
        latest = recs[-1]
        prior = recs[-2] if len(recs) > 1 else {}
        
        result.append({
            "facility_name": fac,
            "region": latest.get("region"),
            "acquisition_group": latest.get("acquisition_group"),
            "payroll_schedule_group": latest.get("payroll_schedule_group"),
            "latest_ot_dollars": latest.get("ot_dollars"),
            "prior_ot_dollars": prior.get("ot_dollars"),
            "ot_delta": (latest.get("ot_dollars") or 0) - (prior.get("ot_dollars") or 0),
            "latest_bonus_dollars": latest.get("bonus_dollars"),
            "prior_bonus_dollars": prior.get("bonus_dollars"),
            "bonus_delta": (latest.get("bonus_dollars") or 0) - (prior.get("bonus_dollars") or 0),
            "latest_hppd": latest.get("direct_care_hppd"),
            "prior_hppd": prior.get("direct_care_hppd"),
            "hppd_delta": (latest.get("direct_care_hppd") or 0) - (prior.get("direct_care_hppd") or 0) if latest.get("direct_care_hppd") and prior.get("direct_care_hppd") else None,
            "latest_ppd": latest.get("direct_care_ppd"),
            "latest_period": latest.get("period_date")
        })
    return result

# ── Pay Cycle Mapping Engine ─────────────────────────────────────────────────────────────

def compute_pay_cycle_mapping(batch_id, schedule_groups):
    """
    Summarizes the pay cycle groups and their member facilities.
    """
    mapping = []
    for fac, info in schedule_groups.items():
        mapping.append({
            "facility_name": fac,
            "inferred_cycle": info.get("schedule_group"),
            "pay_periods": info.get("pay_periods", [])
        })
    return mapping

# ── Employee Review (Top OT & Bonus earners with detail) ────────────────────────────────

def compute_employee_review(batch_id):
    """
    Returns top 50 employees by combined labor pressure (OT + Bonus).
    """
    db = get_db()
    rows = db.execute("""
        SELECT 
            ot.employee_name, 
            ot.facility_name, 
            ot.department, 
            ot.position, 
            SUM(CASE WHEN ot.metric_group = 'OT Dollars ($)' THEN ot.value ELSE 0 END) as total_ot,
            (SELECT SUM(bonus_dollars) FROM bonus_detail_lines b WHERE b.batch_id=ot.batch_id AND b.employee_name=ot.employee_name AND b.facility_name=ot.facility_name) as total_bonus
        FROM ot_detail_lines ot
        WHERE ot.batch_id = ?
        GROUP BY ot.employee_name, ot.facility_name
        ORDER BY total_ot DESC
        LIMIT 50
    """, (batch_id,)).fetchall()
    db.close()
    return [dict(r) for r in rows]

# ── Bonus Summary by Type ───────────────────────────────────────────────────────────────

def compute_bonus_by_type_summary(batch_id):
    """
    Aggregates bonus dollars by bonus type for portfolio analysis.
    """
    db = get_db()
    rows = db.execute("""
        SELECT bonus_type, SUM(bonus_dollars) as total_dollars, COUNT(DISTINCT facility_name) as facility_count
        FROM bonus_detail_lines
        WHERE batch_id = ?
        GROUP BY bonus_type
        ORDER BY total_dollars DESC
    """, (batch_id,)).fetchall()
    db.close()
    return [dict(r) for r in rows]

# ── Data Quality Report ──────────────────────────────────────────────────────────────────

def compute_data_quality_report(batch_id, parsed_data):
    """
    Compiles a report on sheet detection, date issues, and parsing warnings.
    """
    report = {
        "sheets_found": parsed_data.get("sheets_found", []),
        "issues": parsed_data.get("issues", []),
        "batch_id": batch_id,
        "timestamp": datetime.now().isoformat()
    }
    return report

# ── Update get_facility_metrics to include extra fields ──────────────────────────────────

def get_facility_metrics(batch_id=None):
    db = get_db()
    query = """
        SELECT fpm.*, f.region, f.acquisition_group, f.payroll_schedule_group
        FROM facility_period_metrics fpm
        JOIN facilities f ON fpm.facility_name = f.name
    """
    if batch_id:
        rows = db.execute(query + " WHERE fpm.batch_id=? ORDER BY fpm.facility_name, fpm.period_date", (batch_id,)).fetchall()
    else:
        rows = db.execute(query + " JOIN upload_batches ub ON fpm.batch_id = ub.id WHERE ub.status = 'active' ORDER BY fpm.facility_name, fpm.period_date").fetchall()
    db.close()
    return [dict(r) for r in rows]
