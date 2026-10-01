import sqlite3
import json
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client

# ---------------------------------------------------------
# SUPABASE CLOUD CONNECTION
# ---------------------------------------------------------
SUPABASE_URL = "https://rpgidxxpobulzrqzwvnc.supabase.co"
SUPABASE_KEY = "sb_publishable_NW29EDWrexNancffxu3xow_E384sMq0"

try:
    if "SUPABASE_URL" in st.secrets:
        SUPABASE_URL = st.secrets["SUPABASE_URL"]
    if "SUPABASE_KEY" in st.secrets:
        SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except Exception:
    pass

@st.cache_resource
def init_supabase():
    try:
        if SUPABASE_URL and SUPABASE_KEY:
            return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception:
        return None
    return None

supabase = init_supabase()

def sync_to_cloud(data_dict):
    if supabase:
        try:
            supabase.table("sales_history").insert(data_dict).execute()
        except Exception:
            pass

# Local Database Connection
conn = sqlite3.connect('dighasri_hospital.db', check_same_thread=False)
c = conn.cursor()

# ---------------------------------------------------------
# DATABASE TABLES CREATION & MIGRATION
# ---------------------------------------------------------
c.execute('''CREATE TABLE IF NOT EXISTS users
             (username TEXT PRIMARY KEY, password TEXT, role TEXT)''')

c.execute('''CREATE TABLE IF NOT EXISTS inventory
             (id INTEGER PRIMARY KEY AUTOINCREMENT, supplier_name TEXT, item_name TEXT, brand_name TEXT, category TEXT,
              dosage TEXT, cost_price REAL, unit_price REAL, profit_margin REAL,
              stock_qty INTEGER, expiry_date TEXT, reorder_level INTEGER, batch_no TEXT, barcode TEXT)''')

c.execute('''CREATE TABLE IF NOT EXISTS lab_tests
             (id INTEGER PRIMARY KEY AUTOINCREMENT, test_name TEXT, patient_fee REAL, lab_cost REAL, center_commission REAL)''')

c.execute('''CREATE TABLE IF NOT EXISTS doctors
             (id INTEGER PRIMARY KEY AUTOINCREMENT, doc_name TEXT, designation TEXT, doc_fee REAL, center_fee REAL, doc_scan_fee REAL, center_scan_fee REAL)''')

c.execute('''CREATE TABLE IF NOT EXISTS opd_procedures
             (id INTEGER PRIMARY KEY AUTOINCREMENT, proc_name TEXT, default_doc_fee REAL, center_fee REAL)''')

c.execute('''CREATE TABLE IF NOT EXISTS preset_prescriptions
             (id INTEGER PRIMARY KEY AUTOINCREMENT, preset_name TEXT, items_json TEXT)''')

c.execute('''CREATE TABLE IF NOT EXISTS sales_history
             (id INTEGER PRIMARY KEY AUTOINCREMENT, prescription_no TEXT, bill_type TEXT, doctor_name TEXT, bill_details TEXT,
              total_amount REAL, doc_fee REAL, lab_cost REAL, center_profit REAL, date TIMESTAMP, cost_price REAL DEFAULT 0.0, discount REAL DEFAULT 0.0, status TEXT DEFAULT 'COMPLETED')''')

def safe_add_column(table_name, column_def):
    try:
        c.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_def}")
    except sqlite3.OperationalError:
        pass

safe_add_column('inventory', "brand_name TEXT DEFAULT ''")
safe_add_column('sales_history', "status TEXT DEFAULT 'COMPLETED'")

# Default users insertion
c.execute("INSERT OR IGNORE INTO users VALUES ('admin', 'admin123', 'Admin')")
c.execute("INSERT OR IGNORE INTO users VALUES ('supervisor', 'super123', 'Supervisor')")
c.execute("INSERT OR IGNORE INTO users VALUES ('cashier', 'cashier123', 'Cashier')")

conn.commit()

# Initialize Session States
if 'pos_cart' not in st.session_state:
    st.session_state.pos_cart = []
if 'print_html' not in st.session_state:
    st.session_state.print_html = None
if 'user' not in st.session_state:
    st.session_state.user = None

def show_table(df, **kwargs):
    if not df.empty:
        df_copy = df.copy()
        df_copy.index = range(1, len(df_copy) + 1)
        st.dataframe(df_copy, **kwargs)
    else:
        st.dataframe(df, **kwargs)

# --- INSTANT PRINT SCRIPT ---
def trigger_instant_print(bill_html_content, unique_key):
    full_html = f"""
    <div id="printArea_{unique_key}" style="font-family: 'Courier New', Courier, monospace; font-size: 7.5pt; font-weight: bold; width: 140px; padding: 0px; margin: 0 auto; text-align: center; color: #000; line-height: 1.2; word-wrap: break-word;">
        {bill_html_content}
    </div>
    <script>
    setTimeout(function() {{
        var printContents = document.getElementById('printArea_{unique_key}').innerHTML;
        var frame = document.createElement('iframe');
        frame.name = "printFrame_{unique_key}";
        frame.style.position = "absolute";
        frame.style.top = "-10000px";
        document.body.appendChild(frame);
        var frameDoc = frame.contentWindow ? frame.contentWindow : frame.contentDocument.document ? frame.contentDocument.document : frame.contentDocument;
        frameDoc.document.open();
        frameDoc.document.write('<html><head><title>Print Receipt</title>');
        frameDoc.document.write('<style>@page {{ margin: 0px; size: 58mm auto; }} body {{ font-family: "Courier New", Courier, monospace; font-size: 7.5pt; font-weight: bold; width: 140px; margin: 0 auto; padding: 0; text-align: center; color: #000; word-wrap: break-word; }} hr {{ border: none; border-top: 1px dashed #000; margin: 3px 0; }}</style>');
        frameDoc.document.write('</head><body>');
        frameDoc.document.write(printContents);
        frameDoc.document.write('</body></html>');
        frameDoc.document.close();
        setTimeout(function() {{
            window.frames["printFrame_{unique_key}"].focus();
            window.frames["printFrame_{unique_key}"].print();
        }}, 500);
    }}, 200);
    </script>
    """
    components.html(full_html, height=100)

# ---------------------------------------------------------
# APPLICATION SETUP
# ---------------------------------------------------------
st.set_page_config(page_title="Dighasri Channel Center POS", page_icon="🏥", layout="wide")

if st.session_state.print_html:
    trigger_instant_print(st.session_state.print_html, "bill_print")
    st.session_state.print_html = None

# ---------------------------------------------------------
# LOGIN SYSTEM
# ---------------------------------------------------------
if st.session_state.user is None:
    st.title("🔐 Dighasri Hospital POS - User Login")
    
    col_l1, col_l2, col_l3 = st.columns([1, 1.5, 1])
    with col_l2:
        st.subheader("Login to Access System")
        u_name = st.text_input("Username (පරිශීලක නාමය):")
        u_pass = st.text_input("Password (මුරපදය):", type="password")
        
        if st.button("🔑 Login", type="primary", use_container_width=True):
            c.execute("SELECT username, role FROM users WHERE username=? AND password=?", (u_name, u_pass))
            res = c.fetchone()
            if res:
                st.session_state.user = {'username': res[0], 'role': res[1]}
                st.success(f"සාර්ථකව ප්‍රවේශ විය! (Role: {res[1]})")
                st.rerun()
            else:
                st.error("කරුණාකර නිවැරදි Username සහ Password ඇතුළත් කරන්න.")
        
        st.info("""
        **Default Passwords:**
        * **Admin:** `admin` / `admin123`
        * **Supervisor:** `supervisor` / `super123`
        * **Cashier:** `cashier` / `cashier123`
        """)
    st.stop()

# ---------------------------------------------------------
# MAIN INTERFACE
# ---------------------------------------------------------
st.sidebar.title(f"👤 User: {st.session_state.user['username']}")
st.sidebar.markdown(f"**Role:** `{st.session_state.user['role']}`")
if st.sidebar.button("🚪 Logout", use_container_width=True):
    st.session_state.user = None
    st.session_state.pos_cart = []
    st.rerun()

st.title("🏥 Dighasri Channel Center POS System")

user_role = st.session_state.user['role']

if user_role == "Admin":
    available_tabs = ["🛒 POS Billing", "📦 Master Settings & Inventory", "📊 Reports & Accounts", "⚙️️ User Management"]
elif user_role == "Supervisor":
    available_tabs = ["🛒 POS Billing", "📦 Master Settings & Inventory", "📊 Reports & Accounts"]
else:
    available_tabs = ["🛒 POS Billing", "📊 Reports & Accounts"]

tabs = st.tabs(available_tabs)

# ---------------------------------------------------------
# TAB 1: POS BILLING
# ---------------------------------------------------------
with tabs[0]:
    col_left, col_right = st.columns([1.2, 1.8])
    
    with col_left:
        st.subheader("🛒 Current Order / Cart")
        ref_no = st.text_input("Patient / Ref No:", value="REF-1001")
        
        if st.session_state.pos_cart:
            cart_df = pd.DataFrame(st.session_state.pos_cart)
            show_table(cart_df[['display_name', 'qty', 'unit_price', 'total_price']], use_container_width=True)
            
            subtotal = cart_df['total_price'].sum()
            st.metric("Total Amount", f"LKR {subtotal:.2f}")
            
            st.markdown("---")
            col_p1, col_p2 = st.columns(2)
            with col_p1:
                paid_amt = st.number_input("Paid Amount (LKR):", min_value=0.0, value=float(subtotal), step=50.0)
            with col_p2:
                balance_amt = max(0.0, paid_amt - subtotal)
                st.metric("Balance", f"LKR {balance_amt:.2f}")
                
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                if st.button("🗑️ Clear Cart", use_container_width=True):
                    st.session_state.pos_cart = []
                    st.rerun()
            
            with col_b2:
                if st.button("💾 Checkout & Print Bill", type="primary", use_container_width=True):
                    bill_items_html = ""
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                    
                    for item in st.session_state.pos_cart:
                        print_title = "Laboratory Charges" if item['category'] == "Laboratory" else item['display_name']
                        bill_items_html += f"<div>{print_title}<br>{item['qty']} x {item['unit_price']:.2f} = LKR {item['total_price']:.2f}</div>"
                        
                        dt_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        if item['category'] == 'Pharmacy':
                            c.execute("UPDATE inventory SET stock_qty = stock_qty - ? WHERE id = ?", (item['qty'], item['id']))
                            cost_tot = item['qty'] * item.get('cost_price', 0.0)
                            c.execute("INSERT INTO sales_history (prescription_no, bill_type, doctor_name, bill_details, total_amount, doc_fee, lab_cost, center_profit, cost_price, date, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                      (ref_no, 'Pharmacy', '-', f"{item['id']}|{item['display_name']} x {item['qty']}", item['total_price'], 0.0, 0.0, item['total_price'] - cost_tot, cost_tot, dt_now, 'COMPLETED'))
                            sync_to_cloud({
                                'prescription_no': ref_no, 'bill_type': 'Pharmacy', 'doctor_name': '-',
                                'bill_details': f"{item['id']}|{item['display_name']} x {item['qty']}",
                                'total_amount': item['total_price'], 'doc_fee': 0.0, 'lab_cost': 0.0,
                                'center_profit': item['total_price'] - cost_tot, 'cost_price': cost_tot, 'date': dt_now, 'status': 'COMPLETED'
                            })
                        
                        elif item['category'] == 'Laboratory':
                            c.execute("INSERT INTO sales_history (prescription_no, bill_type, doctor_name, bill_details, total_amount, doc_fee, lab_cost, center_profit, date, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                      (ref_no, 'Laboratory', '-', item['display_name'], item['total_price'], 0.0, item['lab_cost'], item['center_comm'], dt_now, 'COMPLETED'))
                            sync_to_cloud({
                                'prescription_no': ref_no, 'bill_type': 'Laboratory', 'doctor_name': '-',
                                'bill_details': item['display_name'], 'total_amount': item['total_price'],
                                'doc_fee': 0.0, 'lab_cost': item['lab_cost'], 'center_profit': item['center_comm'], 'date': dt_now, 'status': 'COMPLETED'
                            })
                        
                        elif item['category'] in ['OPD', 'Channeling', 'Scanning']:
                            c.execute("INSERT INTO sales_history (prescription_no, bill_type, doctor_name, bill_details, total_amount, doc_fee, lab_cost, center_profit, date, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                      (ref_no, item['category'], item.get('doctor_name', '-'), item['display_name'], item['total_price'], item.get('doc_fee', 0.0), 0.0, item.get('center_profit', 0.0), dt_now, 'COMPLETED'))
                            sync_to_cloud({
                                'prescription_no': ref_no, 'bill_type': item['category'], 'doctor_name': item.get('doctor_name', '-'),
                                'bill_details': item['display_name'], 'total_amount': item['total_price'],
                                'doc_fee': item.get('doc_fee', 0.0), 'lab_cost': 0.0, 'center_profit': item.get('center_profit', 0.0), 'date': dt_now, 'status': 'COMPLETED'
                            })
                    
                    conn.commit()
                    
                    st.session_state.print_html = f"""
                    <div style="text-align: center;">
                        <b style="font-size: 8pt;">DIGHASRI CHANNEL CENTER</b><br>
                        <span>Official Receipt</span><br>
                        <small style="font-size: 6.5pt;">{now_str}</small>
                    </div>
                    <hr style="border: 1px dashed #000;">
                    <div style="text-align: center;">Ref No : {ref_no}</div>
                    <hr style="border: 1px dashed #000;">
                    <div style="text-align: center;">{bill_items_html}</div>
                    <hr style="border: 1px dashed #000;">
                    <div style="text-align: center;"><b>NET TOTAL : LKR {subtotal:.2f}</b></div>
                    <div style="text-align: center;">Paid Amt : LKR {paid_amt:.2f}</div>
                    <div style="text-align: center;">Balance  : LKR {balance_amt:.2f}</div>
                    <hr style="border: 1px dashed #000;">
                    <div style="text-align: center;"><small style="font-size: 6.5pt;">Thank You Come Again!</small></div>
                    """
                    
                    st.session_state.pos_cart = []
                    st.success("✅ Order Processed & Receipt Sent to Printer!")
                    st.rerun()
        else:
            st.info("Cart එක හිස්ව පවතී.")

    with col_right:
        st.subheader("⚡ Quick Category Select")
        sub_tab1, sub_tab2, sub_tab3, sub_tab4, sub_tab5 = st.tabs(["🧪 Laboratory", "💊 Pharmacy", "🩺 OPD Procedures", "👨‍⚕️ Channeling", "🖥️ Scanning"])
        
        with sub_tab1:
            labs_df = pd.read_sql_query("SELECT * FROM lab_tests", conn)
            if not labs_df.empty:
                col_l1, col_l2 = st.columns([2, 1])
                with col_l1:
                    selected_test = st.selectbox("Select Laboratory Test:", labs_df['test_name'].tolist())
                with col_l2:
                    t_row = labs_df[labs_df['test_name'] == selected_test].iloc[0]
                    st.metric("Fee", f"LKR {t_row['patient_fee']:.2f}")
                
                if st.button("➕ Add Lab Test to Cart", use_container_width=True):
                    st.session_state.pos_cart.append({
                        'category': 'Laboratory',
                        'id': t_row['id'],
                        'display_name': f"Lab: {t_row['test_name']}",
                        'qty': 1,
                        'unit_price': float(t_row['patient_fee']),
                        'total_price': float(t_row['patient_fee']),
                        'lab_cost': float(t_row['lab_cost']),
                        'center_comm': float(t_row['center_commission'])
                    })
                    st.success(f"Added {t_row['test_name']} to Cart!")
                    st.rerun()

        with sub_tab2:
            inv_df = pd.read_sql_query("SELECT * FROM inventory WHERE stock_qty > 0", conn)
            if not inv_df.empty:
                inv_df['display_label'] = inv_df['item_name'] + " (" + inv_df['brand_name'] + ") [" + inv_df['category'] + "]"
                col_p1, col_p2 = st.columns([2, 1])
                with col_p1:
                    selected_med_label = st.selectbox("Select Item:", inv_df['display_label'].tolist())
                    m_row = inv_df[inv_df['display_label'] == selected_med_label].iloc[0]
                with col_p2:
                    med_qty = st.number_input(f"Qty (Stock: {m_row['stock_qty']}):", min_value=1, max_value=int(m_row['stock_qty']), value=1)
                
                if st.button("➕ Add Item to Cart", use_container_width=True):
                    st.session_state.pos_cart.append({
                        'category': 'Pharmacy',
                        'id': m_row['id'],
                        'display_name': f"{m_row['item_name']} ({m_row['brand_name']})",
                        'qty': med_qty,
                        'unit_price': float(m_row['unit_price']),
                        'total_price': float(m_row['unit_price']) * med_qty,
                        'cost_price': float(m_row['cost_price'])
                    })
                    st.success(f"Added {m_row['item_name']} to Cart!")
                    st.rerun()

        with sub_tab3:
            st.markdown("#### OPD Treatments, Procedures & Presets")
            procs_df = pd.read_sql_query("SELECT * FROM opd_procedures", conn)
            presets_df = pd.read_sql_query("SELECT * FROM preset_prescriptions", conn)
            
            opd_mode = st.radio("OPD Type:", ["Procedures / Treatments", "Preset Prescriptions"], horizontal=True)
            
            if opd_mode == "Procedures / Treatments":
                if not procs_df.empty:
                    selected_proc = st.selectbox("Select Procedure / Treatment:", procs_df['proc_name'].tolist())
                    p_row = procs_df[procs_df['proc_name'] == selected_proc].iloc[0]
                    default_d_fee = float(p_row['default_doc_fee'])
                    default_c_fee = float(p_row['center_fee'])
                else:
                    selected_proc = "General OPD Consultation"
                    default_d_fee = 350.0
                    default_c_fee = 150.0

                remove_doc_fee = st.checkbox("🚫 No Doctor Fee", value=False)
                col_of1, col_of2 = st.columns(2)
                with col_of1:
                    opd_doc_fee = 0.0 if remove_doc_fee else st.number_input("Doctor Fee (LKR):", value=default_d_fee, step=50.0)
                with col_of2:
                    opd_center_fee = st.number_input("Center Fee (LKR):", value=default_c_fee, step=50.0)
                    
                tot_opd_fee = opd_doc_fee + opd_center_fee
                st.metric("Total Payable Amount", f"LKR {tot_opd_fee:.2f}")
                    
                if st.button("➕ Add OPD Procedure to Cart", use_container_width=True):
                    st.session_state.pos_cart.append({
                        'category': 'OPD',
                        'display_name': f"OPD: {selected_proc}",
                        'qty': 1,
                        'unit_price': float(tot_opd_fee),
                        'total_price': float(tot_opd_fee),
                        'doctor_name': "OPD Doctor",
                        'doc_fee': float(opd_doc_fee),
                        'center_profit': float(opd_center_fee)
                    })
                    st.success("Added to Cart!")
                    st.rerun()
            else:
                if not presets_df.empty:
                    selected_preset = st.selectbox("Select Preset Prescription:", presets_df['preset_name'].tolist())
                    pr_row = presets_df[presets_df['preset_name'] == selected_preset].iloc[0]
                    st.info(f"Preset Details: {pr_row['items_json']}")
                    preset_price = st.number_input("Preset Total Amount (LKR):", min_value=0.0, value=500.0, step=50.0)
                    
                    if st.button("➕ Add Preset Prescription to Cart", use_container_width=True):
                        st.session_state.pos_cart.append({
                            'category': 'OPD',
                            'display_name': f"OPD Preset: {pr_row['preset_name']}",
                            'qty': 1,
                            'unit_price': float(preset_price),
                            'total_price': float(preset_price),
                            'doctor_name': "OPD Doctor",
                            'doc_fee': 0.0,
                            'center_profit': float(preset_price)
                        })
                        st.success("Preset Added to Cart!")
                        st.rerun()
                else:
                    st.warning("Preset Prescriptions නොමැත. Master Settings මගින් එකතු කරන්න.")

        with sub_tab4:
            docs_df = pd.read_sql_query("SELECT * FROM doctors", conn)
            if not docs_df.empty:
                doc_sel = st.selectbox("Select Channeling Doctor:", docs_df['doc_name'].tolist(), key="chan_doc_select")
                d_row = docs_df[docs_df['doc_name'] == doc_sel].iloc[0]
                tot_chan_fee = float(d_row['doc_fee']) + float(d_row['center_fee'])
                st.metric("Total Channeling Fee", f"LKR {tot_chan_fee:.2f}")
                
                if st.button("➕ Add Channeling to Cart", use_container_width=True):
                    st.session_state.pos_cart.append({
                        'category': 'Channeling',
                        'display_name': f"Channeling - {d_row['doc_name']}",
                        'qty': 1,
                        'unit_price': tot_chan_fee,
                        'total_price': tot_chan_fee,
                        'doctor_name': d_row['doc_name'],
                        'doc_fee': float(d_row['doc_fee']),
                        'center_profit': float(d_row['center_fee'])
                    })
                    st.success("Added Channeling to Cart!")
                    st.rerun()

        with sub_tab5:
            docs_df = pd.read_sql_query("SELECT * FROM doctors", conn)
            if not docs_df.empty:
                scan_doc_sel = st.selectbox("Select Scanning Doctor:", docs_df['doc_name'].tolist(), key="scan_doc_select")
                sd_row = docs_df[docs_df['doc_name'] == scan_doc_sel].iloc[0]
                doc_scan_fee = float(sd_row.get('doc_scan_fee', 0.0))
                center_scan_fee = float(sd_row.get('center_scan_fee', 0.0))
                tot_scan_fee = doc_scan_fee + center_scan_fee
                
                if st.button("➕ Add Scanning to Cart", use_container_width=True):
                    st.session_state.pos_cart.append({
                        'category': 'Scanning',
                        'display_name': f"Scanning - {sd_row['doc_name']}",
                        'qty': 1,
                        'unit_price': tot_scan_fee,
                        'total_price': tot_scan_fee,
                        'doctor_name': sd_row['doc_name'],
                        'doc_fee': doc_scan_fee,
                        'center_profit': center_scan_fee
                    })
                    st.success("Added Scanning to Cart!")
                    st.rerun()

# ---------------------------------------------------------
# TAB 2: MASTER SETTINGS & INVENTORY (CRUD OPERATIONS)
# ---------------------------------------------------------
if "📦 Master Settings & Inventory" in available_tabs:
    tab_index = available_tabs.index("📦 Master Settings & Inventory")
    with tabs[tab_index]:
        st.subheader("📦 Master Settings & CRUD Operations")
        m_tab1, m_tab2, m_tab3, m_tab_preset, m_tab4 = st.tabs(["💊 Pharmacy Inventory", "🧪 Lab Tests", "🩺 OPD Procedures", "📋 OPD Presets", "👨‍⚕️ Doctors"])
        
        # --- 1. PHARMACY INVENTORY CRUD ---
        with m_tab1:
            st.markdown("### 💊 Pharmacy Inventory Management (Medicine & Non-Medicine)")
            p_action = st.radio("Action:", ["View All", "➕ Add New Item", "✏️ Edit Item", "🗑️ Delete Item"], horizontal=True, key="p_action")
            
            if p_action == "View All":
                inv_all = pd.read_sql_query("SELECT * FROM inventory", conn)
                show_table(inv_all, use_container_width=True)
                
            elif p_action == "➕ Add New Item":
                st.markdown("#### Add New Pharmacy Item")
                c1, c2, c3 = st.columns(3)
                with c1:
                    cat = st.selectbox("Category (කාණ්ඩය):", ["Medicine (ඖෂධ)", "Non-Medicine (ඖෂධ නොවන)"])
                    i_name = st.text_input("Item Name (නම):")
                    b_name = st.text_input("Brand Name (වෙළඳ නාමය):")
                    dosage = st.text_input("Dosage / Size (උදා: 500mg, 10ml, Single):")
                with c2:
                    supplier = st.text_input("Supplier Name:")
                    cost_p = st.number_input("Cost Price (LKR):", min_value=0.0, step=10.0)
                    unit_p = st.number_input("Unit Price (LKR):", min_value=0.0, step=10.0)
                    profit_m = unit_p - cost_p
                    st.info(f"Calculated Margin: LKR {profit_m:.2f}")
                with c3:
                    stock_q = st.number_input("Stock Qty:", min_value=0, step=10)
                    reorder_l = st.number_input("Re-order Level:", min_value=0, value=10)
                    exp_d = st.date_input("Expiry Date:", value=datetime.now().date() + timedelta(days=365))
                    batch_n = st.text_input("Batch No:")
                    barcode_n = st.text_input("Barcode:")

                if st.button("💾 Save Item to Inventory", type="primary"):
                    if i_name:
                        c.execute("""INSERT INTO inventory (supplier_name, item_name, brand_name, category, dosage, cost_price, unit_price, profit_margin, stock_qty, expiry_date, reorder_level, batch_no, barcode) 
                                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                                  (supplier, i_name, b_name, cat, dosage, cost_p, unit_p, profit_m, stock_q, str(exp_d), reorder_l, batch_no, barcode_n))
                        conn.commit()
                        st.success(f"✅ '{i_name}' successfully added!")
                        st.rerun()
                    else:
                        st.error("කරුණාකර Item Name ඇතුළත් කරන්න.")

            elif p_action == "✏️ Edit Item":
                inv_df = pd.read_sql_query("SELECT * FROM inventory", conn)
                if not inv_df.empty:
                    selected_id = st.selectbox("Select Item to Edit:", inv_df['id'].astype(str) + " - " + inv_df['item_name'] + " (" + inv_df['brand_name'] + ")")
                    item_id = int(selected_id.split(" - ")[0])
                    row = inv_df[inv_df['id'] == item_id].iloc[0]

                    c1, c2, c3 = st.columns(3)
                    with c1:
                        cat_e = st.selectbox("Category:", ["Medicine (ඖෂධ)", "Non-Medicine (ඖෂධ නොවන)"], index=0 if "Medicine" in str(row['category']) else 1)
                        i_name_e = st.text_input("Item Name:", value=str(row['item_name']))
                        b_name_e = st.text_input("Brand Name:", value=str(row['brand_name']))
                        dosage_e = st.text_input("Dosage / Size:", value=str(row['dosage']))
                    with c2:
                        supplier_e = st.text_input("Supplier Name:", value=str(row['supplier_name']))
                        cost_p_e = st.number_input("Cost Price:", value=float(row['cost_price']), step=10.0)
                        unit_p_e = st.number_input("Unit Price:", value=float(row['unit_price']), step=10.0)
                    with c3:
                        stock_q_e = st.number_input("Stock Qty:", value=int(row['stock_qty']))
                        reorder_l_e = st.number_input("Re-order Level:", value=int(row['reorder_level']))
                        batch_n_e = st.text_input("Batch No:", value=str(row['batch_no']))

                    if st.button("🔄 Update Item", type="primary"):
                        profit_m_e = unit_p_e - cost_p_e
                        c.execute("""UPDATE inventory SET supplier_name=?, item_name=?, brand_name=?, category=?, dosage=?, cost_price=?, unit_price=?, profit_margin=?, stock_qty=?, reorder_level=?, batch_no=? WHERE id=?""",
                                  (supplier_e, i_name_e, b_name_e, cat_e, dosage_e, cost_p_e, unit_p_e, profit_m_e, stock_q_e, reorder_l_e, batch_no, item_id))
                        conn.commit()
                        st.success("✅ Item updated successfully!")
                        st.rerun()

            elif p_action == "🗑️ Delete Item":
                inv_df = pd.read_sql_query("SELECT * FROM inventory", conn)
                if not inv_df.empty:
                    del_id_str = st.selectbox("Select Item to Delete:", inv_df['id'].astype(str) + " - " + inv_df['item_name'])
                    del_id = int(del_id_str.split(" - ")[0])
                    if st.button("🔥 Delete Selected Item", type="primary"):
                        c.execute("DELETE FROM inventory WHERE id=?", (del_id,))
                        conn.commit()
                        st.warning("🗑️ Item deleted successfully!")
                        st.rerun()

        # --- 2. LAB TESTS CRUD ---
        with m_tab2:
            st.markdown("### 🧪 Lab Tests Management")
            l_action = st.radio("Action:", ["View All", "➕ Add Test", "✏️ Edit Test", "🗑 Delete Test"], horizontal=True, key="l_action")
            
            if l_action == "View All":
                show_table(pd.read_sql_query("SELECT * FROM lab_tests", conn), use_container_width=True)

            elif l_action == "➕ Add Test":
                c1, c2, c3 = st.columns(3)
                t_name = c1.text_input("Test Name:")
                p_fee = c2.number_input("Patient Fee (LKR):", min_value=0.0, step=50.0)
                l_cost = c3.number_input("Lab Cost (LKR):", min_value=0.0, step=50.0)
                c_comm = p_fee - l_cost
                st.info(f"Center Commission: LKR {c_comm:.2f}")

                if st.button("💾 Save Lab Test", type="primary"):
                    c.execute("INSERT INTO lab_tests (test_name, patient_fee, lab_cost, center_commission) VALUES (?, ?, ?, ?)",
                              (t_name, p_fee, l_cost, c_comm))
                    conn.commit()
                    st.success("✅ Lab Test added!")
                    st.rerun()

            elif l_action == "✏️ Edit Test":
                labs_df = pd.read_sql_query("SELECT * FROM lab_tests", conn)
                if not labs_df.empty:
                    sel_lab = st.selectbox("Select Test:", labs_df['id'].astype(str) + " - " + labs_df['test_name'])
                    lid = int(sel_lab.split(" - ")[0])
                    lrow = labs_df[labs_df['id'] == lid].iloc[0]

                    c1, c2, c3 = st.columns(3)
                    tn_e = c1.text_input("Test Name:", value=str(lrow['test_name']))
                    pf_e = c2.number_input("Patient Fee:", value=float(lrow['patient_fee']))
                    lc_e = c3.number_input("Lab Cost:", value=float(lrow['lab_cost']))

                    if st.button("🔄 Update Lab Test"):
                        c.execute("UPDATE lab_tests SET test_name=?, patient_fee=?, lab_cost=?, center_commission=? WHERE id=?",
                                  (tn_e, pf_e, lc_e, pf_e - lc_e, lid))
                        conn.commit()
                        st.success("✅ Lab Test updated!")
                        st.rerun()

            elif l_action == "🗑️ Delete Test":
                labs_df = pd.read_sql_query("SELECT * FROM lab_tests", conn)
                if not labs_df.empty:
                    sel_del = st.selectbox("Select Test to Delete:", labs_df['id'].astype(str) + " - " + labs_df['test_name'], key="del_lab")
                    if st.button("🔥 Delete Lab Test"):
                        c.execute("DELETE FROM lab_tests WHERE id=?", (int(sel_del.split(" - ")[0]),))
                        conn.commit()
                        st.warning("Deleted!")
                        st.rerun()

        # --- 3. OPD PROCEDURES CRUD ---
        with m_tab3:
            st.markdown("### 🩺 OPD Procedures & Treatments (ECG, Dressing, Consultations)")
            o_action = st.radio("Action:", ["View All", "➕ Add Procedure", "✏️ Edit Procedure", "🗑️ Delete Procedure"], horizontal=True, key="o_action")

            if o_action == "View All":
                show_table(pd.read_sql_query("SELECT * FROM opd_procedures", conn), use_container_width=True)

            elif o_action == "➕ Add Procedure":
                c1, c2, c3 = st.columns(3)
                pr_name = c1.text_input("Procedure / Treatment Name (e.g. ECG, Dressing):")
                d_fee = c2.number_input("Default Doc Fee (LKR):", min_value=0.0, step=50.0)
                c_fee = c3.number_input("Center Fee (LKR):", min_value=0.0, step=50.0)

                if st.button("💾 Save OPD Procedure", type="primary"):
                    c.execute("INSERT INTO opd_procedures (proc_name, default_doc_fee, center_fee) VALUES (?, ?, ?)",
                              (pr_name, d_fee, c_fee))
                    conn.commit()
                    st.success("✅ OPD Procedure saved!")
                    st.rerun()

            elif o_action == "✏️ Edit Procedure":
                opd_df = pd.read_sql_query("SELECT * FROM opd_procedures", conn)
                if not opd_df.empty:
                    sel_opd = st.selectbox("Select Procedure:", opd_df['id'].astype(str) + " - " + opd_df['proc_name'])
                    opd_id = int(sel_opd.split(" - ")[0])
                    orow = opd_df[opd_df['id'] == opd_id].iloc[0]

                    c1, c2, c3 = st.columns(3)
                    pn_e = c1.text_input("Procedure Name:", value=str(orow['proc_name']))
                    df_e = c2.number_input("Default Doc Fee:", value=float(orow['default_doc_fee']))
                    cf_e = c3.number_input("Center Fee:", value=float(orow['center_fee']))

                    if st.button("🔄 Update OPD Procedure"):
                        c.execute("UPDATE opd_procedures SET proc_name=?, default_doc_fee=?, center_fee=? WHERE id=?",
                                  (pn_e, df_e, cf_e, opd_id))
                        conn.commit()
                        st.success("✅ OPD Procedure updated!")
                        st.rerun()

            elif o_action == "🗑️ Delete Procedure":
                opd_df = pd.read_sql_query("SELECT * FROM opd_procedures", conn)
                if not opd_df.empty:
                    sel_del_o = st.selectbox("Select Procedure to Delete:", opd_df['id'].astype(str) + " - " + opd_df['proc_name'])
                    if st.button("🔥 Delete OPD Procedure"):
                        c.execute("DELETE FROM opd_procedures WHERE id=?", (int(sel_del_o.split(" - ")[0]),))
                        conn.commit()
                        st.warning("Deleted!")
                        st.rerun()

        # --- 4. OPD PRESETS CRUD (NEW ADDITION) ---
        with m_tab_preset:
            st.markdown("### 📋 OPD Preset Prescriptions Management")
            pr_action = st.radio("Action:", ["View All", "➕ Add Preset", "✏️ Edit Preset", "🗑️ Delete Preset"], horizontal=True, key="pr_action")

            if pr_action == "View All":
                show_table(pd.read_sql_query("SELECT * FROM preset_prescriptions", conn), use_container_width=True)

            elif pr_action == "➕ Add Preset":
                preset_n = st.text_input("Preset Name (e.g., Fever Pack / Cold Pack):")
                items_desc = st.text_area("Preset Items / Description (e.g., Paracetamol 500mg x 10, Piriton x 5):")

                if st.button("💾 Save Preset Prescription", type="primary"):
                    if preset_n:
                        c.execute("INSERT INTO preset_prescriptions (preset_name, items_json) VALUES (?, ?)", (preset_n, items_desc))
                        conn.commit()
                        st.success(f"✅ Preset '{preset_n}' saved successfully!")
                        st.rerun()
                    else:
                        st.error("කරුණාකර Preset Name ඇතුළත් කරන්න.")

            elif pr_action == "✏️ Edit Preset":
                presets_df = pd.read_sql_query("SELECT * FROM preset_prescriptions", conn)
                if not presets_df.empty:
                    sel_pr = st.selectbox("Select Preset to Edit:", presets_df['id'].astype(str) + " - " + presets_df['preset_name'])
                    pr_id = int(sel_pr.split(" - ")[0])
                    prow = presets_df[presets_df['id'] == pr_id].iloc[0]

                    pr_name_e = st.text_input("Preset Name:", value=str(prow['preset_name']))
                    pr_desc_e = st.text_area("Preset Items / Description:", value=str(prow['items_json']))

                    if st.button("🔄 Update Preset Prescription"):
                        c.execute("UPDATE preset_prescriptions SET preset_name=?, items_json=? WHERE id=?", (pr_name_e, pr_desc_e, pr_id))
                        conn.commit()
                        st.success("✅ Preset updated!")
                        st.rerun()

            elif pr_action == "🗑️ Delete Preset":
                presets_df = pd.read_sql_query("SELECT * FROM preset_prescriptions", conn)
                if not presets_df.empty:
                    sel_del_p = st.selectbox("Select Preset to Delete:", presets_df['id'].astype(str) + " - " + presets_df['preset_name'])
                    if st.button("🔥 Delete Preset Prescription"):
                        c.execute("DELETE FROM preset_prescriptions WHERE id=?", (int(sel_del_p.split(" - ")[0]),))
                        conn.commit()
                        st.warning("Preset Deleted!")
                        st.rerun()

        # --- 5. DOCTORS CRUD ---
        with m_tab4:
            st.markdown("### 👨‍⚕️ Doctor & Scanning Management")
            d_action = st.radio("Action:", ["View All", "➕ Add Doctor", "✏️ Edit Doctor", "🗑️ Delete Doctor"], horizontal=True, key="d_action")

            if d_action == "View All":
                show_table(pd.read_sql_query("SELECT * FROM doctors", conn), use_container_width=True)

            elif d_action == "➕ Add Doctor":
                c1, c2 = st.columns(2)
                doc_name = c1.text_input("Doctor Name:")
                desig = c2.text_input("Designation / Specialization:")

                st.markdown("**Channeling Fees:**")
                cc1, cc2 = st.columns(2)
                d_fee_c = cc1.number_input("Doc Channeling Fee (LKR):", min_value=0.0, step=50.0)
                c_fee_c = cc2.number_input("Center Channeling Fee (LKR):", min_value=0.0, step=50.0)

                st.markdown("**Scanning Fees:**")
                sc1, sc2 = st.columns(2)
                d_fee_s = sc1.number_input("Doc Scan Fee (LKR):", min_value=0.0, step=50.0)
                c_fee_s = sc2.number_input("Center Scan Fee (LKR):", min_value=0.0, step=50.0)

                if st.button("💾 Save Doctor Profile", type="primary"):
                    c.execute("INSERT INTO doctors (doc_name, designation, doc_fee, center_fee, doc_scan_fee, center_scan_fee) VALUES (?, ?, ?, ?, ?, ?)",
                              (doc_name, desig, d_fee_c, c_fee_c, d_fee_s, c_fee_s))
                    conn.commit()
                    st.success("✅ Doctor added successfully!")
                    st.rerun()

            elif d_action == "✏️ Edit Doctor":
                docs_df = pd.read_sql_query("SELECT * FROM doctors", conn)
                if not docs_df.empty:
                    sel_doc = st.selectbox("Select Doctor:", docs_df['id'].astype(str) + " - " + docs_df['doc_name'])
                    doc_id = int(sel_doc.split(" - ")[0])
                    drow = docs_df[docs_df['id'] == doc_id].iloc[0]

                    c1, c2 = st.columns(2)
                    dn_e = c1.text_input("Doctor Name:", value=str(drow['doc_name']))
                    des_e = c2.text_input("Designation:", value=str(drow['designation']))

                    cc1, cc2 = st.columns(2)
                    dfc_e = cc1.number_input("Doc Channeling Fee:", value=float(drow['doc_fee']))
                    cfc_e = cc2.number_input("Center Channeling Fee:", value=float(drow['center_fee']))

                    sc1, sc2 = st.columns(2)
                    dfs_e = sc1.number_input("Doc Scan Fee:", value=float(drow.get('doc_scan_fee', 0.0)))
                    cfs_e = sc2.number_input("Center Scan Fee:", value=float(drow.get('center_scan_fee', 0.0)))

                    if st.button("🔄 Update Doctor Profile"):
                        c.execute("UPDATE doctors SET doc_name=?, designation=?, doc_fee=?, center_fee=?, doc_scan_fee=?, center_scan_fee=? WHERE id=?",
                                  (dn_e, des_e, dfc_e, cfc_e, dfs_e, cfs_e, doc_id))
                        conn.commit()
                        st.success("✅ Doctor profile updated!")
                        st.rerun()

            elif d_action == "🗑️ Delete Doctor":
                docs_df = pd.read_sql_query("SELECT * FROM doctors", conn)
                if not docs_df.empty:
                    sel_del_d = st.selectbox("Select Doctor to Delete:", docs_df['id'].astype(str) + " - " + docs_df['doc_name'])
                    if st.button("🔥 Delete Doctor Profile"):
                        c.execute("DELETE FROM doctors WHERE id=?", (int(sel_del_d.split(" - ")[0]),))
                        conn.commit()
                        st.warning("Deleted!")
                        st.rerun()

# ---------------------------------------------------------
# TAB 3: REPORTS & ACCOUNTS
# ---------------------------------------------------------
rep_tab_index = available_tabs.index("📊 Reports & Accounts")
with tabs[rep_tab_index]:
    st.subheader("📊 Reports & Inventory Tracking")
    
    col_sync1, col_sync2 = st.columns([1, 2])
    with col_sync1:
        if st.button("🔄 Sync All Local Data to Cloud", type="primary", use_container_width=True):
            try:
                local_sales = pd.read_sql_query("SELECT * FROM sales_history", conn)
                if not local_sales.empty and supabase:
                    success_count = 0
                    for _, row in local_sales.iterrows():
                        data_dict = {
                            'prescription_no': str(row['prescription_no']),
                            'bill_type': str(row['bill_type']),
                            'doctor_name': str(row['doctor_name']),
                            'bill_details': str(row['bill_details']),
                            'total_amount': float(row['total_amount']),
                            'doc_fee': float(row['doc_fee']),
                            'lab_cost': float(row['lab_cost']),
                            'center_profit': float(row['center_profit']),
                            'cost_price': float(row['cost_price']),
                            'date': str(row['date']),
                            'status': str(row.get('status', 'COMPLETED'))
                        }
                        try:
                            supabase.table("sales_history").insert(data_dict).execute()
                            success_count += 1
                        except Exception:
                            pass
                    st.success(f"✅ ගනුදෙනු {success_count} ක් Cloud එකට සාර්ථකව Sync විය!")
                else:
                    st.info("Sync කිරීමට ගනුදෙනු නොමැත හෝ Cloud Connection නොමැත.")
            except Exception as e:
                st.error(f"Sync Error: {e}")

    # Read Sales Data safely
    sales_full_df = pd.DataFrame()
    if supabase:
        try:
            res = supabase.table("sales_history").select("*").order("id", desc=True).execute()
            if res.data:
                sales_full_df = pd.DataFrame(res.data)
        except Exception:
            pass

    if sales_full_df.empty:
        sales_full_df = pd.read_sql_query("SELECT * FROM sales_history ORDER BY id DESC", conn)

    # STRICT DEDUPLICATION: Prevents Duplicate Calculation Errors in Cloud
    if not sales_full_df.empty:
        dedup_cols = [c for c in ['prescription_no', 'bill_type', 'total_amount', 'date'] if c in sales_full_df.columns]
        if dedup_cols:
            sales_full_df = sales_full_df.drop_duplicates(subset=dedup_cols, keep='last')

    main_rep_tab1, main_rep_tab2 = st.tabs(["💰 Financial Reports (ගිණුම් වාර්තා)", "⚠️ Expiry & Re-Order Tracking"])
    
    with main_rep_tab1:
        st.markdown("### 📅 Date Filter Options (දිනයන් අනුව වාර්තා තෝරන්න)")
        col_f1, col_f2, col_f3 = st.columns([1.5, 1.5, 1.5])
        
        with col_f1:
            time_filter = st.selectbox(
                "තෝරන්න (Range):", 
                ["සියල්ල (All Time)", "අද දින (Today)", "මෙම සතියේ (This Week)", "මෙම මාසයේ (This Month)", "දින සිට දින දක්වා (Custom Date)"]
            )

        start_date, end_date = None, None
        if time_filter == "දින සිට දින දක්වා (Custom Date)":
            with col_f2:
                start_date = st.date_input("ආරම්භක දිනය (From Date):", value=datetime.now().date())
            with col_f3:
                end_date = st.date_input("අවසාන දිනය (To Date):", value=datetime.now().date())

        sales_df = sales_full_df.copy()
        if not sales_df.empty and 'date' in sales_df.columns:
            sales_df['parsed_date'] = pd.to_datetime(sales_df['date'], errors='coerce')
            today = datetime.now().date()

            if time_filter == "අද දින (Today)":
                sales_df = sales_df[sales_df['parsed_date'].dt.date == today]
            elif time_filter == "මෙම සතියේ (This Week)":
                start_of_week = today - timedelta(days=today.weekday())
                sales_df = sales_df[sales_df['parsed_date'].dt.date >= start_of_week]
            elif time_filter == "මෙම මාසයේ (This Month)":
                sales_df = sales_df[(sales_df['parsed_date'].dt.month == today.month) & (sales_df['parsed_date'].dt.year == today.year)]
            elif time_filter == "දින සිට දින දක්වා (Custom Date)" and start_date and end_date:
                sales_df = sales_df[(sales_df['parsed_date'].dt.date >= start_date) & (sales_df['parsed_date'].dt.date <= end_date)]

        r_tab_summary, r_tab_sections, r_tab_all = st.tabs(["🌐 Grand Total Summary", "🏢 Section-Wise Breakdown", "🧾 All Transactions History"])
        
        with r_tab_summary:
            st.markdown(f"### **🌐 Grand Total Summary ({time_filter})**")
            
            if not sales_df.empty and 'status' in sales_df.columns:
                active_sales = sales_df[sales_df['status'].fillna('COMPLETED') != 'CANCELLED']
            else:
                active_sales = sales_df
            
            tot_revenue = active_sales['total_amount'].sum() if not active_sales.empty and 'total_amount' in active_sales.columns else 0.0
            tot_doc_pay = active_sales['doc_fee'].sum() if not active_sales.empty and 'doc_fee' in active_sales.columns else 0.0
            tot_lab_cost = active_sales['lab_cost'].sum() if not active_sales.empty and 'lab_cost' in active_sales.columns else 0.0
            tot_pharma_cost = active_sales['cost_price'].sum() if not active_sales.empty and 'cost_price' in active_sales.columns else 0.0
            tot_center_net_profit = active_sales['center_profit'].sum() if not active_sales.empty and 'center_profit' in active_sales.columns else 0.0
            
            col_g1, col_g2, col_g3 = st.columns(3)
            col_g1.metric("💰 Total Gross Revenue", f"LKR {tot_revenue:.2f}")
            col_g2.metric("💸 Direct Costs (Docs/Lab/Pharma)", f"LKR {(tot_doc_pay + tot_lab_cost + tot_pharma_cost):.2f}")
            col_g3.metric("📈 Center Net Profit", f"LKR {tot_center_net_profit:.2f}")
            
            st.markdown("---")
            if not active_sales.empty and 'bill_type' in active_sales.columns:
                dept_summary = active_sales.groupby('bill_type').agg(
                    Total_Revenue=('total_amount', 'sum'),
                    Doctor_Payable=('doc_fee', 'sum'),
                    Lab_Cost=('lab_cost', 'sum'),
                    Center_Profit=('center_profit', 'sum')
                ).reset_index()
                show_table(dept_summary, use_container_width=True)

        with r_tab_sections:
            st.markdown(f"### **🏢 Detailed Section-Wise Breakdown ({time_filter})**")
            if not sales_df.empty and 'status' in sales_df.columns:
                active_sales = sales_df[sales_df['status'].fillna('COMPLETED') != 'CANCELLED']
            else:
                active_sales = sales_df
            
            sec_lab, sec_pharma, sec_opd, sec_chan, sec_scan = st.tabs([
                "🧪 Laboratory", "💊 Pharmacy Profit", "🩺 OPD Income", "👨‍⚕️ Channeling Doc Fees", "🖥️ Scanning Report"
            ])
            
            def add_total_row(df_sec):
                if df_sec.empty:
                    return df_sec
                df_calc = df_sec.copy()
                total_row = {}
                for col in df_calc.columns:
                    if col in ['total_amount', 'doc_fee', 'lab_cost', 'center_profit', 'cost_price', 'discount']:
                        total_row[col] = df_calc[col].sum()
                    elif col in ['id', 'prescription_no', 'bill_type', 'doctor_name', 'status', 'parsed_date']:
                        total_row[col] = ""
                    elif col == 'bill_details':
                        total_row[col] = "TOTAL"
                    else:
                        total_row[col] = ""
                total_df = pd.DataFrame([total_row])
                return pd.concat([df_calc, total_df], ignore_index=True)

            with sec_lab:
                lab_sales = active_sales[active_sales['bill_type'] == 'Laboratory'] if not active_sales.empty and 'bill_type' in active_sales.columns else pd.DataFrame()
                show_table(add_total_row(lab_sales), use_container_width=True)

            with sec_pharma:
                pharma_sales = active_sales[active_sales['bill_type'] == 'Pharmacy'] if not active_sales.empty and 'bill_type' in active_sales.columns else pd.DataFrame()
                show_table(add_total_row(pharma_sales), use_container_width=True)

            with sec_opd:
                opd_sales = active_sales[active_sales['bill_type'].isin(['OPD', 'OPD Consultation', 'OPD Procedure'])] if not active_sales.empty and 'bill_type' in active_sales.columns else pd.DataFrame()
                show_table(add_total_row(opd_sales), use_container_width=True)

            with sec_chan:
                chan_sales = active_sales[active_sales['bill_type'] == 'Channeling'] if not active_sales.empty and 'bill_type' in active_sales.columns else pd.DataFrame()
                show_table(add_total_row(chan_sales), use_container_width=True)

            with sec_scan:
                scan_sales = active_sales[active_sales['bill_type'] == 'Scanning'] if not active_sales.empty and 'bill_type' in active_sales.columns else pd.DataFrame()
                show_table(add_total_row(scan_sales), use_container_width=True)

        with r_tab_all:
            st.markdown(f"### **🧾 All Transactions ({time_filter})**")
            show_table(sales_df, use_container_width=True)

    with main_rep_tab2:
        st.markdown("### ⚠️ Inventory Expiry & Low Stock Alerts")
        inv_check = pd.read_sql_query("SELECT * FROM inventory", conn)
        if not inv_check.empty:
            low_stock = inv_check[inv_check['stock_qty'] <= inv_check['reorder_level']]
            st.warning("⚠️ Low Stock Items")
            show_table(low_stock, use_container_width=True)

# ---------------------------------------------------------
# TAB 4: USER MANAGEMENT (Admin Only)
# ---------------------------------------------------------
if "⚙️ User Management" in available_tabs:
    user_tab_index = available_tabs.index("⚙️ User Management")
    with tabs[user_tab_index]:
        st.subheader("⚙️ User Management")
        users_df = pd.read_sql_query("SELECT username, role FROM users", conn)
        show_table(users_df, use_container_width=True)
