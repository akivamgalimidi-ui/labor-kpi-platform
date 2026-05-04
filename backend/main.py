from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from supabase_client import get_supabase
import pandas as pd
import io
import uuid
import json

app = FastAPI(title="Nursing Labor KPI API - Supabase Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Labor KPI API running on Supabase"}

@app.post("/api/uploads")
async def upload_payroll_file(file: UploadFile = File(...)):
    """
    Accepts the Excel file, uploads to Supabase storage, and triggers parsing.
    """
    try:
        supabase = get_supabase()
        
        # Read file
        contents = await file.read()
        
        # 1. Store in Supabase Storage
        file_path = f"uploads/{uuid.uuid4()}_{file.filename}"
        
        # Note: You need a bucket named 'payroll_files' created in Supabase
        # supabase.storage.from_("payroll_files").upload(file_path, contents)
        
        # 2. Create Upload Batch Record
        batch_res = supabase.table("upload_batches").insert({
            "filename": file.filename,
            "status": "processing"
        }).execute()
        
        batch_id = batch_res.data[0]['id'] if batch_res.data else None
        
        # Here we would normally enqueue a background worker to parse the file using Pandas
        # and insert into the Supabase tables (facilities, ot_detail_lines, etc.)
        
        return {"message": "File uploaded successfully", "batch_id": batch_id, "file_path": file_path}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/dashboard/executive")
def get_executive_dashboard():
    """
    Queries Supabase for portfolio level KPIs.
    """
    supabase = get_supabase()
    
    # Query the facility_period_metrics table natively via PostgREST
    res = supabase.table("facility_period_metrics").select(
        "pay_period_id, ot_dollars, bonus_dollars, direct_care_hppd"
    ).execute()
    
    if not res.data:
        return {"data": []}
        
    return {"data": res.data}


@app.get("/api/filters/{filter_type}")
def get_global_filters(filter_type: str):
    """
    Returns unique values from the database for the global slicers.
    """
    supabase = get_supabase()
    
    if filter_type == "facilities":
        res = supabase.table("facilities").select("id, facility_name").execute()
    elif filter_type == "regions":
        res = supabase.table("regions").select("id, region_name").execute()
    elif filter_type == "acquisition-groups":
        res = supabase.table("acquisition_groups").select("id, acquisition_group_name").execute()
    elif filter_type == "pay-periods":
        res = supabase.table("pay_periods").select("id, pay_period_date").execute()
    else:
        raise HTTPException(status_code=400, detail="Unknown filter type")
        
    return {"data": res.data}

@app.get("/api/drilldown/facility/{facility_id}")
def get_facility_drilldown(facility_id: str):
    """
    Drilldown service fetching granular employee data for a facility.
    """
    supabase = get_supabase()
    
    ot_res = supabase.table("ot_detail_lines").select(
        "employee_name, department, position, ot_dollars, ot_hours, period_date:pay_period_id(pay_period_date)"
    ).eq("facility_id", facility_id).execute()
    
    bonus_res = supabase.table("bonus_detail_lines").select(
        "employee_name, bonus_type, department, position, bonus_dollars"
    ).eq("facility_id", facility_id).execute()
    
    return {
        "ot_detail": ot_res.data,
        "bonus_detail": bonus_res.data
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
