"""
Regalia Hotel - Luxury Hotel Booking & Management System
Main Flask Application
"""
import os
import uuid
import json
from datetime import datetime, timedelta, date
from decimal import Decimal, ROUND_HALF_UP
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for, 
    session, flash, jsonify, abort
)
from flask_session import Session
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import database
from models.database import db

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
app.config['SESSION_FILE_DIR'] = os.path.join(os.path.dirname(__file__), '.flask_session')

# Initialize extensions
Session(app)
CSRFProtect(app)

# Initialize database - auto-detect MySQL or SQLite
if os.getenv('DB_PASSWORD'):
    # Use MySQL when DB_PASSWORD is set in .env
    try:
        from config import Config
        db.init_mysql(Config.get_mysql_config())
        print("")
        print("=" * 55)
        print("  [OK] Connected to MySQL database: regalia_hotel")
        print("=" * 55)
        print("")
    except Exception as e:
        print(f"[ERROR] MySQL connection failed: {e}")
        print("[INFO] Falling back to SQLite...")
        db.init_db()
        from utils.seed import seed_all
        seed_all()
else:
    # Fallback to SQLite for development
    db.init_db()
    from utils.seed import seed_all
    seed_all()
    print("")
    print("=" * 55)
    print("  [OK] Using SQLite database (development mode)")
    print("  [TIP] Set DB_PASSWORD in .env to use MySQL")
    print("=" * 55)
    print("")

# Auto-create default admin and staff users if they don't exist
def ensure_default_users():
    """Create admin and staff users if they don't exist in the database"""
    default_users = [
        ('admin@regaliahotel.com', 'Admin@2024', 'admin', 'Hotel Administrator', '+91 33 1234 5678'),
        ('staff@regaliahotel.com', 'Staff@2024', 'staff', 'Front Desk Manager', '+91 33 2345 6789'),
    ]
    
    for email, password, role_name, name, phone in default_users:
        existing = db.execute("SELECT id FROM users WHERE email = %s", (email,), fetch_one=True)
        if not existing:
            role = db.execute("SELECT id FROM roles WHERE name = %s", (role_name,), fetch_one=True)
            if role:
                db.execute(
                    "INSERT INTO users (email, password_hash, role_id, full_name, phone) VALUES (%s, %s, %s, %s, %s)",
                    (email, generate_password_hash(password), role['id'], name, phone)
                )
                print(f"  [OK] Created {role_name} user: {email}")
            else:
                print(f"  [WARN] Role '{role_name}' not found - skipping {email}")
        else:
            # Verify the existing password works, if not update it
            user = db.execute(
                "SELECT id, password_hash FROM users WHERE email = %s",
                (email,), fetch_one=True
            )
            if user:
                try:
                    if not check_password_hash(user['password_hash'], password):
                        db.execute(
                            "UPDATE users SET password_hash = %s WHERE email = %s",
                            (generate_password_hash(password), email)
                        )
                        print(f"  [OK] Updated password for: {email}")
                except (ValueError, Exception):
                    # Hash is corrupt (e.g., leading space), fix it
                    db.execute(
                        "UPDATE users SET password_hash = %s WHERE email = %s",
                        (generate_password_hash(password), email)
                    )
                    print(f"  [OK] Fixed corrupted password for: {email}")

ensure_default_users()

# ==================== UTILITY FUNCTIONS ====================

def get_setting(key, default=None):
    """Get hotel setting value"""
    result = db.execute(
        "SELECT setting_value FROM hotel_settings WHERE setting_key = %s",
        (key,), fetch_one=True
    )
    return result['setting_value'] if result else default

def format_currency(amount):
    """Format amount as INR"""
    symbol = get_setting('currency_symbol', '₹')
    try:
        amount = float(amount)
        return f"{symbol}{amount:,.2f}"
    except (ValueError, TypeError):
        return f"{symbol}0.00"

def generate_booking_ref():
    """Generate unique booking reference"""
    return f"RG{datetime.now().strftime('%Y%m%d')}{uuid.uuid4().hex[:6].upper()}"

def generate_invoice_number():
    """Generate unique invoice number"""
    return f"INV-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

def log_audit(user_id, action, entity_type=None, entity_id=None, details=None):
    """Write audit log entry"""
    try:
        db.execute(
            """INSERT INTO audit_logs (user_id, action, entity_type, entity_id, details, ip_address) 
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (user_id, action, entity_type, entity_id, details, request.remote_addr)
        )
    except Exception as e:
        app.logger.error(f"Audit log error: {e}")

def calculate_nights(check_in, check_out):
    """Calculate number of nights"""
    if isinstance(check_in, str):
        check_in = datetime.strptime(check_in, '%Y-%m-%d').date()
    if isinstance(check_out, str):
        check_out = datetime.strptime(check_out, '%Y-%m-%d').date()
    return (check_out - check_in).days

def calculate_booking_totals(nightly_rate, num_nights, tax_rate, discount=0, additional_charges=0):
    """Calculate booking totals - server-side only"""
    nightly_rate = Decimal(str(nightly_rate))
    num_nights = int(num_nights)
    tax_rate = Decimal(str(tax_rate))
    discount = Decimal(str(discount))
    additional_charges = Decimal(str(additional_charges))
    
    subtotal = nightly_rate * num_nights
    tax_amount = (subtotal * tax_rate / 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    total = subtotal + tax_amount - discount + additional_charges
    
    return {
        'subtotal': float(subtotal),
        'tax_amount': float(tax_amount),
        'discount': float(discount),
        'additional_charges': float(additional_charges),
        'total': float(total)
    }

# ==================== AUTHENTICATION DECORATORS ====================

def login_required(f):
    """Require user to be logged in"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('signin'))
        # Check session timeout
        last_activity = session.get('last_activity')
        if last_activity:
            timeout = int(get_setting('session_timeout_minutes', 30)) * 60
            if (datetime.now() - datetime.fromisoformat(last_activity)).total_seconds() > timeout:
                session.clear()
                flash('Session expired. Please log in again.', 'warning')
                return redirect(url_for('signin'))
        session['last_activity'] = datetime.now().isoformat()
        return f(*args, **kwargs)
    return decorated

def role_required(*roles):
    """Require specific role(s)"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('signin'))
            if session.get('role') not in roles:
                flash('Access denied. Insufficient permissions.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated
    return decorator

# ==================== TEMPLATE CONTEXT ====================

def format_date(value, fmt='%Y-%m-%d'):
    """Template filter to safely format dates (handles both datetime objects and strings)"""
    if value is None:
        return 'N/A'
    if isinstance(value, str):
        return value[:10]
    if hasattr(value, 'strftime'):
        return value.strftime(fmt)
    return str(value)

def format_datetime(value, fmt='%Y-%m-%d %H:%M'):
    """Template filter to safely format datetime (handles both datetime objects and strings)"""
    if value is None:
        return 'N/A'
    if isinstance(value, str):
        return value[:16]
    if hasattr(value, 'strftime'):
        return value.strftime(fmt)
    return str(value)

# Register template filters
app.jinja_env.filters['format_date'] = format_date
app.jinja_env.filters['format_datetime'] = format_datetime

@app.context_processor
def inject_globals():
    """Inject global variables into templates"""
    return {
        'hotel_name': get_setting('hotel_name', 'Regalia Hotel'),
        'hotel_address': get_setting('hotel_address', 'Royal Avenue, Kolkata'),
        'hotel_phone': get_setting('hotel_phone', '+91 33 1234 5678'),
        'hotel_email': get_setting('hotel_email', 'info@regaliahotel.com'),
        'currency_symbol': get_setting('currency_symbol', '₹'),
        'current_year': datetime.now().year,
        'now': datetime.now()
    }

# ==================== PUBLIC ROUTES ====================

@app.route('/')
def index():
    """Home page"""
    # Get featured rooms
    featured_rooms = db.execute(
        """SELECT r.*, rc.name as category_name 
           FROM rooms r 
           JOIN room_categories rc ON r.category_id = rc.id 
           WHERE r.is_active = 1 AND r.status = 'available' 
           ORDER BY r.nightly_rate DESC LIMIT 6""",
        fetch_all=True
    )
    return render_template('public/index.html', featured_rooms=featured_rooms)

@app.route('/about')
def about():
    """About page"""
    return render_template('public/about.html')

@app.route('/rooms')
def rooms():
    """Rooms listing page"""
    floor = request.args.get('floor')
    category = request.args.get('category')
    status = request.args.get('status')
    min_price = request.args.get('min_price')
    max_price = request.args.get('max_price')
    search = request.args.get('search')
    
    query = """SELECT r.*, rc.name as category_name 
               FROM rooms r 
               JOIN room_categories rc ON r.category_id = rc.id 
               WHERE r.is_active = 1"""
    params = []
    
    if floor:
        query += " AND r.floor = %s"
        params.append(int(floor))
    if category:
        query += " AND r.suite_category = %s"
        params.append(category)
    if status:
        query += " AND r.status = %s"
        params.append(status)
    if min_price:
        query += " AND r.nightly_rate >= %s"
        params.append(float(min_price))
    if max_price:
        query += " AND r.nightly_rate <= %s"
        params.append(float(max_price))
    if search:
        query += " AND (r.room_number LIKE %s OR r.description LIKE %s OR r.suite_category LIKE %s)"
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
    
    query += " ORDER BY r.floor, r.room_number"
    rooms_list = db.execute(query, params, fetch_all=True)
    
    categories = db.execute("SELECT DISTINCT name FROM room_categories ORDER BY name", fetch_all=True)
    
    return render_template('public/rooms.html', 
                         rooms=rooms_list, 
                         categories=categories,
                         filters={'floor': floor, 'category': category, 'status': status,
                                 'min_price': min_price, 'max_price': max_price, 'search': search})

@app.route('/room/<int:room_id>')
def room_detail(room_id):
    """Room detail page"""
    room = db.execute(
        """SELECT r.*, rc.name as category_name 
           FROM rooms r 
           JOIN room_categories rc ON r.category_id = rc.id 
           WHERE r.id = %s""",
        (room_id,), fetch_one=True
    )
    if not room:
        abort(404)
    return render_template('public/room_detail.html', room=room)

@app.route('/availability')
def availability():
    """Room availability search"""
    check_in = request.args.get('check_in')
    check_out = request.args.get('check_out')
    guests = request.args.get('guests', 1)
    category = request.args.get('category')
    
    available_rooms = []
    searched = False
    
    if check_in and check_out:
        searched = True
        try:
            ci = datetime.strptime(check_in, '%Y-%m-%d').date()
            co = datetime.strptime(check_out, '%Y-%m-%d').date()
            
            if ci < date.today():
                flash('Check-in date cannot be in the past.', 'danger')
                return render_template('public/availability.html', rooms=[], searched=True,
                                     check_in=check_in, check_out=check_out, guests=guests)
            
            if co <= ci:
                flash('Check-out date must be after check-in date.', 'danger')
                return render_template('public/availability.html', rooms=[], searched=True,
                                     check_in=check_in, check_out=check_out, guests=guests)
            
            # Find available rooms (not booked for the date range)
            query = """
                SELECT r.*, rc.name as category_name
                FROM rooms r
                JOIN room_categories rc ON r.category_id = rc.id
                WHERE r.is_active = 1
                AND r.status != 'maintenance'
                AND r.max_occupancy >= %s
                AND r.id NOT IN (
                    SELECT room_id FROM bookings 
                    WHERE status NOT IN ('cancelled', 'no_show', 'checked_out', 'completed')
                    AND check_in_date < %s AND check_out_date > %s
                )
            """
            params = [int(guests), co.isoformat(), ci.isoformat()]
            
            if category:
                query += " AND r.suite_category = %s"
                params.append(category)
            
            query += " ORDER BY r.nightly_rate"
            available_rooms = db.execute(query, params, fetch_all=True)
        except ValueError:
            flash('Invalid date format.', 'danger')
    
    categories = db.execute("SELECT DISTINCT name FROM room_categories ORDER BY name", fetch_all=True)
    
    return render_template('public/availability.html', 
                         rooms=available_rooms, searched=searched,
                         check_in=check_in, check_out=check_out, 
                         guests=guests, category=category,
                         categories=categories)

@app.route('/contact')
def contact():
    """Contact page"""
    return render_template('public/contact.html')

@app.route('/contact', methods=['POST'])
def contact_submit():
    """Handle contact form"""
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    subject = request.form.get('subject', '').strip()
    message = request.form.get('message', '').strip()
    
    if not all([name, email, subject, message]):
        flash('All fields are required.', 'danger')
        return redirect(url_for('contact'))
    
    # Log the contact message
    log_audit(None, 'CONTACT_FORM', 'contact', None, 
              json.dumps({'name': name, 'email': email, 'subject': subject, 'message': message}))
    
    flash('Thank you for your message. We will get back to you soon.', 'success')
    return redirect(url_for('contact'))

# ==================== POLICY PAGES ====================

@app.route('/privacy')
def privacy():
    return render_template('public/privacy.html')

@app.route('/terms')
def terms():
    return render_template('public/terms.html')

@app.route('/cancellation')
def cancellation():
    return render_template('public/cancellation.html')

@app.route('/faq')
def faq():
    return render_template('public/faq.html')

# ==================== AUTHENTICATION ROUTES ====================

@app.route('/signin')
def signin():
    """Sign in page with role selection"""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('auth/signin.html')

@app.route('/login/<role>')
def login_page(role):
    """Login page for specific role"""
    if role not in ['admin', 'staff', 'guest']:
        abort(404)
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('auth/login.html', role=role)

@app.route('/login/<role>', methods=['POST'])
def login_submit(role):
    """Process login"""
    if role not in ['admin', 'staff', 'guest']:
        abort(404)
    
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    
    if not email or not password:
        flash('Please enter both email and password.', 'danger')
        return redirect(url_for('login_page', role=role))
    
    # Find user
    user = db.execute(
        """SELECT u.*, r.name as role_name 
           FROM users u 
           JOIN roles r ON u.role_id = r.id 
           WHERE u.email = %s AND u.is_active = 1""",
        (email,), fetch_one=True
    )
    
    if not user:
        flash('Invalid email or password.', 'danger')
        log_audit(None, 'LOGIN_FAILED', 'user', None, f'Email: {email}, Role: {role}')
        return redirect(url_for('login_page', role=role))
    
    # Check role match
    if user['role_name'] != role:
        flash('This account is not registered as a ' + role + '. Please use the correct login category.', 'danger')
        return redirect(url_for('login_page', role=role))
    
    # Check lockout
    if user.get('locked_until'):
        locked_until = user['locked_until']
        if isinstance(locked_until, str):
            locked_until = datetime.fromisoformat(locked_until)
        if datetime.now() < locked_until:
            flash('Account is temporarily locked. Please try again later.', 'danger')
            return redirect(url_for('login_page', role=role))
    
    # Check password
    if not check_password_hash(user['password_hash'], password):
        # Increment failed attempts
        attempts = user.get('failed_login_attempts', 0) + 1
        max_attempts = int(get_setting('max_login_attempts', 5))
        lockout_minutes = int(get_setting('lockout_minutes', 15))
        
        if attempts >= max_attempts:
            lockout_until = (datetime.now() + timedelta(minutes=lockout_minutes)).isoformat()
            db.execute(
                "UPDATE users SET failed_login_attempts = %s, locked_until = %s WHERE id = %s",
                (attempts, lockout_until, user['id'])
            )
            flash(f'Too many failed attempts. Account locked for {lockout_minutes} minutes.', 'danger')
        else:
            db.execute(
                "UPDATE users SET failed_login_attempts = %s WHERE id = %s",
                (attempts, user['id'])
            )
            remaining = max_attempts - attempts
            flash(f'Invalid password. {remaining} attempts remaining.', 'danger')
        
        log_audit(user['id'], 'LOGIN_FAILED', 'user', user['id'], 'Wrong password')
        return redirect(url_for('login_page', role=role))
    
    # Successful login
    db.execute(
        "UPDATE users SET failed_login_attempts = 0, locked_until = NULL, last_login = %s WHERE id = %s",
        (datetime.now().isoformat(), user['id'])
    )
    
    session['user_id'] = user['id']
    session['user_email'] = user['email']
    session['user_name'] = user['full_name']
    session['role'] = user['role_name']
    session['last_activity'] = datetime.now().isoformat()
    
    # Create customer record for guests if not exists
    if role == 'guest':
        customer = db.execute(
            "SELECT id FROM customers WHERE user_id = %s",
            (user['id'],), fetch_one=True
        )
        if not customer:
            db.execute(
                """INSERT INTO customers (user_id, full_name, email, phone) 
                   VALUES (%s, %s, %s, %s)""",
                (user['id'], user['full_name'], user['email'], user.get('phone'))
            )
    
    log_audit(user['id'], 'LOGIN_SUCCESS', 'user', user['id'], f'Role: {role}')
    flash(f'Welcome back, {user["full_name"]}!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Guest registration"""
    if request.method == 'GET':
        return render_template('auth/register.html')
    
    # Process registration
    full_name = request.form.get('full_name', '').strip()
    email = request.form.get('email', '').strip().lower()
    phone = request.form.get('phone', '').strip()
    password = request.form.get('password', '')
    confirm_password = request.form.get('confirm_password', '')
    address = request.form.get('address', '').strip()
    country = request.form.get('country', 'India').strip()
    
    errors = []
    if not full_name or len(full_name) < 2:
        errors.append('Full name is required (minimum 2 characters).')
    if not email or '@' not in email:
        errors.append('Valid email address is required.')
    if not password or len(password) < 8:
        errors.append('Password must be at least 8 characters.')
    if password != confirm_password:
        errors.append('Passwords do not match.')
    
    # Check duplicate email
    existing = db.execute(
        "SELECT id FROM users WHERE email = %s",
        (email,), fetch_one=True
    )
    if existing:
        errors.append('An account with this email already exists.')
    
    if errors:
        for err in errors:
            flash(err, 'danger')
        return render_template('auth/register.html', 
                             form_data=request.form)
    
    # Create user
    guest_role = db.execute(
        "SELECT id FROM roles WHERE name = 'guest'",
        fetch_one=True
    )
    
    user_id = db.execute(
        """INSERT INTO users (email, password_hash, role_id, full_name, phone) 
           VALUES (%s, %s, %s, %s, %s)""",
        (email, generate_password_hash(password), guest_role['id'], full_name, phone)
    )
    
    # Create customer record
    db.execute(
        """INSERT INTO customers (user_id, full_name, email, phone, address, country) 
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (user_id, full_name, email, phone, address, country)
    )
    
    log_audit(user_id, 'REGISTER', 'user', user_id, f'New guest: {full_name}')
    
    flash('Registration successful! Please log in.', 'success')
    return redirect(url_for('login_page', role='guest'))

@app.route('/logout')
def logout():
    """Logout"""
    user_id = session.get('user_id')
    if user_id:
        log_audit(user_id, 'LOGOUT', 'user', user_id, None)
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('index'))

# ==================== DASHBOARD ROUTES ====================

@app.route('/dashboard')
@login_required
def dashboard():
    """Route to appropriate dashboard based on role"""
    role = session.get('role')
    if role == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif role == 'staff':
        return redirect(url_for('staff_dashboard'))
    else:
        return redirect(url_for('guest_dashboard'))

@app.route('/admin/dashboard')
@login_required
@role_required('admin')
def admin_dashboard():
    """Admin dashboard"""
    stats = {}
    
    # Room stats
    stats['total_rooms'] = db.execute("SELECT COUNT(*) as c FROM rooms WHERE is_active = 1", fetch_one=True)['c']
    stats['available_rooms'] = db.execute("SELECT COUNT(*) as c FROM rooms WHERE status = 'available' AND is_active = 1", fetch_one=True)['c']
    stats['occupied_rooms'] = db.execute("SELECT COUNT(*) as c FROM rooms WHERE status = 'occupied' AND is_active = 1", fetch_one=True)['c']
    stats['reserved_rooms'] = db.execute("SELECT COUNT(*) as c FROM rooms WHERE status = 'reserved' AND is_active = 1", fetch_one=True)['c']
    stats['maintenance_rooms'] = db.execute("SELECT COUNT(*) as c FROM rooms WHERE status = 'maintenance' AND is_active = 1", fetch_one=True)['c']
    
    # Customer stats
    stats['total_customers'] = db.execute("SELECT COUNT(*) as c FROM customers WHERE status = 'active'", fetch_one=True)['c']
    
    # Booking stats
    stats['total_bookings'] = db.execute("SELECT COUNT(*) as c FROM bookings", fetch_one=True)['c']
    stats['pending_bookings'] = db.execute("SELECT COUNT(*) as c FROM bookings WHERE status = 'pending'", fetch_one=True)['c']
    stats['active_bookings'] = db.execute("SELECT COUNT(*) as c FROM bookings WHERE status IN ('confirmed', 'checked_in')", fetch_one=True)['c']
    
    # Revenue
    revenue = db.execute("SELECT COALESCE(SUM(total_amount), 0) as total FROM bookings WHERE status IN ('confirmed', 'checked_in', 'checked_out', 'completed')", fetch_one=True)
    stats['total_revenue'] = revenue['total']
    
    # Recent bookings
    recent_bookings = db.execute(
        """SELECT b.*, c.full_name as customer_name, r.room_number 
           FROM bookings b 
           JOIN customers c ON b.customer_id = c.id 
           JOIN rooms r ON b.room_id = r.id 
           ORDER BY b.created_at DESC LIMIT 10""",
        fetch_all=True
    )
    
    # Recent audit logs
    audit_logs = db.execute(
        """SELECT al.*, u.full_name as user_name 
           FROM audit_logs al 
           LEFT JOIN users u ON al.user_id = u.id 
           ORDER BY al.created_at DESC LIMIT 15""",
        fetch_all=True
    )
    
    return render_template('admin/dashboard.html', stats=stats, 
                         recent_bookings=recent_bookings, audit_logs=audit_logs)

@app.route('/staff/dashboard')
@login_required
@role_required('staff')
def staff_dashboard():
    """Staff dashboard"""
    today = date.today().isoformat()
    
    stats = {}
    stats['today_checkins'] = db.execute(
        "SELECT COUNT(*) as c FROM bookings WHERE check_in_date = %s AND status IN ('pending', 'confirmed')",
        (today,), fetch_one=True)['c']
    stats['today_checkouts'] = db.execute(
        "SELECT COUNT(*) as c FROM bookings WHERE check_out_date = %s AND status = 'checked_in'",
        (today,), fetch_one=True)['c']
    stats['available_rooms'] = db.execute("SELECT COUNT(*) as c FROM rooms WHERE status = 'available' AND is_active = 1", fetch_one=True)['c']
    stats['occupied_rooms'] = db.execute("SELECT COUNT(*) as c FROM rooms WHERE status = 'occupied' AND is_active = 1", fetch_one=True)['c']
    stats['pending_bookings'] = db.execute("SELECT COUNT(*) as c FROM bookings WHERE status = 'pending'", fetch_one=True)['c']
    
    recent_bookings = db.execute(
        """SELECT b.*, c.full_name as customer_name, r.room_number 
           FROM bookings b 
           JOIN customers c ON b.customer_id = c.id 
           JOIN rooms r ON b.room_id = r.id 
           ORDER BY b.created_at DESC LIMIT 10""",
        fetch_all=True
    )
    
    recent_customers = db.execute(
        "SELECT * FROM customers WHERE status = 'active' ORDER BY created_at DESC LIMIT 10",
        fetch_all=True
    )
    
    return render_template('staff/dashboard.html', stats=stats, 
                         recent_bookings=recent_bookings, recent_customers=recent_customers)

@app.route('/guest/dashboard')
@login_required
@role_required('guest')
def guest_dashboard():
    """Guest dashboard"""
    user_id = session['user_id']
    
    customer = db.execute(
        "SELECT * FROM customers WHERE user_id = %s",
        (user_id,), fetch_one=True
    )
    
    if not customer:
        flash('Customer profile not found. Please contact support.', 'danger')
        return redirect(url_for('index'))
    
    upcoming_bookings = db.execute(
        """SELECT b.*, r.room_number, r.suite_category, r.image_url 
           FROM bookings b 
           JOIN rooms r ON b.room_id = r.id 
           WHERE b.customer_id = %s AND b.status IN ('pending', 'confirmed') 
           AND b.check_out_date >= %s
           ORDER BY b.check_in_date ASC""",
        (customer['id'], date.today().isoformat()), fetch_all=True
    )
    
    past_bookings = db.execute(
        """SELECT b.*, r.room_number, r.suite_category, r.image_url 
           FROM bookings b 
           JOIN rooms r ON b.room_id = r.id 
           WHERE b.customer_id = %s AND (b.status IN ('checked_out', 'completed', 'cancelled', 'no_show') 
           OR b.check_out_date < %s)
           ORDER BY b.check_in_date DESC""",
        (customer['id'], date.today().isoformat()), fetch_all=True
    )
    
    return render_template('guest/dashboard.html', customer=customer,
                         upcoming_bookings=upcoming_bookings, past_bookings=past_bookings)

# ==================== CUSTOMER MANAGEMENT ====================

@app.route('/admin/customers')
@login_required
@role_required('admin', 'staff')
def customers_list():
    """List all customers"""
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '')
    
    query = "SELECT * FROM customers WHERE 1=1"
    params = []
    
    if search:
        query += " AND (full_name LIKE %s OR email LIKE %s OR phone LIKE %s)"
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
    if status_filter:
        query += " AND status = %s"
        params.append(status_filter)
    
    query += " ORDER BY created_at DESC"
    customers = db.execute(query, params, fetch_all=True)
    
    return render_template('admin/customers.html', customers=customers, 
                         search=search, status_filter=status_filter)

@app.route('/admin/customers/add', methods=['POST'])
@login_required
@role_required('admin', 'staff')
def customer_add():
    """Add new customer"""
    full_name = request.form.get('full_name', '').strip()
    email = request.form.get('email', '').strip().lower()
    phone = request.form.get('phone', '').strip()
    address = request.form.get('address', '').strip()
    country = request.form.get('country', 'India').strip()
    id_type = request.form.get('id_type', '').strip()
    id_number = request.form.get('id_number', '').strip()
    
    # Validation
    if not full_name or not email:
        flash('Full name and email are required.', 'danger')
        return redirect(url_for('customers_list'))
    
    if '@' not in email:
        flash('Please enter a valid email address.', 'danger')
        return redirect(url_for('customers_list'))
    
    # Check duplicate
    existing = db.execute(
        "SELECT id FROM customers WHERE email = %s",
        (email,), fetch_one=True
    )
    if existing:
        flash('A customer with this email already exists.', 'danger')
        return redirect(url_for('customers_list'))
    
    # Insert
    customer_id = db.execute(
        """INSERT INTO customers (full_name, email, phone, address, country, id_type, id_number) 
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (full_name, email, phone, address, country, id_type, id_number)
    )
    
    log_audit(session['user_id'], 'ADD', 'customer', customer_id, f'Added customer: {full_name}')
    flash(f'Customer "{full_name}" added successfully.', 'success')
    return redirect(url_for('customers_list'))

@app.route('/admin/customers/update/<int:customer_id>', methods=['POST'])
@login_required
@role_required('admin', 'staff')
def customer_update(customer_id):
    """Update customer"""
    customer = db.execute("SELECT * FROM customers WHERE id = %s", (customer_id,), fetch_one=True)
    if not customer:
        flash('Customer not found.', 'danger')
        return redirect(url_for('customers_list'))
    
    full_name = request.form.get('full_name', '').strip()
    email = request.form.get('email', '').strip().lower()
    phone = request.form.get('phone', '').strip()
    address = request.form.get('address', '').strip()
    country = request.form.get('country', 'India').strip()
    id_type = request.form.get('id_type', '').strip()
    id_number = request.form.get('id_number', '').strip()
    status = request.form.get('status', 'active').strip()
    
    if not full_name or not email:
        flash('Full name and email are required.', 'danger')
        return redirect(url_for('customers_list'))
    
    # Check duplicate email (excluding current customer)
    existing = db.execute(
        "SELECT id FROM customers WHERE email = %s AND id != %s",
        (email, customer_id), fetch_one=True
    )
    if existing:
        flash('Another customer with this email already exists.', 'danger')
        return redirect(url_for('customers_list'))
    
    db.execute(
        """UPDATE customers SET full_name=%s, email=%s, phone=%s, address=%s, 
           country=%s, id_type=%s, id_number=%s, status=%s, updated_at=%s 
           WHERE id=%s""",
        (full_name, email, phone, address, country, id_type, id_number, status,
         datetime.now().isoformat(), customer_id)
    )
    
    log_audit(session['user_id'], 'UPDATE', 'customer', customer_id, f'Updated customer: {full_name}')
    flash(f'Customer "{full_name}" updated successfully.', 'success')
    return redirect(url_for('customers_list'))

@app.route('/admin/customers/delete/<int:customer_id>', methods=['POST'])
@login_required
@role_required('admin', 'staff')
def customer_delete(customer_id):
    """Delete or deactivate customer"""
    customer = db.execute("SELECT * FROM customers WHERE id = %s", (customer_id,), fetch_one=True)
    if not customer:
        flash('Customer not found.', 'danger')
        return redirect(url_for('customers_list'))
    
    # Check for active bookings
    active_bookings = db.execute(
        "SELECT COUNT(*) as c FROM bookings WHERE customer_id = %s AND status IN ('pending', 'confirmed', 'checked_in')",
        (customer_id,), fetch_one=True
    )
    
    if active_bookings['c'] > 0:
        # Soft delete - set inactive
        db.execute(
            "UPDATE customers SET status = 'inactive', updated_at = %s WHERE id = %s",
            (datetime.now().isoformat(), customer_id)
        )
        log_audit(session['user_id'], 'DEACTIVATE', 'customer', customer_id, 
                 f'Deactivated customer: {customer["full_name"]} (has active bookings)')
        flash(f'Customer "{customer["full_name"]}" deactivated (has active bookings).', 'warning')
    else:
        # Check for any historical bookings
        any_bookings = db.execute(
            "SELECT COUNT(*) as c FROM bookings WHERE customer_id = %s",
            (customer_id,), fetch_one=True
        )
        
        if any_bookings['c'] > 0:
            # Soft delete to preserve booking history
            db.execute(
                "UPDATE customers SET status = 'inactive', updated_at = %s WHERE id = %s",
                (datetime.now().isoformat(), customer_id)
            )
            log_audit(session['user_id'], 'DEACTIVATE', 'customer', customer_id,
                     f'Deactivated customer: {customer["full_name"]} (has booking history)')
            flash(f'Customer "{customer["full_name"]}" deactivated (booking history preserved).', 'warning')
        else:
            # Safe to hard delete
            db.execute("DELETE FROM customers WHERE id = %s", (customer_id,))
            log_audit(session['user_id'], 'DELETE', 'customer', customer_id,
                     f'Deleted customer: {customer["full_name"]}')
            flash(f'Customer "{customer["full_name"]}" deleted successfully.', 'success')
    
    return redirect(url_for('customers_list'))

@app.route('/admin/customers/get/<int:customer_id>')
@login_required
@role_required('admin', 'staff')
def customer_get(customer_id):
    """Get customer details for editing"""
    customer = db.execute("SELECT * FROM customers WHERE id = %s", (customer_id,), fetch_one=True)
    if not customer:
        return jsonify({'error': 'Customer not found'}), 404
    return jsonify(customer)

# ==================== ROOM MANAGEMENT ====================

@app.route('/admin/rooms')
@login_required
@role_required('admin', 'staff')
def admin_rooms():
    """Room management page"""
    floor = request.args.get('floor')
    category = request.args.get('category')
    status = request.args.get('status')
    search = request.args.get('search')
    
    query = """SELECT r.*, rc.name as category_name 
               FROM rooms r 
               JOIN room_categories rc ON r.category_id = rc.id 
               WHERE r.is_active = 1"""
    params = []
    
    if floor:
        query += " AND r.floor = %s"
        params.append(int(floor))
    if category:
        query += " AND r.suite_category = %s"
        params.append(category)
    if status:
        query += " AND r.status = %s"
        params.append(status)
    if search:
        query += " AND (r.room_number LIKE %s OR r.suite_category LIKE %s)"
        params.extend([f'%{search}%', f'%{search}%'])
    
    query += " ORDER BY r.floor, r.room_number"
    rooms = db.execute(query, params, fetch_all=True)
    
    categories = db.execute("SELECT * FROM room_categories ORDER BY name", fetch_all=True)
    
    return render_template('admin/rooms.html', rooms=rooms, categories=categories,
                         filters={'floor': floor, 'category': category, 'status': status, 'search': search})

@app.route('/admin/rooms/update/<int:room_id>', methods=['POST'])
@login_required
@role_required('admin')
def room_update(room_id):
    """Update room details"""
    room = db.execute("SELECT * FROM rooms WHERE id = %s", (room_id,), fetch_one=True)
    if not room:
        flash('Room not found.', 'danger')
        return redirect(url_for('admin_rooms'))
    
    nightly_rate = request.form.get('nightly_rate')
    status = request.form.get('status')
    max_occupancy = request.form.get('max_occupancy')
    description = request.form.get('description', '').strip()
    amenities = request.form.get('amenities', '').strip()
    view_type = request.form.get('view_type', '').strip()
    bed_type = request.form.get('bed_type', '').strip()
    image_url = request.form.get('image_url', '').strip()
    
    # Validation
    try:
        nightly_rate = float(nightly_rate)
        if nightly_rate <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        flash('Invalid nightly rate.', 'danger')
        return redirect(url_for('admin_rooms'))
    
    try:
        max_occupancy = int(max_occupancy)
        if max_occupancy <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        flash('Invalid occupancy.', 'danger')
        return redirect(url_for('admin_rooms'))
    
    valid_statuses = ['available', 'occupied', 'reserved', 'dirty', 'maintenance']
    if status not in valid_statuses:
        flash('Invalid room status.', 'danger')
        return redirect(url_for('admin_rooms'))
    
    # Track status change
    if room['status'] != status:
        db.execute(
            """INSERT INTO room_status_history (room_id, old_status, new_status, changed_by, notes) 
               VALUES (%s, %s, %s, %s, %s)""",
            (room_id, room['status'], status, session['user_id'], f'Status changed via room management')
        )
    
    db.execute(
        """UPDATE rooms SET nightly_rate=%s, status=%s, max_occupancy=%s, description=%s, 
           amenities=%s, view_type=%s, bed_type=%s, image_url=%s, updated_at=%s 
           WHERE id=%s""",
        (nightly_rate, status, max_occupancy, description, amenities, view_type, bed_type, image_url,
         datetime.now().isoformat(), room_id)
    )
    
    log_audit(session['user_id'], 'UPDATE', 'room', room_id, f'Updated room {room["room_number"]}')
    flash(f'Room {room["room_number"]} updated successfully.', 'success')
    return redirect(url_for('admin_rooms'))

@app.route('/admin/rooms/status/<int:room_id>', methods=['POST'])
@login_required
@role_required('admin', 'staff')
def room_update_status(room_id):
    """Update room status only"""
    room = db.execute("SELECT * FROM rooms WHERE id = %s", (room_id,), fetch_one=True)
    if not room:
        return jsonify({'error': 'Room not found'}), 404
    
    new_status = request.form.get('status')
    valid_statuses = ['available', 'occupied', 'reserved', 'dirty', 'maintenance']
    
    if new_status not in valid_statuses:
        flash('Invalid status.', 'danger')
        return redirect(url_for('admin_rooms'))
    
    if room['status'] != new_status:
        db.execute(
            """INSERT INTO room_status_history (room_id, old_status, new_status, changed_by) 
               VALUES (%s, %s, %s, %s)""",
            (room_id, room['status'], new_status, session['user_id'])
        )
    
    db.execute(
        "UPDATE rooms SET status = %s, updated_at = %s WHERE id = %s",
        (new_status, datetime.now().isoformat(), room_id)
    )
    
    log_audit(session['user_id'], 'UPDATE_STATUS', 'room', room_id, 
             f'Room {room["room_number"]}: {room["status"]} → {new_status}')
    flash(f'Room {room["room_number"]} status updated to {new_status}.', 'success')
    return redirect(url_for('admin_rooms'))

@app.route('/admin/rooms/get/<int:room_id>')
@login_required
@role_required('admin', 'staff')
def room_get(room_id):
    """Get room details for editing"""
    room = db.execute("SELECT * FROM rooms WHERE id = %s", (room_id,), fetch_one=True)
    if not room:
        return jsonify({'error': 'Room not found'}), 404
    return jsonify(room)

# ==================== BOOKING MANAGEMENT ====================

@app.route('/book/<int:room_id>', methods=['GET', 'POST'])
@login_required
def book_room(room_id):
    """Book a room"""
    room = db.execute(
        """SELECT r.*, rc.name as category_name 
           FROM rooms r 
           JOIN room_categories rc ON r.category_id = rc.id 
           WHERE r.id = %s AND r.is_active = 1""",
        (room_id,), fetch_one=True
    )
    if not room:
        abort(404)
    
    # Get customer
    customer = db.execute(
        "SELECT * FROM customers WHERE user_id = %s",
        (session['user_id'],), fetch_one=True
    )
    if not customer:
        flash('Please complete your profile first.', 'warning')
        return redirect(url_for('guest_dashboard'))
    
    if request.method == 'GET':
        check_in = request.args.get('check_in', '')
        check_out = request.args.get('check_out', '')
        guests = request.args.get('guests', 1)
        return render_template('guest/book.html', room=room, customer=customer,
                             check_in=check_in, check_out=check_out, guests=guests)
    
    # Process booking
    check_in = request.form.get('check_in')
    check_out = request.form.get('check_out')
    num_guests = request.form.get('num_guests', 1)
    special_requests = request.form.get('special_requests', '').strip()
    
    errors = []
    
    if not check_in or not check_out:
        errors.append('Check-in and check-out dates are required.')
    
    try:
        ci_date = datetime.strptime(check_in, '%Y-%m-%d').date()
        co_date = datetime.strptime(check_out, '%Y-%m-%d').date()
    except ValueError:
        errors.append('Invalid date format.')
        ci_date = co_date = None
    
    if ci_date and co_date:
        if ci_date < date.today():
            errors.append('Check-in date cannot be in the past.')
        if co_date <= ci_date:
            errors.append('Check-out date must be after check-in date.')
    
    try:
        num_guests = int(num_guests)
        if num_guests < 1:
            errors.append('At least 1 guest is required.')
        if num_guests > room['max_occupancy']:
            errors.append(f'Maximum occupancy for this room is {room["max_occupancy"]} guests.')
    except ValueError:
        errors.append('Invalid number of guests.')
        num_guests = 1
    
    # Check room availability
    if room['status'] == 'maintenance':
        errors.append('This room is currently under maintenance.')
    
    # Check for overlapping bookings
    if ci_date and co_date:
        overlap = db.execute(
            """SELECT COUNT(*) as c FROM bookings 
               WHERE room_id = %s 
               AND status NOT IN ('cancelled', 'no_show', 'checked_out', 'completed')
               AND check_in_date < %s AND check_out_date > %s""",
            (room_id, co_date.isoformat(), ci_date.isoformat()), fetch_one=True
        )
        if overlap['c'] > 0:
            errors.append('This room is not available for the selected dates.')
    
    if errors:
        for err in errors:
            flash(err, 'danger')
        return render_template('guest/book.html', room=room, customer=customer,
                             check_in=check_in, check_out=check_out, guests=num_guests)
    
    # Calculate totals (server-side)
    num_nights = calculate_nights(ci_date, co_date)
    tax_rate = float(get_setting('tax_rate', 12))
    totals = calculate_booking_totals(room['nightly_rate'], num_nights, tax_rate)
    
    # Create booking
    booking_ref = generate_booking_ref()
    booking_id = db.execute(
        """INSERT INTO bookings (booking_ref, customer_id, room_id, check_in_date, check_out_date,
           num_guests, num_nights, nightly_rate, subtotal, tax_rate, tax_amount, total_amount,
           status, special_requests, booked_by)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s, %s)""",
        (booking_ref, customer['id'], room_id, ci_date.isoformat(), co_date.isoformat(),
         num_guests, num_nights, room['nightly_rate'], totals['subtotal'], tax_rate, 
         totals['tax_amount'], totals['total'], special_requests, session['user_id'])
    )
    
    # Update room status
    db.execute("UPDATE rooms SET status = 'reserved' WHERE id = %s AND status = 'available'", (room_id,))
    
    log_audit(session['user_id'], 'BOOKING_CREATE', 'booking', booking_id, 
             f'Booking {booking_ref} for room {room["room_number"]}')
    
    flash(f'Booking confirmed! Reference: {booking_ref}', 'success')
    return redirect(url_for('booking_confirmation', booking_ref=booking_ref))

@app.route('/booking/<booking_ref>')
@login_required
def booking_confirmation(booking_ref):
    """Booking confirmation page"""
    booking = db.execute(
        """SELECT b.*, c.full_name as customer_name, c.email as customer_email, c.phone as customer_phone,
           r.room_number, r.suite_category, r.image_url, r.view_type, r.bed_type, r.amenities
           FROM bookings b
           JOIN customers c ON b.customer_id = c.id
           JOIN rooms r ON b.room_id = r.id
           WHERE b.booking_ref = %s""",
        (booking_ref,), fetch_one=True
    )
    if not booking:
        abort(404)
    
    # Verify ownership or staff/admin access
    role = session.get('role')
    if role == 'guest':
        customer = db.execute(
            "SELECT id FROM customers WHERE user_id = %s",
            (session['user_id'],), fetch_one=True
        )
        if not customer or customer['id'] != booking['customer_id']:
            abort(403)
    
    return render_template('guest/booking_confirmation.html', booking=booking)

@app.route('/booking/<booking_ref>/cancel', methods=['POST'])
@login_required
def cancel_booking(booking_ref):
    """Cancel a booking"""
    booking = db.execute(
        "SELECT b.*, r.room_number FROM bookings b JOIN rooms r ON b.room_id = r.id WHERE b.booking_ref = %s",
        (booking_ref,), fetch_one=True
    )
    if not booking:
        abort(404)
    
    # Verify ownership or staff access
    role = session.get('role')
    if role == 'guest':
        customer = db.execute(
            "SELECT id FROM customers WHERE user_id = %s",
            (session['user_id'],), fetch_one=True
        )
        if not customer or customer['id'] != booking['customer_id']:
            abort(403)
    
    # Check if cancellation is allowed
    if booking['status'] not in ('pending', 'confirmed'):
        flash('This booking cannot be cancelled.', 'danger')
        return redirect(url_for('booking_confirmation', booking_ref=booking_ref))
    
    # Check cancellation window
    cancellation_hours = int(get_setting('cancellation_hours', 48))
    check_in = booking['check_in_date']
    if isinstance(check_in, str):
        check_in = datetime.strptime(check_in, '%Y-%m-%d').date()
    
    hours_until_checkin = (check_in - date.today()).days * 24
    reason = request.form.get('reason', 'Cancelled by user')
    
    db.execute(
        "UPDATE bookings SET status = 'cancelled', cancellation_reason = %s, updated_at = %s WHERE id = %s",
        (reason, datetime.now().isoformat(), booking['id'])
    )
    
    # Free up room
    db.execute("UPDATE rooms SET status = 'available' WHERE id = %s AND status = 'reserved'", 
              (booking['room_id'],))
    
    log_audit(session['user_id'], 'BOOKING_CANCEL', 'booking', booking['id'],
             f'Booking {booking_ref} cancelled. Reason: {reason}')
    
    if hours_until_checkin < cancellation_hours:
        flash(f'Booking cancelled. Note: Cancellation is within {cancellation_hours}-hour window. Refund may be subject to policy.', 'warning')
    else:
        flash('Booking cancelled successfully. Refund will be processed as per policy.', 'success')
    
    return redirect(url_for('dashboard'))

@app.route('/admin/bookings')
@login_required
@role_required('admin', 'staff')
def admin_bookings():
    """Booking management page"""
    status_filter = request.args.get('status', '')
    search = request.args.get('search', '').strip()
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    query = """SELECT b.*, c.full_name as customer_name, c.email as customer_email,
               r.room_number, r.suite_category
               FROM bookings b
               JOIN customers c ON b.customer_id = c.id
               JOIN rooms r ON b.room_id = r.id
               WHERE 1=1"""
    params = []
    
    if status_filter:
        query += " AND b.status = %s"
        params.append(status_filter)
    if search:
        query += " AND (b.booking_ref LIKE %s OR c.full_name LIKE %s OR r.room_number LIKE %s)"
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
    if date_from:
        query += " AND b.check_in_date >= %s"
        params.append(date_from)
    if date_to:
        query += " AND b.check_out_date <= %s"
        params.append(date_to)
    
    query += " ORDER BY b.created_at DESC"
    bookings = db.execute(query, params, fetch_all=True)
    
    return render_template('admin/bookings.html', bookings=bookings,
                         filters={'status': status_filter, 'search': search, 
                                 'date_from': date_from, 'date_to': date_to})

@app.route('/admin/bookings/<int:booking_id>/confirm', methods=['POST'])
@login_required
@role_required('admin', 'staff')
def confirm_booking(booking_id):
    """Confirm a booking"""
    booking = db.execute("SELECT * FROM bookings WHERE id = %s", (booking_id,), fetch_one=True)
    if not booking:
        flash('Booking not found.', 'danger')
        return redirect(url_for('admin_bookings'))
    
    if booking['status'] != 'pending':
        flash('Only pending bookings can be confirmed.', 'warning')
        return redirect(url_for('admin_bookings'))
    
    db.execute(
        "UPDATE bookings SET status = 'confirmed', updated_at = %s WHERE id = %s",
        (datetime.now().isoformat(), booking_id)
    )
    
    log_audit(session['user_id'], 'BOOKING_CONFIRM', 'booking', booking_id,
             f'Booking {booking["booking_ref"]} confirmed')
    flash(f'Booking {booking["booking_ref"]} confirmed.', 'success')
    return redirect(url_for('admin_bookings'))

@app.route('/admin/bookings/<int:booking_id>/checkin', methods=['POST'])
@login_required
@role_required('admin', 'staff')
def checkin_booking(booking_id):
    """Check in a booking"""
    booking = db.execute("SELECT * FROM bookings WHERE id = %s", (booking_id,), fetch_one=True)
    if not booking:
        flash('Booking not found.', 'danger')
        return redirect(url_for('admin_bookings'))
    
    if booking['status'] not in ('pending', 'confirmed'):
        flash('This booking cannot be checked in.', 'warning')
        return redirect(url_for('admin_bookings'))
    
    notes = request.form.get('notes', '')
    
    db.execute(
        """UPDATE bookings SET status = 'checked_in', checked_in_at = %s, checked_in_by = %s, 
           updated_at = %s WHERE id = %s""",
        (datetime.now().isoformat(), session['user_id'], datetime.now().isoformat(), booking_id)
    )
    
    # Update room status
    db.execute(
        "UPDATE rooms SET status = 'occupied', updated_at = %s WHERE id = %s",
        (datetime.now().isoformat(), booking['room_id'])
    )
    
    log_audit(session['user_id'], 'CHECK_IN', 'booking', booking_id,
             f'Guest checked in. Booking: {booking["booking_ref"]}. Notes: {notes}')
    flash(f'Guest checked in for booking {booking["booking_ref"]}.', 'success')
    return redirect(url_for('admin_bookings'))

@app.route('/admin/bookings/<int:booking_id>/checkout', methods=['POST'])
@login_required
@role_required('admin', 'staff')
def checkout_booking(booking_id):
    """Check out a booking"""
    booking = db.execute("SELECT * FROM bookings WHERE id = %s", (booking_id,), fetch_one=True)
    if not booking:
        flash('Booking not found.', 'danger')
        return redirect(url_for('admin_bookings'))
    
    if booking['status'] != 'checked_in':
        flash('Only checked-in bookings can be checked out.', 'warning')
        return redirect(url_for('admin_bookings'))
    
    additional_charges = float(request.form.get('additional_charges', 0))
    
    # Recalculate totals
    tax_rate = float(get_setting('tax_rate', 12))
    subtotal = booking['nightly_rate'] * booking['num_nights']
    tax_amount = round(subtotal * tax_rate / 100, 2)
    total = subtotal + tax_amount - booking['discount'] + additional_charges
    
    db.execute(
        """UPDATE bookings SET status = 'checked_out', checked_out_at = %s, checked_out_by = %s,
           additional_charges = %s, total_amount = %s, updated_at = %s WHERE id = %s""",
        (datetime.now().isoformat(), session['user_id'], additional_charges, total,
         datetime.now().isoformat(), booking_id)
    )
    
    # Update room status
    db.execute(
        "UPDATE rooms SET status = 'dirty', updated_at = %s WHERE id = %s",
        (datetime.now().isoformat(), booking['room_id'])
    )
    
    # Generate invoice
    invoice_number = generate_invoice_number()
    customer_id = booking['customer_id']
    
    invoice_id = db.execute(
        """INSERT INTO invoices (invoice_number, booking_id, customer_id, subtotal, tax_rate, 
           tax_amount, discount, additional_charges, total_amount, payment_status)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')""",
        (invoice_number, booking_id, customer_id, subtotal, tax_rate, tax_amount,
         booking['discount'], additional_charges, total)
    )
    
    # Add invoice items
    db.execute(
        """INSERT INTO invoice_items (invoice_id, description, quantity, unit_price, total) 
           VALUES (%s, %s, %s, %s, %s)""",
        (invoice_id, f'Room {booking["room_id"]} - {booking["num_nights"]} nights',
         booking['num_nights'], booking['nightly_rate'], subtotal)
    )
    
    if tax_amount > 0:
        db.execute(
            """INSERT INTO invoice_items (invoice_id, description, quantity, unit_price, total) 
               VALUES (%s, %s, 1, %s, %s)""",
            (invoice_id, f'GST @ {tax_rate}%', tax_amount, tax_amount)
        )
    
    if additional_charges > 0:
        db.execute(
            """INSERT INTO invoice_items (invoice_id, description, quantity, unit_price, total) 
               VALUES (%s, %s, 1, %s, %s)""",
            (invoice_id, 'Additional Charges', additional_charges, additional_charges)
        )
    
    log_audit(session['user_id'], 'CHECK_OUT', 'booking', booking_id,
             f'Guest checked out. Booking: {booking["booking_ref"]}. Invoice: {invoice_number}')
    flash(f'Guest checked out. Invoice {invoice_number} generated.', 'success')
    return redirect(url_for('admin_bookings'))

# ==================== INVOICES ====================

@app.route('/admin/invoices')
@login_required
@role_required('admin', 'staff')
def invoices_list():
    """List invoices"""
    invoices = db.execute(
        """SELECT i.*, b.booking_ref, c.full_name as customer_name, c.email as customer_email
           FROM invoices i
           JOIN bookings b ON i.booking_id = b.id
           JOIN customers c ON i.customer_id = c.id
           ORDER BY i.issued_at DESC""",
        fetch_all=True
    )
    return render_template('admin/invoices.html', invoices=invoices)

@app.route('/admin/invoices/<int:invoice_id>')
@login_required
@role_required('admin', 'staff')
def invoice_detail(invoice_id):
    """Invoice detail page"""
    invoice = db.execute(
        """SELECT i.*, b.booking_ref, b.check_in_date, b.check_out_date, b.num_nights,
           c.full_name as customer_name, c.email as customer_email, c.phone as customer_phone,
           c.address as customer_address, c.country as customer_country,
           r.room_number, r.suite_category
           FROM invoices i
           JOIN bookings b ON i.booking_id = b.id
           JOIN customers c ON i.customer_id = c.id
           JOIN rooms r ON b.room_id = r.id
           WHERE i.id = %s""",
        (invoice_id,), fetch_one=True
    )
    if not invoice:
        abort(404)
    
    items = db.execute(
        "SELECT * FROM invoice_items WHERE invoice_id = %s ORDER BY id",
        (invoice_id,), fetch_all=True
    )
    
    return render_template('admin/invoice_detail.html', invoice=invoice, items=items)

@app.route('/admin/invoices/<int:invoice_id>/mark-paid', methods=['POST'])
@login_required
@role_required('admin', 'staff')
def mark_invoice_paid(invoice_id):
    """Mark invoice as paid"""
    invoice = db.execute("SELECT * FROM invoices WHERE id = %s", (invoice_id,), fetch_one=True)
    if not invoice:
        flash('Invoice not found.', 'danger')
        return redirect(url_for('invoices_list'))
    
    method = request.form.get('method', 'cash')
    reference = request.form.get('reference', '')
    
    db.execute(
        "UPDATE invoices SET payment_status = 'paid', paid_at = %s WHERE id = %s",
        (datetime.now().isoformat(), invoice_id)
    )
    
    # Create payment record
    db.execute(
        """INSERT INTO payments (invoice_id, amount, method, status, reference, processed_by) 
           VALUES (%s, %s, %s, 'completed', %s, %s)""",
        (invoice_id, invoice['total_amount'], method, reference, session['user_id'])
    )
    
    # Update booking status
    db.execute(
        "UPDATE bookings SET status = 'completed', updated_at = %s WHERE id = %s",
        (datetime.now().isoformat(), invoice['booking_id'])
    )
    
    log_audit(session['user_id'], 'PAYMENT', 'invoice', invoice_id,
             f'Invoice {invoice["invoice_number"]} marked as paid via {method}')
    flash(f'Invoice {invoice["invoice_number"]} marked as paid.', 'success')
    return redirect(url_for('invoices_list'))

# ==================== SETTINGS ====================

@app.route('/admin/settings', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_settings():
    """Hotel settings"""
    if request.method == 'POST':
        settings = ['tax_rate', 'tax_type', 'gstin', 'check_in_time', 'check_out_time',
                    'cancellation_hours', 'session_timeout_minutes', 'hotel_phone', 'hotel_email']
        
        for key in settings:
            value = request.form.get(key, '').strip()
            if value:
                db.execute(
                    "UPDATE hotel_settings SET setting_value = %s WHERE setting_key = %s",
                    (value, key)
                )
        
        log_audit(session['user_id'], 'UPDATE', 'settings', None, 'Updated hotel settings')
        flash('Settings updated successfully.', 'success')
        return redirect(url_for('admin_settings'))
    
    settings = db.execute("SELECT * FROM hotel_settings ORDER BY setting_key", fetch_all=True)
    settings_dict = {s['setting_key']: s['setting_value'] for s in settings}
    return render_template('admin/settings.html', settings=settings_dict)

# ==================== AUDIT LOGS ====================

@app.route('/admin/audit-logs')
@login_required
@role_required('admin')
def audit_logs():
    """View audit logs"""
    action = request.args.get('action', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    query = """SELECT al.*, u.full_name as user_name, u.email as user_email
               FROM audit_logs al
               LEFT JOIN users u ON al.user_id = u.id
               WHERE 1=1"""
    params = []
    
    if action:
        query += " AND al.action = %s"
        params.append(action)
    if date_from:
        query += " AND al.created_at >= %s"
        params.append(date_from)
    if date_to:
        query += " AND al.created_at <= %s"
        params.append(date_to + ' 23:59:59')
    
    query += " ORDER BY al.created_at DESC LIMIT 200"
    logs = db.execute(query, params, fetch_all=True)
    
    return render_template('admin/audit_logs.html', logs=logs,
                         filters={'action': action, 'date_from': date_from, 'date_to': date_to})

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(e):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('errors/500.html'), 500

@app.errorhandler(403)
def forbidden(e):
    return render_template('errors/403.html'), 403

@app.route('/test-db')
def test_db_connection():
    """Test database connection - visit http://localhost:5000/test-db"""
    try:
        db_type = "MySQL" if db.use_mysql else "SQLite"
        room_count = db.execute("SELECT COUNT(*) as c FROM rooms", fetch_one=True)
        customer_count = db.execute("SELECT COUNT(*) as c FROM customers", fetch_one=True)
        booking_count = db.execute("SELECT COUNT(*) as c FROM bookings", fetch_one=True)
        category_count = db.execute("SELECT COUNT(*) as c FROM room_categories", fetch_one=True)
        setting_count = db.execute("SELECT COUNT(*) as c FROM hotel_settings", fetch_one=True)
        user_count = db.execute("SELECT COUNT(*) as c FROM users", fetch_one=True)
        
        return f"""
        <html>
        <head><title>Database Connection Test</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }}
            h2 {{ color: #1a1f3a; }}
            .status {{ background: #d4edda; color: #155724; padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
            th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
            th {{ background: #1a1f3a; color: white; }}
            tr:nth-child(even) {{ background: #f9f9f9; }}
            .db-type {{ font-size: 1.2em; font-weight: bold; color: #c9a96e; }}
        </style></head>
        <body>
            <h2>Regalia Hotel - Database Connection Test</h2>
            <div class="status">
                <strong>CONNECTED</strong> to <span class="db-type">{db_type}</span> database
            </div>
            <table>
                <tr><th>Table Name</th><th>Records</th><th>Status</th></tr>
                <tr><td>rooms</td><td>{room_count['c']}</td><td>{"OK" if room_count['c'] == 23 else "Check seed data"}</td></tr>
                <tr><td>room_categories</td><td>{category_count['c']}</td><td>{"OK" if category_count['c'] == 6 else "Check seed data"}</td></tr>
                <tr><td>customers</td><td>{customer_count['c']}</td><td>OK</td></tr>
                <tr><td>bookings</td><td>{booking_count['c']}</td><td>OK</td></tr>
                <tr><td>users</td><td>{user_count['c']}</td><td>OK</td></tr>
                <tr><td>hotel_settings</td><td>{setting_count['c']}</td><td>{"OK" if setting_count['c'] > 0 else "Check seed data"}</td></tr>
            </table>
            <p style="margin-top: 20px; color: #666;">
                <strong>Tip:</strong> Add a customer on the website, then refresh this page. 
                If the customer count increases, your website is connected to the database!
            </p>
        </body></html>
        """
    except Exception as e:
        return f"""
        <html><body style="font-family: Arial; max-width: 600px; margin: 50px auto;">
        <h2 style="color: red;">Database Error</h2>
        <p style="background: #f8d7da; color: #721c24; padding: 15px; border-radius: 8px;">
            {str(e)}
        </p>
        <p>Check your .env file and MySQL connection settings.</p>
        </body></html>
        """

# ==================== MAIN ====================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
