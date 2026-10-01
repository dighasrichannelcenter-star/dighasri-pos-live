import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime
from supabase import create_client, Client

# Streamlit Page Config
st.set_page_config(page_title="Dighasri Hospital POS", page_icon="🏥", layout="wide")

# Supabase Configurations
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "https://your-supabase-url.supabase.co")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "your-supabase-anon-key")

@st.cache_resource
def init_supabase():
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        st.error(f"Supabase connection error: {e}")
        return None

supabase = init_supabase()

# SQLite Database Connection (Local Storage)
DB_FILE = "dighasri_hospital.db"

def get_db_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Transactions Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_no TEXT UNIQUE,
            bill_type TEXT,
            doctor_name TEXT,
            bill_details TEXT,
            sub_total REAL,
            discount REAL,
            gross_profit REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            synced INTEGER DEFAULT 0
        )
    ''')
    
    # Users Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT
        )
    ''')
    
    # Default Admin User
    cursor.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES ('admin', 'admin123', 'Admin')")
    
    conn.commit()
    conn.close()

init_db()

# Sync Engine - Prevents Duplicates safely
def sync_data_to_supabase():
    if not supabase:
        return False, "Supabase connection unavailable."
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Select unsynced records
    cursor.execute("SELECT * FROM transactions WHERE synced = 0")
    unsynced_rows = cursor.fetchall()
    
    if not unsynced_rows:
        conn.close()
        return True, "සියලුම දත්ත දැනටමත් Cloud එක සමඟ Sync වී ඇත."
    
    success_count = 0
    for row in unsynced_rows:
        data = {
            "bill_no": row["bill_no"],
            "bill_type": row["bill_type"],
            "doctor_name": row["doctor_name"],
            "bill_details": row["bill_details"],
            "sub_total": row["sub_total"],
            "discount": row["discount"],
            "gross_profit": row["gross_profit"],
            "created_at": row["created_at"]
        }
        
        try:
            # Use upsert based on 'bill_no' to strictly avoid duplicate records
            response = supabase.table("transactions").upsert(data, on_conflict="bill_no").execute()
            if response.data:
                cursor.execute("UPDATE transactions SET synced = 1 WHERE id = ?", (row["id"],))
                success_count += 1
        except Exception as e:
            st.warning(f"Error syncing bill {row['bill_no']}: {e}")
            
    conn.commit()
    conn.close()
    return True, f"{success_count} සජීවී ගනුදෙනු සාර්ථකව Sync විය!"

# Authentication Logic
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🏥 Dighasri Hospital POS - User Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password)).fetchone()
        conn.close()
        if user:
            st.session_state.logged_in = True
            st.session_state.username = user["username"]
            st.session_state.role = user["role"]
            st.rerun()
        else:
            st.error("Invalid Username or Password")
    
    st.info("""
    **Default Passwords:**
    - Admin: `admin` / `admin123`
    """)
else:
    # Sidebar Navigation
    st.sidebar.title(f"👤 User: {st.session_state.username}")
    st.sidebar.caption(f"Role: {st.session_state.role}")
    
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()
        
    menu = st.sidebar.radio("Navigation", ["Financial Reports (මුදල් වාර්තා)", "Expiry & Re-Order Tracking", "Manual Sync Data"])
    
    # Financial Reports Section
    if menu == "Financial Reports (මුදල් වාර්තා)":
        st.header("📊 Date Filter Options (දිනයන් අනුව වාර්තා තෝරන්න)")
        
        # Load Data safely from Supabase (Cloud) or SQLite (Local)
        try:
            if supabase:
                res = supabase.table("transactions").select("*").execute()
                df = pd.DataFrame(res.data)
            else:
                conn = get_db_connection()
                df = pd.read_sql_query("SELECT * FROM transactions", conn)
                conn.close()
        except Exception:
            conn = get_db_connection()
            df = pd.read_sql_query("SELECT * FROM transactions", conn)
            conn.close()

        if not df.empty:
            # Ensure unique display by bill_no
            df = df.drop_duplicates(subset=["bill_no"], keep="last")
            
            st.subheader("📋 Detailed Section-Wise Breakdown (අද දින - Today)")
            st.dataframe(df, use_container_width=True)
            
            # Summary Totals
            total_income = df["sub_total"].sum() - df["discount"].sum()
            st.metric("Total Net Income (ශුද්ධ ආදායම)", f"LKR {total_income:,.2f}")
        else:
            st.warning("දැනට කිසිදු ගනුදෙනුවක් සටහන් වී නොමැත.")

    elif menu == "Manual Sync Data":
        st.header("🔄 Live Data Synchronization")
        if st.button("Sync Now to Cloud"):
            status, msg = sync_data_to_supabase()
            if status:
                st.success(msg)
            else:
                st.error(msg)
