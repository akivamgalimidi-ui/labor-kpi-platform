import os
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://wttunwewaxaltxhgvirt.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_secret_dnn04XkuyUk_upLGe8rMaQ_uipmoZ_5]")

def get_supabase() -> Client:
    # Use the service role key to bypass RLS for backend operations
    return create_client(SUPABASE_URL, SUPABASE_KEY)
