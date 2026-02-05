import csv
from decimal import Decimal
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file, flash
import psycopg2
from psycopg2 import pool
import os
from datetime import timedelta, datetime
import pandas as pd
from sqlalchemy import create_engine, text
import sqlite3
from pathlib import Path
from werkzeug.utils import secure_filename
import time
from functools import wraps
import io

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'pst-stocktake-secret-key-2024')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=0.5)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# Session timeout configuration
SESSION_TIMEOUT = timedelta(minutes=480)

# Create uploads directory if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('stocktake_databases', exist_ok=True)

# Database configuration from environment variables
DB_CONFIG = {
    'user': os.environ.get('DB_USER', 'prthanapat'),
    'host': os.environ.get('DB_HOST', '103.22.182.82'),
    'database': os.environ.get('DB_NAME', 'pstdb4'),
    'password': os.environ.get('DB_PASSWORD', '20020015'),
    'port': int(os.environ.get('DB_PORT', 5432))
}

# PostgreSQL connection pool - lazy initialization
db_pool = None

def init_db_pool():
    """Initialize database connection pool"""
    global db_pool
    if db_pool is None:
        db_pool = psycopg2.pool.SimpleConnectionPool(
            1, 20,
            **DB_CONFIG,
            connect_timeout=10
        )
    return db_pool

def get_db_connection():
    """Get a connection from the pool"""
    pool = init_db_pool()
    return pool.getconn()

def release_db_connection(conn):
    """Release connection back to the pool"""
    if db_pool:
        db_pool.putconn(conn)

def get_sqlalchemy_engine():
    """Get SQLAlchemy engine for PostgreSQL"""
    db_url = f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    return create_engine(db_url, connect_args={'connect_timeout': 10})

def get_sqlalchemy_engine_pstdb3():
    """Get SQLAlchemy engine for pstdb3 PostgreSQL"""
    db_url = f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/pstdb3"
    return create_engine(db_url, connect_args={'connect_timeout': 10})

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return jsonify({'error': 'Not authenticated'}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.before_request
def auto_logout():
    """Auto logout user if session has expired"""
    # Skip session timeout check for static files
    if request.endpoint and request.endpoint == 'static':
        return
    
    if 'username' in session:
        now = datetime.now()
        
        last_activity = session.get('last_activity')
        
        if last_activity:
            try:
                last_activity = datetime.fromisoformat(last_activity)
                
                if now - last_activity > SESSION_TIMEOUT:
                    session.clear()
                    return redirect(url_for('login', session_expired='1'))
            except (ValueError, TypeError):
                # Handle invalid timestamp format
                pass
        
        # Update activity time
        session['last_activity'] = now.isoformat()

@app.route('/')
def index():
    """Redirect to login if not authenticated, otherwise to home"""
    if 'username' in session:
        return redirect(url_for('home'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page and authentication"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not username or not password: 
            return render_template('login.html', error='Please enter both username and password')
        
        # Query database for user
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Query auth_user table
            cursor.execute("SELECT * FROM auth_user WHERE username = %s AND password = %s", 
                         (username, password))
            user = cursor.fetchone()
            
            cursor.close()
            
            if user:
                # Successful login
                session.permanent = True
                session['username'] = username
                session['last_activity'] = datetime.now().isoformat()
                return redirect(url_for('home'))
            else:
                return render_template('login.html', error='Invalid username or password')
                
        except Exception as e: 
            print(f"Database error: {e}")
            return render_template('login.html', error='Database connection error')
        finally:
            if conn: 
                release_db_connection(conn)
    
    # GET request - show login form
    return render_template('login.html')

@app.route('/home')
def home():
    """Home page - requires authentication"""
    if 'username' not in session:
        return redirect(url_for('login'))
    
    return render_template('home.html', username=session['username'])

@app.route('/create_cntnumber')
def create_cntnumber():
    """Create count number page - requires authentication"""
    if 'username' not in session:
        return redirect(url_for('login'))
    
    return render_template('create_cntnumber.html', username=session['username'])

@app.route('/location_manage')
def location_manage():
    """Location management page - requires authentication"""
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if 'cntnum' not in request.form:
        return jsonify({'error': 'CNTNUM is required in form data'}), 400
    
    return render_template('location_manage.html', username=session['username'], cntnum=request.form.get('cntnum', '').strip())

@app.route('/logout')
def logout():
    """Logout - clear session"""
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/b2s/search', methods=['POST'])
def search_cntnum():
    """Search for CNTNUM and return details"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json()
    cntnum = data.get('cntnum', '').strip()
    
    if not cntnum:
        return jsonify({'error': 'CNTNUM is required'}), 400
    
    try:
        engine = get_sqlalchemy_engine()
        
        # Query stocktakeid table
        query = text("""
            SELECT stcode, cntdate, branch as stname, count_step, status 
            FROM stocktakeid 
            WHERE cntnum = :cntnum
        """)
        
        df = pd.read_sql(query, engine, params={'cntnum': cntnum})
        
        if df.empty:
            return jsonify({'error': 'CNTNUM not found'}), 404
        
        # Get block vendor count
        block_vendor_query = text("""
            SELECT count(*) as count 
            FROM b2s_block_veno 
            WHERE cntnum = :cntnum
        """)
        df_vendor = pd.read_sql(block_vendor_query, engine, params={'cntnum': cntnum})
        
        # Get block SKU count
        block_sku_query = text("""
            SELECT count(*) as count 
            FROM b2s_block_sku 
            WHERE cntnum = :cntnum
        """)
        df_sku = pd.read_sql(block_sku_query, engine, params={'cntnum': cntnum})

        location_query = text("""
            with cte_counted as (
            select distinct stocktakeid as cntnum ,"location" as location_no
            from cntfiles_this_year cty 
            ), detail as (
            select lm.location_no,
                case 
                    when cted.location_no is not null then '02Green'
                    when lc.location_no is not null then '04Gray'
                    else '01White' end as location_status
            from location_master lm 
            left join cte_counted cted on lm.cntnum = cted.cntnum
                and lm.location_no = cted.location_no
            left join location_close lc on lm.cntnum = lc.cntnum 
                and lm.location_no = lc.location_no 
            where lm.cntnum = :cntnum
            union all 
            select cted1.location_no,
                '03Over' as location_status
            from cte_counted cted1
            left join location_master lm on cted1.cntnum = lm.cntnum 
                and cted1.location_no = lm.location_no 
            where lm.location_no is null and cted1.cntnum = :cntnum
            )
            select count(*) as location_all ,
                count(*) filter (where location_status = '04Gray') as location_closed,
                count(*) filter (where location_status = '03Over') as location_over,
                count(*) filter (where location_status = '02Green') as location_counted,
                count(*) filter (where location_status = '01White') as location_remaining,
                concat(
                    round(
                        (count(*) - count(*) filter (where location_status = '01White')) 
                        * 100.0 / nullif(count(*), 0)
                    , 2),
                    '%'
                ) as progress
            from detail""")
        
        df_location = pd.read_sql(location_query, engine, params={'cntnum': cntnum})

        update_soh_query = text("""
            select distinct msasdt
            from b2s_soh
            WHERE cntnum = :cntnum
        """)

        df_update_soh = pd.read_sql(update_soh_query, engine, params={'cntnum': cntnum})
        
        # Safely build result with defaults when any query returns empty
        stcode = df.iloc[0]['stcode'] if (not df.empty and 'stcode' in df.columns) else ''
        cntdate = str(df.iloc[0]['cntdate']) if (not df.empty and 'cntdate' in df.columns) else ''
        stname = df.iloc[0]['stname'] if (not df.empty and 'stname' in df.columns) else ''
        count_step = int(df.iloc[0]['count_step']) if (not df.empty and 'count_step' in df.columns and pd.notna(df.iloc[0]['count_step'])) else 0
        status = df.iloc[0]['status'] if (not df.empty and 'status' in df.columns) else ''
        
        blockVendor = int(df_vendor.iloc[0]['count']) if (not df_vendor.empty and 'count' in df_vendor.columns and pd.notna(df_vendor.iloc[0]['count'])) else 0
        blockSku = int(df_sku.iloc[0]['count']) if (not df_sku.empty and 'count' in df_sku.columns and pd.notna(df_sku.iloc[0]['count'])) else 0

        soh_update_date = str(df_update_soh.iloc[0]['msasdt']) if (not df_update_soh.empty and 'msasdt' in df_update_soh.columns) else 'ยังไม่เคยอัปเดท'

        locationAll = int(df_location.iloc[0]['location_all']) if (not df_location.empty and 'location_all' in df_location.columns and pd.notna(df_location.iloc[0]['location_all'])) else 0
        locationClosed = int(df_location.iloc[0]['location_closed']) if (not df_location.empty and 'location_closed' in df_location.columns and pd.notna(df_location.iloc[0]['location_closed'])) else 0
        locationOver = int(df_location.iloc[0]['location_over']) if (not df_location.empty and 'location_over' in df_location.columns and pd.notna(df_location.iloc[0]['location_over'])) else 0
        locationCounted = int(df_location.iloc[0]['location_counted']) if (not df_location.empty and 'location_counted' in df_location.columns and pd.notna(df_location.iloc[0]['location_counted'])) else 0
        locationRemaining = int(df_location.iloc[0]['location_remaining']) if (not df_location.empty and 'location_remaining' in df_location.columns and pd.notna(df_location.iloc[0]['location_remaining'])) else 0
        progress = df_location.iloc[0]['progress'] if (not df_location.empty and 'progress' in df_location.columns and pd.notna(df_location.iloc[0]['progress'])) else '0%'

        result = {
            'stcode': stcode,
            'cntdate': cntdate,
            'stname': stname,
            'count_step': count_step,
            'status': status,
            'blockVendor': blockVendor,
            'blockSku': blockSku,
            'soh_update_date': soh_update_date,
            'locationAll': locationAll,
            'locationClosed': locationClosed,
            'locationOver': locationOver,
            'locationCounted': locationCounted,
            'locationRemaining': locationRemaining,
            'progress': progress
        }
        return jsonify(result)

    except Exception as e:
        print(f"Error searching CNTNUM: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/b2s/create_cntnum', methods=['POST'])
def create_cntnum():
    """Create new CNTNUM"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json()
    username = session['username']
    bu = data.get('bu', '').strip()
    stcode = data.get('stcode', '').strip()
    atype = data.get('atype', '').strip()
    cntdate = data.get('cntdate', '').strip()
    
    if not all([bu, stcode, atype, cntdate]):
        return jsonify({'error': 'All fields are required'}), 400
    
    try:
        engine = get_sqlalchemy_engine()
        
        # Generate CNTNUM
        cntdate_plan = cntdate.replace('-', '')
        
        # Validate inputs
        if len(atype) < 2:
            return jsonify({'error': 'Invalid ATYPE format'}), 400
        if len(cntdate) != 10 or cntdate[4] != '-' or cntdate[7] != '-': 
            return jsonify({'error': 'Invalid date format.  Use YYYY-MM-DD'}), 400
        
        cntnum = bu + stcode + atype[1:2] + cntdate[: 4] + cntdate[5:7] + cntdate[8:10] + '001'
        
        # Check if plan exists
        plan_query = text("""
            SELECT bu, stcode, branch 
            FROM planall2 
            WHERE bu = :bu AND stcode = :stcode AND cntdate = :cntdate_plan
        """)
        df_plan = pd.read_sql(plan_query, engine, params={
            'bu': bu, 
            'stcode': stcode, 
            'cntdate_plan': cntdate_plan
        })
        
        # Check if CNTNUM already exists
        check_query = text("""
            SELECT 1 
            FROM stocktakeid 
            WHERE cntnum = :cntnum
        """)
        df_stocktakeid = pd.read_sql(check_query, engine, params={'cntnum': cntnum})
        
        if df_plan.empty:
            return jsonify({'error': 'ไม่พบข้อมูลใน planall2 กรุณาตรวจสอบข้อมูล'}), 400
        
        if not df_stocktakeid.empty:
            return jsonify({'error': f'CNTNUM {cntnum} มีอยู่แล้ว'}), 400
        
        # Insert new CNTNUM
        branch = df_plan.iloc[0]['branch']
        insert_query = text("""
            INSERT INTO stocktakeid (cntnum, bu, stcode, atype, cntdate, username, count_step, status, branch)
            VALUES (:cntnum, :bu, :stcode, :atype, :cntdate, :username, '1', 'สร้าง CNTNUM', :branch)
        """)
        
        with engine.connect() as conn:
            conn.execute(insert_query, {
                'cntnum': cntnum,
                'bu': bu,
                'stcode': stcode,
                'atype': atype,
                'cntdate': cntdate,
                'username':  username,
                'branch': branch
            })
            conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'สร้าง CNTNUM สำเร็จ:  {cntnum}',
            'cntnum': cntnum
        })
        
    except Exception as e:
        print(f"Error creating CNTNUM: {e}")
        return jsonify({'error': str(e)}), 500
    
@app.route('/api/b2s/countclose01to04', methods=['POST'])
def countclose01to04():
    """Count Close 01 to 04"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json(silent=True)

    if not data or 'cntnum' not in data:
        return jsonify({'error': 'CNTNUM is required'}), 400

    try:
        engine = get_sqlalchemy_engine()
        username = session['username']
        cntnum_raw = data.get('cntnum', '')
        cntnum = str(cntnum_raw).strip()
        
        if not cntnum:
            return jsonify({'error': 'CNTNUM is required'}), 400
        # Basic validation (allow underscores)
        if not cntnum.replace('_', '').isalnum():
            return jsonify({'error': 'Invalid CNTNUM format'}), 400

        # check count status
        status_query = text("""select count_step from stocktakeid where cntnum = :cntnum""")
        df_status = pd.read_sql(status_query, engine, params={'cntnum': cntnum})

        if df_status.empty:
            return jsonify({'error': 'ไม่พบ CNTNUM กรุณา Create CNTNUM ก่อน'}), 404
        
        count_step = int(df_status.iloc[0]['count_step'])

        if count_step != 1:
            return jsonify({'error': 'ไม่สามารถปิด Count ได้ เนื่องจากสถานะไม่ถูกต้อง'}), 400
        

        # เตรียมข้อมูลสำหรับ Count 4
        query_b2s_count_0_1_edited = text("""
            SELECT
            bsc.cntnum,
            bsm.sku_type,
            bsc.location,
            bsc.seq,
            bsc.sku,
            bsm.ibc,
            bsm."sbc#1" AS sbc,
            bsm.brand_id,
            bsm.sku_descr,
            bsm.vendor,
            bsm.v_name,
            bsm.dept,
            bsm.dept_name,
            bsm.sub_dpt,
            bsm.s_dpt_name,
            COALESCE(bses.qnt::double precision, bsc.qnt) AS qnt
            FROM b2s_count_0_1 bsc
            LEFT JOIN b2s_edit_01_seq bses
            ON bsc.cntnum = bses.cntnum
            AND bsc.location = bses.location
            AND bsc.sku = bses.sku
            AND bsc.seq = bses.seq
            LEFT JOIN b2s_master bsm
            ON bsc.sku = bsm.sku_no
            where bsc.cntnum = :cntnum
                                                                        
            UNION ALL

            SELECT
            bses.cntnum,
            bsm2.sku_type,
            bses.location,
            bses.seq,
            bses.sku,
            bsm2.ibc,
            bsm2."sbc#1" AS sbc,
            bsm2.brand_id,
            bsm2.sku_descr,
            bsm2.vendor,
            bsm2.v_name,
            bsm2.dept,
            bsm2.dept_name,
            bsm2.sub_dpt,
            bsm2.s_dpt_name,
            bses.qnt
            FROM b2s_edit_01_seq bses
            LEFT JOIN b2s_count_0_1 bsc
            ON bses.cntnum = bsc.cntnum
            AND bses.location = bsc.location
            AND bses.sku = bsc.sku
            AND bses.seq = bsc.seq
            LEFT JOIN b2s_master bsm2
            ON bses.sku = bsm2.sku_no
            WHERE bsc.sku IS NULL and bses.cntnum = :cntnum;
        """)

        df_count_0_1_edited = pd.read_sql(query_b2s_count_0_1_edited, engine, params={'cntnum': cntnum})

        df = df_count_0_1_edited.groupby(['cntnum', 'sku_type', 'location', 'sku', 'ibc', 'sbc', 
                                          'brand_id', 'sku_descr', 'vendor', 'v_name', 'dept', 
                                          'dept_name', 'sub_dpt', 's_dpt_name'], as_index=False).agg({'qnt': 'sum'})

        # Insert into b2s_count_1
        if df.empty:
            return jsonify({'error': 'ไม่พบข้อมูลการนับสต็อกใน Count 1'}), 404
        
        if not df.empty:
            df.to_sql('b2s_count_1', engine, if_exists='append', index=False,method='multi')


        # update count step to 4
        update_query = text("""update stocktakeid set count_step = '4', status = 'ปิด Count 1 แล้ว', modify = NOW(), username_modify = :username where cntnum = :cntnum""")
        with engine.connect() as conn:
            conn.execute(update_query, {
                'cntnum': cntnum,
                'username': username
            })
            conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'ปิด Count 1 สำเร็จ:  {cntnum} / จำนวน {len(df)} รายการ / จำนวนชิ้น {df["qnt"].sum()}',
            'cntnum': cntnum
        })
        
    except Exception as e:
        print(f"Error creating CNTNUM: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/b2s/create_master', methods=['POST'])
def create_master():
    """Create Master database file"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json()
    cntnum = data. get('cntnum', '').strip()
    
    if not cntnum:
        return jsonify({'error': 'CNTNUM is required'}), 400
    
    # Validate CNTNUM format (alphanumeric only)
    if not cntnum.replace('_', '').isalnum():
        return jsonify({'error': 'Invalid CNTNUM format'}), 400
    
    try: 
        engine = get_sqlalchemy_engine()
        username = session['username']
        
        # Check if CNTNUM exists
        check_query = text("""
            SELECT cntnum, bu, stcode, cntdate, atype, count_step, status, branch 
            FROM stocktakeid 
            WHERE cntnum = :cntnum
        """)
        df_check = pd.read_sql(check_query, engine, params={'cntnum': cntnum})
        
        if df_check. empty:
            return jsonify({'error': 'ไม่พบ CNTNUM กรุณา Create CNTNUM ก่อน'}), 404
        
        # Check if locations exist
        location_count_query = text("""
            SELECT COUNT(*) as count 
            FROM location_master 
            WHERE cntnum = :cntnum
        """)
        df_location_count = pd.read_sql(location_count_query, engine, params={'cntnum': cntnum})
        location_count = int(df_location_count.iloc[0]['count'])
        
        if location_count == 0:
            return jsonify({
                'error': 'ไม่พบ Location กรุณา Add Location ก่อนสร้าง Master',
                'warning': True
            }), 400
        
        # Create SQLite database with secure path
        db_filename = secure_filename(f"{cntnum}.db")
        db_path = os.path. join("stocktake_databases", db_filename)
        
        # Check if file already exists
        if os.path.exists(db_path):
            # Backup old file
            backup_path = os.path.join("stocktake_databases", f"{cntnum}_backup_{int(time.time())}.db")
            os.rename(db_path, backup_path)
        
        conn_sqlite = sqlite3.connect(db_path)
        conn_sqlite.execute("PRAGMA foreign_keys = ON;")
        
        # Import b2s_create_master logic
        from python_cdoe_model.b2s_create_master import SQL_SCHEMA
        
        cur = conn_sqlite.cursor()
        cur.executescript(SQL_SCHEMA)
        conn_sqlite.commit()
        
        engine_sqlite = create_engine(f"sqlite:///{db_path}")
        
        # Insert stocktakes data
        stocktakeid_query = text("""
            SELECT 
                cntnum as "countName",
                stcode as "storeCode",
                branch as "storeName",
                bu,
                branch
            FROM stocktakeid
            WHERE cntnum = :cntnum
        """)
        stocktakeid_df = pd.read_sql(stocktakeid_query, engine, params={'cntnum': cntnum})
        
        if stocktakeid_df.empty:
            conn_sqlite.close()
            return jsonify({'error': 'ไม่พบข้อมูล Stocktake'}), 404
        
        stocktakeid_df. to_sql('stocktakes', engine_sqlite, if_exists='append', index=False)
        
        # Insert location_masters data
        location_query = text("""
            SELECT 
                location_no as location,
                cntnum as "stocktakeId"
            FROM location_master 
            WHERE cntnum = :cntnum
        """)
        location_df = pd.read_sql(location_query, engine, params={'cntnum': cntnum})
        
        if not location_df.empty:
            location_df.to_sql('location_masters', engine_sqlite, if_exists='append', index=False)
        
        # Insert users data
        users_query = text("""
            SELECT 
                employee_code as username, 
                email, 
                encryptedpassword as "encryptedPassword",
                employee_code as empCode,
                split_part(eng_name, ' ', 1) AS "firstName",
                split_part(eng_name, ' ', 2) AS "lastName",
                first_name as "firstNameTh", 
                last_name as "lastNameTh",
                sub_hub as hub, 
                position
            FROM employees 
            WHERE job_status IS NULL
        """)
        users_df = pd.read_sql(users_query, engine)
        
        if not users_df.empty:
            users_df.to_sql('users', engine_sqlite, if_exists='append', index=False)
        
        # Add additional users
        additional_users = []
        password = "$2a$10$d. QrLlbWIQwZ/hoqBFxCVeSJTvQTyy/KSW7kh3Rf6bnMcnKWpKCrS"
        for prefix in ["ajis", "pcs", "ssd", "sto", "daywork"]:
            for i in range(1, 51):
                username_gen = f"{prefix}{i: 02d}"
                additional_users.append({
                    "username": username_gen,
                    "encryptedPassword": password,
                    "firstName": username_gen,
                    "lastName":  "",
                    "email": f"{username_gen}@example. com",
                    "empCode": username_gen,
                    "hub": "",
                    "position": "",
                    "firstNameTh": "",
                    "lastNameTh": ""
                })
        
        additional_users_df = pd.DataFrame(additional_users)
        additional_users_df.to_sql('users', engine_sqlite, if_exists='append', index=False)
        
        # Insert pda_masters data
        pda_masters_query = text("""
            SELECT 
                s.stcode as "storeCode",
                s.branch as "storeName",
                vendor as "vendorCode",
                v_name as "vendorName",
                lpad(sku_no, 13, '0') as sku,
                lpad(sku_no, 13, '0') as "barcodeIBC",
                case when ibc = '0' then null else lpad(ibc, 13, '0') end as barcode1,
                case when "sbc#1" = '0' then null else lpad("sbc#1", 13, '0') end as barcode2,
                case when "sbc#2" = '0' then null else lpad("sbc#2", 13, '0') end as barcode3,
                case when "sbc#3" = '0' then null else lpad("sbc#3", 13, '0') end as barcode4,
                case when "sbc#4" = '0' then null else lpad("sbc#4", 13, '0') end as barcode5,
                case when "sbc#5" = '0' then null else lpad("sbc#5", 13, '0') end as barcode6,
                regexp_replace(sku_descr, E'[\\n\\r,]', '', 'g') as "productName",
                color_des as "color",
                inner_pack as "unitOfMeasure",
                size_des as "size",
                reg_retail as "cost",
                0 as stock,
                'A' as status         
            FROM b2s_master bm
            LEFT JOIN b2s_block_sku_all bsbsa ON bm. sku_no = bsbsa.sku AND bsbsa. cntnum = :cntnum
            LEFT JOIN stocktakeid s ON s.cntnum = :cntnum
            WHERE sku_type <> '03' and sku_status <> 'P' AND bsbsa.sku IS NULL
        """)
        pda_masters_df = pd.read_sql(pda_masters_query, engine, params={'cntnum': cntnum})
        pda_masters_df['stocktakeId'] = cntnum
        
        if not pda_masters_df. empty:
            pda_masters_df.to_sql('pda_masters', engine_sqlite, if_exists='append', index=False)
        
        conn_sqlite.close()
        
        # Update status in stocktakeid
        update_status_query = text("""
            UPDATE stocktakeid 
            SET status = 'อยู่ระหว่างนับสต็อก',
                modify = NOW(),
                username_modify = :username
            WHERE cntnum = :cntnum
        """)
        
        with engine.connect() as conn:
            conn.execute(update_status_query, {
                'cntnum': cntnum,
                'username': username
            })
            conn.commit()
        
        # Get statistics
        file_size = os.path.getsize(db_path)
        file_size_mb = round(file_size / (1024 * 1024), 2)
        
        return jsonify({
            'success': True,
            'message': f'สร้าง Master Database สำเร็จ',
            'filename': f'{cntnum}. db',
            'stats': {
                'locations': len(location_df),
                'users': len(users_df) + len(additional_users_df),
                'products': len(pda_masters_df),
                'file_size_mb': file_size_mb
            }
        })
        
    except Exception as e:
        print(f"Error creating master:  {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/b2s/download_master/<cntnum>', methods=['GET'])
def download_master(cntnum):
    """Download Master. db file"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    # Validate CNTNUM format
    if not cntnum.replace('_', '').isalnum():
        return jsonify({'error':  'Invalid CNTNUM format'}), 401
    
    try:
        engine = get_sqlalchemy_engine()
        
        # Check if CNTNUM exists in database
        check_query = text("SELECT 1 FROM stocktakeid WHERE cntnum = :cntnum")
        df_check = pd.read_sql(check_query, engine, params={'cntnum': cntnum})
        
        if df_check. empty:
            return jsonify({'error': 'ไม่พบ CNTNUM กรุณา Create CNTNUM ก่อน'}), 404
        
        # Check if file exists with secure path
        db_filename = secure_filename(f"{cntnum}.db")
        db_path = os.path.join("stocktake_databases", db_filename)
        if not os.path.exists(db_path):
            return jsonify({'error': 'กรุณา Create Master ก่อน'}), 404
        
        return send_file(db_path, as_attachment=True, download_name=f'{cntnum}.db')
        
    except Exception as e: 
        print(f"Error downloading master: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/b2s/add_location', methods=['POST'])
def add_Location():
    """Add location from Excel file"""
    print(session['username'])
    print(request.form.get('cntnum', '').strip())
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    if 'cntnum' not in request.form:
        return jsonify({'error': 'CNTNUM is required in form data'}), 400
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # ตรวจสอบนามสกุลไฟล์
    allowed_extensions = {'.xlsx', '.xls'}
    file_ext = os.path.splitext(file. filename)[1].lower()
    if file_ext not in allowed_extensions:
        return jsonify({'error': 'Only Excel files (. xlsx, .xls) are allowed'}), 400
    
    try:
        username = session['username']
        cntnum = request.form.get('cntnum', '').strip()
        
        if not cntnum:  
            return jsonify({'error': 'CNTNUM is required'}), 400
        
        # Read Excel file
        df = pd.read_excel(file, sheet_name='Sheet1')
        
        # ตรวจสอบว่าไฟล์ว่างหรือไม่
        if df.empty:
            return jsonify({'error': 'Excel file is empty'}), 400
        
        # ตรวจสอบ columns ที่จำเป็น
        required_columns = ['location_no', 'cntnum']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return jsonify({
                'error': f'Excel file is missing required columns: {", ".join(missing_columns)}'
            }), 400
        
        # ตรวจสอบว่า cntnum ในไฟล์ตรงกับที่ส่งมาหรือไม่
        if not all(df['cntnum'] == cntnum):
            return jsonify({
                'error': f'CNTNUM in Excel file does not match the provided CNTNUM: {cntnum}'
            }), 400
        
        # ทำความสะอาดข้อมูล
        df['location_no'] = df['location_no'].astype(str).str.strip()
        df['cntnum'] = df['cntnum'].astype(str).str.strip()
        
        # ลบแถวที่มีค่าว่าง
        df = df.dropna(subset=['location_no', 'cntnum'])
        
        if df.empty:
            return jsonify({'error': 'No valid data found in Excel file'}), 400
        

        
        engine = get_sqlalchemy_engine()
        
        # ดึงข้อมูลที่มีอยู่แล้วในฐานข้อมูล
        df_query = pd.read_sql(
            text("SELECT location_no, cntnum FROM location_master WHERE cntnum = :cntnum"), 
            engine, 
            params={'cntnum':  cntnum}
        )
        
        # หาข้อมูลที่ยังไม่มีในฐานข้อมูล (anti-join)
        df_merged = pd.merge(
            df, 
            df_query, 
            on=['location_no', 'cntnum'], 
            how='left', 
            indicator=True
        )
        
        # กรองเฉพาะข้อมูลใหม่ (left_only)
        df_new = df_merged[df_merged['_merge'] == 'left_only']. drop(columns=['_merge'])
        
        total_count = len(df)
        new_count = len(df_new)
        existing_count = total_count - new_count
        
        if not df_new.empty:

            df_new['username'] = username
            df_new['location_bar'] = '*' + df_new['location_no'].astype(str) + '*'

            df_new.to_sql('location_master', engine, if_exists='append', index=False,method='multi')

            message = f'เพิ่มข้อมูลสำเร็จ {new_count} รายการ จากทั้งหมด {total_count} รายการ'
            if existing_count > 0:
                message += f' (ข้ามข้อมูลที่มีอยู่แล้ว {existing_count} รายการ)'
        else:
            message = f'ไม่มีข้อมูลใหม่ที่จะเพิ่ม (ข้อมูลทั้งหมด {total_count} รายการมีอยู่แล้ว)'
        
        return jsonify({
            'success': True,
            'message': message,
            'total_count': total_count,
            'new_count': new_count,
            'existing_count': existing_count
        })

    except pd.errors.EmptyDataError:
        return jsonify({'error':  'Excel file is empty or corrupted'}), 400
    except pd.errors.ParserError:
        return jsonify({'error': 'Unable to parse Excel file'}), 400
    except Exception as e:  
        print(f"Error adding location: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500
    
@app.route('/api/b2s/add_block_vendor', methods=['POST'])
@login_required
def add_block_vendor():
    """Add block vendor from Excel file"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    if 'cntnum' not in request.form:
        return jsonify({'error': 'CNTNUM is required in form data'}), 400
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # ตรวจสอบนามสกุลไฟล์
    allowed_extensions = {'.xlsx', '.xls'}
    file_ext = os.path.splitext(file. filename)[1].lower()
    if file_ext not in allowed_extensions:
        return jsonify({'error': 'Only Excel files (. xlsx, .xls) are allowed'}), 400
    
    try:
        username = session['username']
        cntnum = request.form.get('cntnum', '').strip()
        
        if not cntnum:  
            return jsonify({'error': 'CNTNUM is required'}), 400
        
        # Read Excel file
        df = pd. read_excel(file, sheet_name='Sheet1')
        
        # ตรวจสอบว่าไฟล์ว่างหรือไม่
        if df.empty:
            return jsonify({'error': 'Excel file is empty'}), 400
        
        # ตรวจสอบ columns ที่จำเป็น
        required_columns = ['cntnum', 'veno','vdnm','sdpt','remark']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return jsonify({
                'error': f'Excel file is missing required columns: {", ".join(missing_columns)}'
            }), 400
        
        # ทำความสะอาดข้อมูล
        df['cntnum'] = df['cntnum'].astype(str).str.strip()
        df['veno'] = df['veno'].astype(str).str.strip()
        df['vdnm'] = df['vdnm'].astype(str).str.strip()
        df['sdpt'] = df['sdpt'].astype(str).str.strip()
        df['remark'] = df['remark'].astype(str).str.strip()
        
        # ลบแถวที่มีค่าว่าง
        df = df.dropna(subset=['cntnum', 'veno','sdpt'])
        
        if df.empty:
            return jsonify({'error': 'No valid data found in Excel file'}), 400
        
        # ตรวจสอบว่า cntnum ในไฟล์ตรงกับที่ส่งมาหรือไม่
        #if not all(df['cntnum'] == cntnum):
        #    return jsonify({
        #        'error': f'CNTNUM in Excel file does not match the provided CNTNUM: {cntnum}'
        #    }), 400
        
        engine = get_sqlalchemy_engine()
        
        # ดึงข้อมูลที่มีอยู่แล้วในฐานข้อมูล
        df_query = pd.read_sql(
            text("SELECT veno, sdpt, cntnum FROM b2s_block_veno WHERE cntnum = :cntnum"), 
            engine, 
            params={'cntnum':  cntnum}
        )
        
        # หาข้อมูลที่ยังไม่มีในฐานข้อมูล (anti-join)
        df_merged = pd.merge(
            df, 
            df_query, 
            on=['veno', 'sdpt', 'cntnum'], 
            how='left', 
            indicator=True
        )
        
        # กรองเฉพาะข้อมูลใหม่ (left_only)
        df_new = df_merged[df_merged['_merge'] == 'left_only']. drop(columns=['_merge'])
        
        total_count = len(df)
        new_count = len(df_new)
        existing_count = total_count - new_count
        
        if not df_new.empty:

            df_new['username'] = username

            df_new.to_sql('b2s_block_veno', engine, if_exists='append', index=False)

            query_to_all = text("""select bsbv.cntnum 
                    ,bsm.sku_no as sku
                from b2s_block_veno bsbv 
                left join b2s_master bsm on bsbv.veno = bsm.vendor and bsbv.sdpt = bsm.sub_dpt 
                where cntnum = :cntnum
                    and bsbv.sdpt <> 'all'
                union all
                select bsbv.cntnum 
                    ,bsm.sku_no as sku
                from b2s_block_veno bsbv 
                left join b2s_master bsm on bsbv.veno = bsm.vendor
                where cntnum = :cntnum
                    and bsbv.sdpt = 'all'""")
            
            df_block_sku_all = pd.read_sql(query_to_all, engine, params={'cntnum': cntnum})
            df_block_sku_all.to_sql('b2s_block_sku_all', engine, if_exists='append', index=False)

            message = f'เพิ่มข้อมูลสำเร็จ {new_count} รายการ จากทั้งหมด {total_count} รายการ'
            if existing_count > 0:
                message += f' (ข้ามข้อมูลที่มีอยู่แล้ว {existing_count} รายการ)'
        else:
            message = f'ไม่มีข้อมูลใหม่ที่จะเพิ่ม (ข้อมูลทั้งหมด {total_count} รายการมีอยู่แล้ว)'
        
        return jsonify({
            'success': True,
            'message': message,
            'total_count': total_count,
            'new_count': new_count,
            'existing_count': existing_count
        })

    except pd.errors.EmptyDataError:
        return jsonify({'error':  'Excel file is empty or corrupted'}), 400
    except pd.errors.ParserError:
        return jsonify({'error': 'Unable to parse Excel file'}), 400
    except Exception as e:  
        print(f"Error adding location: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500
    
@app.route('/api/b2s/add_block_sku', methods=['POST'])
def add_block_sku():
    """Add block SKU from Excel file"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    if 'cntnum' not in request.form:
        return jsonify({'error': 'CNTNUM is required in form data'}), 400
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # ตรวจสอบนามสกุลไฟล์
    allowed_extensions = {'.xlsx', '.xls'}
    file_ext = os.path.splitext(file. filename)[1].lower()
    if file_ext not in allowed_extensions:
        return jsonify({'error': 'Only Excel files (. xlsx, .xls) are allowed'}), 400
    
    try:
        username = session['username']
        cntnum = request.form.get('cntnum', '').strip()
        
        if not cntnum:  
            return jsonify({'error': 'CNTNUM is required'}), 400
        
        # Read Excel file
        df = pd. read_excel(file, sheet_name='Sheet1')
        
        # ตรวจสอบว่าไฟล์ว่างหรือไม่
        if df.empty:
            return jsonify({'error': 'Excel file is empty'}), 400
        
        # ตรวจสอบ columns ที่จำเป็น
        required_columns = ['cntnum', 'sku']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return jsonify({
                'error': f'Excel file is missing required columns: {", ".join(missing_columns)}'
            }), 400
        
        # ทำความสะอาดข้อมูล
        df['cntnum'] = df['cntnum'].astype(str).str.strip()
        df['sku'] = df['sku'].astype(str).str.strip()
        
        # ลบแถวที่มีค่าว่าง
        df = df.dropna(subset=['cntnum', 'sku'])
        
        if df.empty:
            return jsonify({'error': 'No valid data found in Excel file'}), 400
        
        # ตรวจสอบว่า cntnum ในไฟล์ตรงกับที่ส่งมาหรือไม่
        #if not all(df['cntnum'] == cntnum):
        #    return jsonify({
        #        'error': f'CNTNUM in Excel file does not match the provided CNTNUM: {cntnum}'
        #    }), 400
        
        engine = get_sqlalchemy_engine()
        
        # ดึงข้อมูลที่มีอยู่แล้วในฐานข้อมูล
        df_query = pd.read_sql(
            text("SELECT sku, cntnum FROM b2s_block_sku WHERE cntnum = :cntnum"), 
            engine, 
            params={'cntnum':  cntnum}
        )
        
        # หาข้อมูลที่ยังไม่มีในฐานข้อมูล (anti-join)
        df_merged = pd.merge(
            df, 
            df_query, 
            on=['sku', 'cntnum'], 
            how='left', 
            indicator=True
        )
        
        # กรองเฉพาะข้อมูลใหม่ (left_only)
        df_new = df_merged[df_merged['_merge'] == 'left_only']. drop(columns=['_merge'])
        
        total_count = len(df)
        new_count = len(df_new)
        existing_count = total_count - new_count
        
        if not df_new.empty:

            df_new['username'] = username

            df_new.to_sql('b2s_block_sku', engine, if_exists='append', index=False)

            df_block_sku_all = df_new[['cntnum', 'sku']].copy()
        
            df_block_sku_all.to_sql('b2s_block_sku_all', engine, if_exists='append', index=False)

            message = f'เพิ่มข้อมูลสำเร็จ {new_count} รายการ จากทั้งหมด {total_count} รายการ'
            if existing_count > 0:
                message += f' (ข้ามข้อมูลที่มีอยู่แล้ว {existing_count} รายการ)'
        else:
            message = f'ไม่มีข้อมูลใหม่ที่จะเพิ่ม (ข้อมูลทั้งหมด {total_count} รายการมีอยู่แล้ว)'
        
        return jsonify({
            'success': True,
            'message': message,
            'total_count': total_count,
            'new_count': new_count,
            'existing_count': existing_count
        })

    except pd.errors.EmptyDataError:
        return jsonify({'error':  'Excel file is empty or corrupted'}), 400
    except pd.errors.ParserError:
        return jsonify({'error': 'Unable to parse Excel file'}), 400
    except Exception as e:  
        print(f"Error adding location: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/api/b2s/close_location', methods=['POST'])
@login_required
def close_Location():
    """Close location from Excel file"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    if 'cntnum' not in request.form:
        return jsonify({'error': 'CNTNUM is required in form data'}), 400
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # ตรวจสอบนามสกุลไฟล์
    allowed_extensions = {'.xlsx', '.xls'}
    file_ext = os.path.splitext(file. filename)[1].lower()
    if file_ext not in allowed_extensions:
        return jsonify({'error': 'Only Excel files (. xlsx, .xls) are allowed'}), 400
    
    try:
        username = session['username']
        cntnum = request.form.get('cntnum', '').strip()
        
        if not cntnum:  
            return jsonify({'error': 'CNTNUM is required'}), 400
        
        # Read Excel file
        df = pd.read_excel(file, sheet_name='Sheet1')
        
        # ตรวจสอบว่าไฟล์ว่างหรือไม่
        if df.empty:
            return jsonify({'error': 'Excel file is empty'}), 400
        
        # ตรวจสอบ columns ที่จำเป็น
        required_columns = ['location_no', 'cntnum']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return jsonify({
                'error': f'Excel file is missing required columns: {", ".join(missing_columns)}'
            }), 400
        
        # ตรวจสอบว่า cntnum ในไฟล์ตรงกับที่ส่งมาหรือไม่
        if not all(df['cntnum'] == cntnum):
            return jsonify({
                'error': f'CNTNUM in Excel file does not match the provided CNTNUM: {cntnum}'
            }), 400
        
        # ทำความสะอาดข้อมูล
        df['location_no'] = df['location_no'].astype(str).str.strip()
        df['cntnum'] = df['cntnum'].astype(str).str.strip()
        print(f'df_new: {df}')
        # ลบแถวที่มีค่าว่าง
        df = df.dropna(subset=['location_no', 'cntnum'])
        
        if df.empty:
            return jsonify({'error': 'No valid data found in Excel file'}), 400
    
        
        engine = get_sqlalchemy_engine()
        
        # ดึงข้อมูลที่มีอยู่แล้วในฐานข้อมูล
        df_query = pd.read_sql(
            text("SELECT location_no, cntnum FROM location_close WHERE cntnum = :cntnum"), 
            engine, 
            params={'cntnum':  df.iloc[0]['cntnum']}
        )
        print(f'df_new: {df_query}')
        # หาข้อมูลที่ยังไม่มีในฐานข้อมูล (anti-join)
        df_merged = pd.merge(
            df, 
            df_query, 
            on=['location_no', 'cntnum'], 
            how='left', 
            indicator=True
        )
        
        # กรองเฉพาะข้อมูลใหม่ (left_only)
        df_new = df_merged[df_merged['_merge'] == 'left_only'].drop(columns=['_merge'])

        total_count = len(df)
        new_count = len(df_new)
        existing_count = total_count - new_count
        
        if not df_new.empty:

            df_new['username'] = username

            df_new.to_sql('location_close', engine, if_exists='append', index=False)

            message = f'เพิ่มข้อมูลสำเร็จ {new_count} รายการ จากทั้งหมด {total_count} รายการ'
            if existing_count > 0:
                message += f' (ข้ามข้อมูลที่มีอยู่แล้ว {existing_count} รายการ)'
        else:
            message = f'ไม่มีข้อมูลใหม่ที่จะเพิ่ม (ข้อมูลทั้งหมด {total_count} รายการมีอยู่แล้ว)'
        
        return jsonify({
            'success': True,
            'message': message,
            'total_count': total_count,
            'new_count': new_count,
            'existing_count': existing_count
        })

    except pd.errors.EmptyDataError:
        return jsonify({'error':  'Excel file is empty or corrupted'}), 400
    except pd.errors.ParserError:
        return jsonify({'error': 'Unable to parse Excel file'}), 400
    except Exception as e:  
        print(f"Error adding location: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/api/b2s/update_soh', methods=['POST'])
def update_soh():
    """Update SOH from Excel file"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    if 'cntnum' not in request.form:
        return jsonify({'error': 'CNTNUM is required in form data'}), 400
    
    if 'file' not in request.files:
        return jsonify({'error':  'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # ✅ เพิ่มการตรวจสอบนามสกุลไฟล์
    allowed_extensions = {'.xlsx', '.xls'}
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions: 
        return jsonify({'error':  'Only Excel files (.xlsx, .xls) are allowed'}), 400
    
    try: 
        username = session['username']
        cntnum = request.form.get('cntnum', '').strip()
        if not cntnum:  
            return jsonify({'error': 'CNTNUM is required'}), 400
        
        # Read Excel file
        df = pd.read_excel(file, sheet_name='Sheet1')
        
        if df.empty:
            return jsonify({'error': 'Excel file is empty'}), 400
        
        if 'cntnum' not in df.columns: 
            return jsonify({'error':  'Excel file must have cntnum column'}), 400
        
        engine = get_sqlalchemy_engine()
        
        # Get unique CNTNUMs from the file
        cntnums = df['cntnum'].unique()
        
        df['username'] = username

        # Delete existing data for these CNTNUMs
        delete_query = text("DELETE FROM b2s_soh WHERE cntnum = :cntnum")
        
        with engine.connect() as conn:
            for cntnum in cntnums:
                conn. execute(delete_query, {'cntnum': cntnum})
            conn.commit()
        
        # Insert new data
        df. to_sql('b2s_soh', engine, if_exists='append', index=False)
        
        return jsonify({
            'success':  True,
            'message': f'อัพเดท SOH สำเร็จ {len(df)} รายการ',
            'count': len(df)
        })
        
    except Exception as e:
        print(f"Error updating SOH:  {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    
@app.route('/api/b2s/import_sale_pos', methods=['POST'])
def import_sale_pos():
    """Import Sale POS from Excel file"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    if 'cntnum' not in request.form:
        return jsonify({'error': 'CNTNUM is required in form data'}), 400
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # ✅ เพิ่มการตรวจสอบนามสกุลไฟล์
    allowed_extensions = {'.xlsx', '.xls'}
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        return jsonify({'error': 'Only Excel files (.xlsx, .xls) are allowed'}), 400
    
    try:
        username = session['username']
        cntnum = request.form.get('cntnum', '').strip()
        if not cntnum:
            return jsonify({'error': 'CNTNUM is required'}), 400
        
        # Read Excel file
        df = pd.read_excel(file, sheet_name='Sheet1')
        
        if df.empty:
            return jsonify({'error': 'Excel file is empty'}), 400
        
        engine = get_sqlalchemy_engine()
        
        df['username'] = username
        df['cntnum'] = cntnum

        # Delete existing data for this CNTNUM
        delete_query = text("DELETE FROM b2s_sale_pos WHERE cntnum = :cntnum")
        with engine.connect() as conn:
            conn.execute(delete_query, {'cntnum': cntnum})
            conn.commit()

        # Insert new data
        df.to_sql('b2s_sale_pos', engine, if_exists='append', index=False)
        
        return jsonify({
            'success': True,
            'message': f'อัพโหลด Sale POS สำเร็จ {len(df)} รายการ',
            'count': len(df)
        })
        
    except Exception as e:
        print(f"Error importing Sale POS: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload_countfiles/upload_cntfiles', methods=['POST'])
@login_required 
def upload_countfiles():

    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    files = request.files.getlist('file')
    if not files:
        return jsonify({'error': 'No file uploaded'}), 400

    allowed_extensions = {'.csv'}
    engine = get_sqlalchemy_engine()

    # ดึงข้อมูลเดิม
    df_old = pd.read_sql(text("""
        select distinct docnum, stocktakeid
        from cntfiles_this_year
    """), engine)

    dataframe_list = []
    file_count = 0

    for file in files:
        if file.filename == '':
            continue

        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in allowed_extensions:
            return jsonify({'error': f'Invalid file type: {file.filename}'}), 400

        try:
            df = pd.read_csv(file, dtype=str)
            df.columns = df.columns.str.lower()
            dataframe_list.append(df)
            file_count += 1
        except Exception as e:
            return jsonify({'error': f'{file.filename}: {str(e)}'}), 400

    if not dataframe_list:
        return jsonify({'error': 'No valid files'}), 400

    # รวมทุกไฟล์
    df = pd.concat(dataframe_list, ignore_index=True)

    # clean
    df['qnt'] = pd.to_numeric(df['qnt'], errors='coerce').fillna(0)

    # ตัดข้อมูลซ้ำ
    df = df.merge(
        df_old,
        on=['docnum', 'stocktakeid'],
        how='left',
        indicator=True
    )

    df_new = df[df['_merge'] == 'left_only'].drop(columns=['_merge'])
    # Extract duplicate records for reference (as requested in requirements)
    # Note: reusing df_old variable name as original is no longer needed after merge
    df_old = df[df['_merge'] == 'both'].drop_duplicates(subset=['docnum', 'stocktakeid'])

    if df_new.empty:
        return jsonify({'message': 'No new records to upload'}), 200

    df_new['username'] = session['username']

    try:
        df_new.to_sql(
            'cntfiles_this_year',
            engine,
            if_exists='append',
            index=False,
            method='multi'
        )

        return jsonify({
            'success': True,
            'message': 'อัปโหลดไฟล์สำเร็จ',
            'record_count': len(df_new),
            'docnum_uploaded': len(df_new['docnum'].unique()),
            'docnum_not_uploaded': df_new['docnum'].unique().tolist()
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    
@app.route('/api/upload_files_final/store_detail', methods=['POST'])
@login_required

def search_store_detail():
        
    bu = request.json.get('bu', '').strip()
    stcode = request.json.get('stcode', '').strip()
    atype = request.json.get('atype', '').strip()
    cntdate = request.json.get('cntdate', '').strip()

    cntdate_dt = pd.to_datetime(cntdate)
    cntdate_text = cntdate_dt.strftime('%Y%m%d')
    # Normalize atype: convert formats like "3F" -> "F"
    atype_1 = atype
    if len(atype_1) >= 2 and atype_1[0].isdigit():
        atype_1 = atype_1[1:]

    stocktakeid = f"{bu}{stcode}{atype_1[0]}{cntdate_text}001"


      
    try:
        engine = get_sqlalchemy_engine()
        
        # Query stocktakeid table
        query = text("""
            SELECT concat(bu,'-',stcode,'-',acronym,'-',branch,'-',cntdate,'-',shub,'-',type1,'-',size) as store_detail 
            FROM planall2
            WHERE bu =:bu AND stcode =:stcode AND cntdate =:cntdate_text and atype =:atype
        """)
        
        df = pd.read_sql(query, engine, params={'bu': bu, 'stcode': stcode, 'cntdate_text': cntdate_text, 'atype': atype})
        
        if df.empty:
            return jsonify({'error': 'ไม่พบข้อมูล ตาม Annual Plan ที่ระบุ'}), 404
        
        
        # Safely build result with defaults when any query returns empty
        store_detail = df.iloc[0]['store_detail'] if (not df.empty and 'store_detail' in df.columns) else ''

        result = {
            'store_detail': store_detail,
            'stocktakeid': stocktakeid
        }

        return jsonify(result)

    except Exception as e:
        print(f"Error searching StocktakeID: {e}")
        return jsonify({'error': str(e)}), 500

# upload file result final stocktake
chg_stk_columns = ['RESULT', 'DOCNAME', 'BUNAME', 'PRNDATE', 'CNTNUM', 'CNTNAME', 'STMERCH',
                'STNAME', 'POSTDATE', 'FREEZEDATE', 'CNTDATE', 'DEPTCODE', 'DEPTNAME', 'SUBDEPTCODE',
                'SUBDEPTNAME', 'SKU', 'SBC', 'IBC', 'BNDCODE', 'BNDNAME', 'PRNAME', 'PRMODEL',
                'SOH', 'CNTQNT', 'VARIANCEQNT', 'VARIANCEPERC', 'EXTPHYCNT_RETAIL',
                'EXTPHYCNT_COST', 'EXTPHY_RETAILVAR', 'EXTPHY_COSTVAR', 'EXTPHYCNT_RETAIL_EXVAT', 'GMPERC']

chg_stk_dtype_decimal_map = {
    'SOH': Decimal, 'CNTQNT': Decimal, 'VARIANCEQNT': Decimal, 'VARIANCEPERC': Decimal,
    'EXTPHYCNT_RETAIL': Decimal, 'EXTPHYCNT_COST': Decimal, 'EXTPHY_RETAILVAR': Decimal,
    'EXTPHY_COSTVAR': Decimal, 'EXTPHYCNT_RETAIL_EXVAT': Decimal, 'GMPERC': Decimal
}

chg_no_zero_count_columns = ['BUName', 'RepName', 'PrintDate', 'SKU', 'IBC', 'SBC', 'รายละเอียด', 'ยี่ห้อ',
                             'รุ่น', 'Cnt', 'Variance', 'Location', 'Total', 'Dept']
            
chg_no_zero_count_dtype_decimal_map = {'Cnt': Decimal, 'Variance': Decimal, 'Total': Decimal}

b2s_stk_columns = ['RESULT', 'DOCNAME', 'BUNAME', 'PRNDATE', 'CNTNUM', 'CNTNAME', 'STMERCH']
b2s_stk_dtype_decimal_map = {
    'SOH': Decimal, 'CNTQNT': Decimal, 'VARIANCEQNT': Decimal, 'VARIANCEPERC': Decimal,
    'EXTPHYCNT_RETAIL': Decimal, 'EXTPHYCNT_COST': Decimal, 'EXTPHY_RETAILVAR': Decimal,
    'EXTPHY_COSTVAR': Decimal, 'EXTPHYCNT_RETAIL_EXVAT': Decimal, 'GMPERC': Decimal
}

chg_var_columns = ['RESULT','DOCNAME','BUNAME','PRNDATE','CNTNUM','FREEZTSTT','ALLSKU','LOSSAMT1','LOSSAMT2',
                   'GAINAMT1','GAINAMT2','DEPTCODE','DEPTNAME','LOCATION','SKCODE','BARIBC','BARSBC1','BARSBC2',
                   'PRNAME','BNDCODE','BNDNAME','MODEL','COLOR','SOH','VARIANCE','CNTQNT','PRTYPE','BARIBCPRINT',
                   'BARLOCATION','BARCNTNUM']
chg_var_dtype_decimal_map = {
    'SOH': Decimal,
    'VARIANCE': Decimal,
    'CNTQNT': Decimal
}

b2s_var_columns = ['RESULT','DOCNAME','BUNAME','PRNDATE','CNTNUM','FREEZTSTT','ALLSKU','LOSSAMT1','LOSSAMT2',
                   'GAINAMT1','GAINAMT2','DEPTCODE','DEPTNAME','STORE','SKCODE','BARIBC','BARSBC1','BARSBC2',
                   'PRNAME','BNDCODE','BNDNAME','MODEL','COLOR','SOH','VARIANCE','CNTQNT','PRTYPE','BARIBCPRINT',
                   'BARSTORE','BARCNTNUM']

b2s_var_dtype_decimal_map = {
    'SOH': Decimal,
    'VARIANCE': Decimal,
    'CNTQNT': Decimal,
    'LOSSAMT1': Decimal,
    'LOSSAMT2': Decimal,
    'GAINAMT1': Decimal,
    'GAINAMT2': Decimal
}


@app.route('/api/upload_files_final/upload/<rpname>/<skutype>', methods=['POST'])   
@login_required
def upload_stk(rpname, skutype):
    """Upload STK from Excel file"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    engine = get_sqlalchemy_engine_pstdb3()

    file = request.files['file']

    '''
        elif request.form.get('rpname', '').strip() in ['VAR1', 'VAR2']:
        rpname = 'var'
    '''
    # =======================================Process STK upload==========================================
    if request.form.get('rpname', '').strip() in ['STK1', 'STK2']:
        rpname = 'stk'
        table_name = f"{request.form.get('bu', '').strip().lower()}_{rpname}_this_year"

        sql = text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = :table
        ORDER BY ordinal_position
        """)
        with engine.connect() as conn:
            db_columns = [row[0] for row in conn.execute(sql, {'table': table_name})]
        
        try:
            username = session['username']
            cntdate = request.form.get('cntdate', '').strip()
            cntdate_dt = pd.to_datetime(cntdate)
            cntdate_text = cntdate_dt.strftime('%Y%m%d')

            # Read Excel file
            df = pd.read_excel(file, sheet_name='Sheet1',dtype=str)

            # ตรวจสอบ columns ที่จำเป็น
            if request.form.get('bu', '').strip() == 'CHG':
                required_columns = chg_stk_columns
                dtype_map = chg_stk_dtype_decimal_map
            elif request.form.get('bu', '').strip() == 'B2S':
                required_columns = b2s_stk_columns
                dtype_map = b2s_stk_dtype_decimal_map
        
            missing_columns = [col for col in required_columns if col not in df.columns]

            if missing_columns:
                return jsonify({
                    'error': f'Excel file is missing required columns: {", ".join(missing_columns)}'
                }), 400
            
            df.columns = df.columns.str.lower()

            # Convert specified columns to Decimal
            for col, col_type in dtype_map.items():
                if col_type == Decimal:
                    # แปลง str → Decimal, remove comma, strip space, 3 ตำแหน่ง
                    df[col.lower()] = df[col.lower()].astype(str).str.replace(',', '').str.strip()
                    df[col.lower()] = df[col.lower()].replace('', '0')
                    df[col.lower()] = df[col.lower()].apply(lambda x: round(Decimal(x), 3))

            df['skutype'] = request.form.get('skutype', '').strip()
            df['rpname'] = request.form.get('rpname', '').strip()
            df['bu'] = request.form.get('bu', '').strip()
            df['stcode'] = request.form.get('stcode', '').strip()
            df['username'] = username
            df['stocktakeid'] = request.form.get('stocktakeid', '').strip()
            if 'cntdate' not in df.columns:
                df['cntdate'] = cntdate_text
            
            if request.form.get('bu', '').strip() == 'CHG':
                df = df[df['stmerch'].notna() & (df['stmerch'] == df['stcode'])].reset_index(drop=True)
            elif request.form.get('bu', '').strip() == 'B2S':
                df = df[df['store'].notna() & (df['stmerch'] == df['stcode'])].reset_index(drop=True)

            if df.empty:
                return jsonify({'error': 'Excel file is empty'}), 400
    
            # check old data
            check_query = text(f"""
                SELECT distinct stocktakeid
                FROM {table_name}
                where stcode = :stcode
                    and cntdate = :cntdate
                    and skutype = :skutype
                    and rpname = :rpname""")
            df_check = pd.read_sql(check_query, engine,
                                params={'stcode': request.form.get('stcode', '').strip(),
                                            'cntdate': cntdate_text,
                                            'skutype': request.form.get('skutype', '').strip(),
                                            'rpname': request.form.get('rpname', '').strip()})
            
            if not df_check.empty:
                # Delete existing data for these stocktakeids
                delete_query = text(f"""
                    DELETE FROM {table_name}
                    where stcode = :stcode
                        and cntdate = :cntdate
                        and skutype = :skutype
                        and rpname = :rpname""")
                with engine.connect() as conn:
                    conn.execute(delete_query, {'stcode': request.form.get('stcode', '').strip(),
                                                'cntdate': cntdate_text,
                                                'skutype': request.form.get('skutype', '').strip(),
                                                'rpname': request.form.get('rpname', '').strip()})
                    print('Deleted old STK data')
                    conn.commit()
            
            # Reorder columns to match database table
            df = df[[c for c in db_columns if c in df.columns]]

            # Add missing columns with None values
            for c in db_columns:
                if c not in df.columns:
                    df[c] = None
            
            # Ensure the DataFrame columns are in the same order as the database table
            df = df[db_columns]

            # Replace NaN with None for SQL insertion
            df = df.where(df.notnull(), None)
            
            buffer = io.StringIO()

            df.to_csv(buffer, index=False, header=False,
                    sep='|')
            buffer.seek(0)

            conn = engine.raw_connection()
            cur = conn.cursor()

            cur.copy_from(buffer, table_name, sep='|',columns=db_columns)

            conn.commit()
            cur.close()
            conn.close()

            if request.form.get('bu', '').strip() == 'CHG' and request.form.get('rpname', '').strip() == 'STK2':
                df['soh_amount_cost'] = df['extphycnt_cost'] - df['extphy_costvar']
                df['soh_amount_retail'] = df['extphycnt_retail'] - df['extphy_retailvar']
                df['dept'] = df['deptcode'] + ' ' + df['deptname']
                df['subdept'] = df['subdeptcode'] + ' ' + df['subdeptname']
            elif request.form.get('bu', '').strip() == 'B2S' and request.form.get('rpname', '').strip() == 'STK2':
                df['soh_amount_cost'] = df['extphycnt_retail_exvat'] - 0
                df['soh_amount_retail'] = df['extphycnt_retail'] - 0
            
            if request.form.get('rpname', '').strip() == 'STK2':
                with engine.begin() as conn:
                    # Update GMPERC to 0 where it is NULL
                    delete_old_stk_report = text(f"""
                        delete from stk_report
                        WHERE bu = :bu
                            AND stcode = :stcode
                            AND cntdate = :cntdate
                            AND skutype = :skutype
                            AND rpname = :rpname
                    """)

                    delete_old_stk_report_subdept = text(f"""
                        delete from stk_report_subdept
                        WHERE bu = :bu
                            AND stcode = :stcode
                            AND cntdate = :cntdate
                            AND skutype = :skutype
                            AND rpname = :rpname
                    """)

                    params = {
                        'bu': request.form.get('bu', '').strip(),
                        'stcode': request.form.get('stcode', '').strip(),
                        'cntdate': cntdate_text,
                        'skutype': request.form.get('skutype', '').strip(),
                        'rpname': request.form.get('rpname', '').strip()
                    }
                    conn.execute(delete_old_stk_report, params)
                    conn.execute(delete_old_stk_report_subdept, params)


                df_stocktake = df.groupby(['bu', 'stcode', 'cntdate', 'skutype', 'rpname'], as_index=False).agg(
                    sku=('sku', 'count'),
                    # นับจำนวน x:(condition)
                    sgain=('varianceqnt',lambda x: (x > 0).sum()),
                    sloss=('varianceqnt', lambda x: (x < 0).sum()),
                    psoh=('soh', 'sum'),
                    pqty=('cntqnt', 'sum'),
                    # รวมจำนวนมูลค่า ต้องมีค่า X: x[condition]
                    pgain=('varianceqnt', lambda x: x[x > 0].sum()),
                    ploss=('varianceqnt', lambda x: x[x < 0].sum()),
                    vrsoh=('soh_amount_retail', 'sum'),
                    vsoh=('soh_amount_cost', 'sum'),
                    vrqty=('extphycnt_retail', 'sum'),
                    vqty=('extphycnt_cost', 'sum'),
                    vrgain=('extphy_retailvar', lambda x: x[x > 0].sum()),
                    vgain=('extphy_costvar', lambda x: x[x > 0].sum()),
                    vrloss=('extphy_retailvar', lambda x: x[x < 0].sum()),
                    vloss=('extphy_costvar', lambda x: x[x < 0].sum()))
                
                df_stocktake.to_sql('stk_report', engine, if_exists='append', index=False)

                # summary by dept and subdept
                df_subdept = df.groupby(['bu', 'stcode', 'cntdate', 'skutype', 'rpname','dept','subdept'], as_index=False).agg(
                    sku=('sku', 'count'),
                    # นับจำนวน x:(condition)
                    sgain=('varianceqnt',lambda x: (x > 0).sum()),
                    sloss=('varianceqnt', lambda x: (x < 0).sum()),
                    psoh=('soh', 'sum'),
                    pqty=('cntqnt', 'sum'),
                    # รวมจำนวนมูลค่า ต้องมีค่า X: x[condition]
                    pgain=('varianceqnt', lambda x: x[x > 0].sum()),
                    ploss=('varianceqnt', lambda x: x[x < 0].sum()),
                    vrsoh=('soh_amount_retail', 'sum'),
                    vsoh=('soh_amount_cost', 'sum'),
                    vrqty=('extphycnt_retail', 'sum'),
                    vqty=('extphycnt_cost', 'sum'),
                    vrgain=('extphy_retailvar', lambda x: x[x > 0].sum()),
                    vgain=('extphy_costvar', lambda x: x[x > 0].sum()),
                    vrloss=('extphy_retailvar', lambda x: x[x < 0].sum()),
                    vloss=('extphy_costvar', lambda x: x[x < 0].sum()))
                df_subdept.to_sql('stk_report_subdept', engine, if_exists='append', index=False)
                
            return jsonify({
                'success':  True,
                'message':  f'อัพโหลด stocktakeid: {request.form.get("stocktakeid", "").strip()}'
                            f'สำเร็จ จำนวน {len(df):,} รายการ'
            })
        except Exception as e:
            return jsonify({'error': f'Internal server error: {str(e)}'}), 500
        
    elif request.form.get('rpname', '').strip() in ['VAR1', 'VAR2']:
        rpname = 'var'
        table_name = f"{request.form.get('bu', '').strip().lower()}_{rpname}_this_year"
        sql = text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = :table
            ORDER BY ordinal_position
        """)
        with engine.connect() as conn:
            db_columns = [row[0] for row in conn.execute(sql, {'table': table_name})]
            username = session['username']
            cntdate = request.form.get('cntdate', '').strip()
            cntdate_dt = pd.to_datetime(cntdate)
            cntdate_text = cntdate_dt.strftime('%Y%m%d')
        # Read Excel file
        df = pd.read_excel(file, sheet_name='Sheet1',dtype=str)

        # ตรวจสอบ columns ที่จำเป็น
        if request.form.get('bu', '').strip() == 'CHG':
            required_columns = chg_var_columns
            dtype_map = chg_var_dtype_decimal_map
        elif request.form.get('bu', '').strip() == 'B2S':
            required_columns = b2s_var_columns
            dtype_map = b2s_var_dtype_decimal_map
    
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            return jsonify({
                'error': f'Excel file is missing required columns: {", ".join(missing_columns)}'
            }), 400
        
        df.columns = df.columns.str.lower()
        
        # Convert specified columns to Decimal
        for col, col_type in dtype_map.items():
            col_name = col.lower()
            if col_type == Decimal:
                # แปลง str → Decimal, remove comma, strip space, 3 ตำแหน่ง
                df[col_name] = pd.to_numeric(df[col_name].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
                df[col_name] = df[col_name].apply(lambda x: round(Decimal(str(x)), 3))

        df['skutype'] = request.form.get('skutype', '').strip()
        df['rpname'] = request.form.get('rpname', '').strip()
        df['bu'] = request.form.get('bu', '').strip()
        df['stcode'] = request.form.get('stcode', '').strip()
        df['username'] = username
        df['stocktakeid'] = request.form.get('stocktakeid', '').strip()
        if 'cntdate' not in df.columns:
            df['cntdate'] = cntdate_text

    
        if request.form.get('bu', '').strip() == 'CHG':
            df = df[df['cntnum'].str[:5] == df['stcode'].values]

        elif request.form.get('bu', '').strip() == 'B2S':
            df = df[df['store'] == df['stcode'].values]

        if df.empty:
            return jsonify({'error': 'Excel file is empty'}), 400

        # check old data
        check_query = text(f"""
            SELECT distinct stocktakeid
            FROM {table_name}
            where stcode = :stcode
                and cntdate = :cntdate
                and skutype = :skutype
                and rpname = :rpname""")
        df_check = pd.read_sql(check_query, engine,
                            params={'stcode': request.form.get('stcode', '').strip(),
                                        'cntdate': cntdate_text,
                                        'skutype': request.form.get('skutype', '').strip(),
                                        'rpname': request.form.get('rpname', '').strip()})

        if not df_check.empty:
            # Delete existing data for these stocktakeids
            delete_query = text(f"""
                DELETE FROM {table_name}
                where stcode = :stcode
                    and cntdate = :cntdate
                    and skutype = :skutype
                    and rpname = :rpname""")
            with engine.connect() as conn:
                conn.execute(delete_query, {'stcode': request.form.get('stcode', '').strip(),
                                            'cntdate': cntdate_text,
                                            'skutype': request.form.get('skutype', '').strip(),
                                            'rpname': request.form.get('rpname', '').strip()})
                print('Deleted old STK data')
                conn.commit()
                
        # Reorder columns to match database table
        df = df[[c for c in db_columns if c in df.columns]]

        # Add missing columns with None values
        for c in db_columns:
            if c not in df.columns:
                df[c] = None

        # Ensure the DataFrame columns are in the same order as the database table
        df = df[db_columns]

        # Replace NaN with None for SQL insertion
        df = df.where(df.notnull(), None)

        buffer = io.StringIO()

        df.to_csv(buffer, index=False, header=False,
                sep='|')
        buffer.seek(0)

        conn = engine.raw_connection()
        cur = conn.cursor()

        cur.copy_from(buffer, table_name, sep='|',columns=db_columns)

        conn.commit()
        cur.close()
        conn.close()
                    
        return jsonify({
            'success':  True,
            'message':  f'อัพโหลด stocktakeid: {request.form.get("stocktakeid", "").strip()}'
                        f'สำเร็จ จำนวน {len(df):,} รายการ'
        })
    elif request.form.get('rpname', '').strip() in ['NOC2','ZEC2']:
        if request.form.get('rpname', '').strip() == 'NOC2':
            rpname = 'nocount'
        else:
            rpname = 'zerocount'

        table_name = f"{request.form.get('bu', '').strip().lower()}_{rpname}_this_year"

        sql = text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = :table
        ORDER BY ordinal_position
        """)
        with engine.connect() as conn:
            db_columns = [row[0] for row in conn.execute(sql, {'table': table_name})]
        
        try:
            username = session['username']
            cntdate = request.form.get('cntdate', '').strip()
            cntdate_dt = pd.to_datetime(cntdate)
            cntdate_text = cntdate_dt.strftime('%Y%m%d')

            # Read Excel file
            df = pd.read_excel(file, sheet_name='Sheet1',dtype=str)

            # ตรวจสอบ columns ที่จำเป็น
            required_columns = chg_no_zero_count_columns
            dtype_map = chg_no_zero_count_dtype_decimal_map
        
            missing_columns = [col for col in required_columns if col not in df.columns]

            if missing_columns:
                return jsonify({
                    'error': f'Excel file is missing required columns: {", ".join(missing_columns)}'
                }), 400
            
            df.columns = df.columns.str.lower()
            
            # Convert specified columns to Decimal
            for col, col_type in dtype_map.items():
                if col_type == Decimal:
                    # แปลง str → Decimal, remove comma, strip space, 3 ตำแหน่ง
                    df[col.lower()] = df[col.lower()].astype(str).str.replace(',', '').str.strip()
                    df[col.lower()] = df[col.lower()].replace('', '0')
                    df[col.lower()] = df[col.lower()].apply(lambda x: round(Decimal(x), 3))

            df['skutype'] = request.form.get('skutype', '').strip()
            df['rpname'] = request.form.get('rpname', '').strip()
            df['bu'] = request.form.get('bu', '').strip()
            df['stcode'] = request.form.get('stcode', '').strip()
            df['username'] = username
            df['stocktakeid'] = request.form.get('stocktakeid', '').strip()
            if 'cntdate' not in df.columns:
                df['cntdate'] = cntdate_text
            df['prname'] = df['รายละเอียด']
            df['bndname'] = df['ยี่ห้อ']
            df['model'] = df['รุ่น']

            df.drop(columns=['รายละเอียด', 'ยี่ห้อ', 'รุ่น'], inplace=True)

            if df.empty:
                return jsonify({'error': 'Excel file is empty'}), 400

            # check old data
            check_query = text(f"""
                SELECT distinct stocktakeid
                FROM {table_name}
                where stcode = :stcode
                    and cntdate = :cntdate
                    and skutype = :skutype
                    and rpname = :rpname""")
            df_check = pd.read_sql(check_query, engine,
                                params={'stcode': request.form.get('stcode', '').strip(),
                                            'cntdate': cntdate_text,
                                            'skutype': request.form.get('skutype', '').strip(),
                                            'rpname': request.form.get('rpname', '').strip()})

            if not df_check.empty:
                # Delete existing data for these stocktakeids
                delete_query = text(f"""
                    DELETE FROM {table_name}
                    where stcode = :stcode
                        and cntdate = :cntdate
                        and skutype = :skutype
                        and rpname = :rpname""")
                with engine.connect() as conn:
                    conn.execute(delete_query, {'stcode': request.form.get('stcode', '').strip(),
                                                'cntdate': cntdate_text,
                                                'skutype': request.form.get('skutype', '').strip(),
                                                'rpname': request.form.get('rpname', '').strip()})
                    print('Deleted old STK data')
                    conn.commit()
            
            # Reorder columns to match database table
            df = df[[c for c in db_columns if c in df.columns]]

            # Add missing columns with None values
            for c in db_columns:
                if c not in df.columns:
                    df[c] = None

            # Ensure the DataFrame columns are in the same order as the database table
            df = df[db_columns]

            # Replace NaN with None for SQL insertion
            df = df.where(df.notnull(), None)

            buffer = io.StringIO()

            df.to_csv(buffer, index=False, header=False,
                    sep='|')
            buffer.seek(0)

            conn = engine.raw_connection()
            cur = conn.cursor()

            cur.copy_from(buffer, table_name, sep='|',columns=db_columns)

            conn.commit()
            cur.close()
            conn.close()
            return jsonify({
                'success':  True,
                'message':  f'อัพโหลด stocktakeid: {request.form.get("stocktakeid", "").strip()}'
                            f'สำเร็จ จำนวน {len(df):,} รายการ'
            })
        except Exception as e:
            return jsonify({'error': f'Internal server error: {str(e)}'}), 500
 


    
@app.route('/api/upload_files_final/no_count', methods=['POST'])
@login_required


# ✅ เพิ่ม Error Handlers
@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({'error': 'File size exceeds 16MB limit'}), 413

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Resource not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__': 
    # Debug mode should only be enabled in development
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    app.run(debug=debug_mode, host='0.0.0.0', port=5000)