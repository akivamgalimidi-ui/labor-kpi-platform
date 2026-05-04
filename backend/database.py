import os
import json
from datetime import datetime
from supabase_client import get_supabase

# Supabase API abstraction for the Labor KPI Engine
# Replaces the legacy SQLite implementation.

def init_db():
    # Database initialization is handled by supabase/migrations/20260504_initial_schema.sql
    # No local SQLite file to create.
    pass

def get_db():
    raise NotImplementedError("SQLite has been removed. Use get_supabase() instead.")

def insert_upload_batch(filename: str) -> str:
    supabase = get_supabase()
    # Note: this requires an organization_id if the schema mandates it.
    # For now, we assume a default org or make it optional in schema.
    data, count = supabase.table('upload_batches').insert({
        'filename': filename,
        'status': 'processing'
    }).execute()
    
    if data and len(data[1]) > 0:
        return data[1][0]['id']
    return None

def update_upload_batch_stats(batch_id: str, parsed_facilities: int, periods: int):
    supabase = get_supabase()
    supabase.table('upload_batches').update({
        'status': 'active',
        'rows_parsed': parsed_facilities,
        'detected_pay_periods': periods
    }).eq('id', batch_id).execute()

def store_parsed_data(batch_id: str, parsed_data: dict):
    """
    Stores the extracted dictionary into Supabase tables via REST.
    """
    supabase = get_supabase()
    
    # Example logic to populate facilities
    for fac_name in parsed_data.get('facilities', []):
        try:
            supabase.table('facilities').insert({
                'facility_name': fac_name, 
                'normalized_facility_name': fac_name.lower()
            }).execute()
        except Exception as e:
            print(f"Facility insert error: {e}")
            
    # For a full implementation, you would:
    # 1. Fetch Facility UUIDs
    # 2. Fetch Region UUIDs
    # 3. Bulk insert to `ot_detail_lines`, `bonus_detail_lines` via supabase.table().insert(list_of_dicts)
    
    print(f"Supabase sync stubbed for batch {batch_id}. To fully implement data hydration, map UUID foreign keys first.")
