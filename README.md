# Regalia Hotel — Luxury Hotel Booking & Management System

A complete, fully functional luxury hotel booking and management web application built with Flask, MySQL/SQLite, and Bootstrap. Designed for Regalia Hotel, Kolkata, India.

![Python](https://img.shields.io/badge/Python-3.8+-blue)
![Flask](https://img.shields.io/badge/Flask-3.x-green)
![MySQL](https://img.shields.io/badge/MySQL-8.x-orange)
![License](https://img.shields.io/badge/License-Proprietary-red)

---

## Table of Contents

1. [Features](#features)
2. [Technology Stack](#technology-stack)
3. [Project Structure](#project-structure)
4. [Installation](#installation)
5. [Database Setup](#database-setup)
6. [Default Credentials](#default-credentials)
7. [User Roles & Permissions](#user-roles--permissions)
8. [Room Inventory](#room-inventory)
9. [Security Features](#security-features)
10. [Testing](#testing)
11. [Deployment](#deployment)
12. [Known Limitations](#known-limitations)

---

## Features

### Public Website
- ✅ Luxury responsive homepage with hero section, hotel logo, and banner
- ✅ About page with hotel amenities
- ✅ Rooms & Suites showcase with filtering (floor, category, price, search)
- ✅ Room detail pages with full descriptions
- ✅ Room availability search by date, guests, and category
- ✅ Contact page with form
- ✅ Privacy Policy, Terms & Conditions, Cancellation Policy, FAQ pages

### Authentication & Authorization
- ✅ Three separate login categories: Admin, Staff, Guest/Customer
- ✅ Guest registration with validation
- ✅ Role-based access control (enforced on backend)
- ✅ Session timeout management
- ✅ Account lockout after failed login attempts
- ✅ Show/hide password toggle
- ✅ Secure logout

### Customer Management (CRUD)
- ✅ **ADD** — Insert customer with validation and duplicate checking
- ✅ **UPDATE** — Modify customer details with audit trail
- ✅ **DELETE/DEACTIVATE** — Soft-delete for customers with booking history
- ✅ **RESET** — Clear form without database changes
- ✅ Search and filter customers

### Room Management
- ✅ View all 23 rooms across 5 floors
- ✅ Filter by floor, category, status
- ✅ Update room rates, status, amenities, descriptions
- ✅ Room status history tracking
- ✅ Status change: Available, Occupied, Reserved, Dirty, Maintenance

### Booking System
- ✅ Date-based availability search with overlap prevention
- ✅ Server-side total calculation (never trust client prices)
- ✅ Double-booking prevention
- ✅ Booking confirmation with unique reference
- ✅ Booking cancellation with policy enforcement
- ✅ Booking search and filtering

### Check-in / Check-out
- ✅ Guest check-in with staff recording
- ✅ Guest check-out with additional charges
- ✅ Automatic room status updates
- ✅ Invoice generation on checkout

### Billing & Invoicing
- ✅ Automatic invoice generation on checkout
- ✅ GST calculation (configurable)
- ✅ Payment status tracking
- ✅ Print-ready invoice layout
- ✅ Payment recording (manual workflow)

### Dashboards
- ✅ **Admin**: Full statistics, revenue, room stats, audit logs, quick actions
- ✅ **Staff**: Today's operations, check-ins/outs, pending bookings
- ✅ **Guest**: Profile, upcoming/past bookings, cancellation options

### Security
- ✅ CSRF protection on all forms
- ✅ Parameterized SQL queries (prevents injection)
- ✅ Password hashing (Werkzeug)
- ✅ Role-based route protection
- ✅ Input validation
- ✅ Output escaping (Jinja2)
- ✅ Audit logging for all actions
- ✅ Rate limiting on login attempts
- ✅ No hardcoded credentials

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.8+, Flask 3.x |
| Database | MySQL 8.x (production) / SQLite (development) |
| Frontend | HTML5, CSS3, JavaScript |
| UI Framework | Bootstrap 5.3 |
| Icons | Bootstrap Icons |
| Fonts | Cormorant Garamond + Montserrat (Google Fonts) |
| Session | Flask-Session (filesystem) |
| CSRF | Flask-WTF |
| Auth | Werkzeug (password hashing) |
| Config | python-dotenv |

---

## Project Structure

```
regalia-hotel/
├── app.py                  # Main Flask application
├── config.py               # Configuration settings
├── schema.sql              # MySQL schema (MySQL Workbench compatible)
├── seed_data.sql           # MySQL seed data
├── .env.example            # Environment variables template
├── README.md               # This file
├── models/
│   └── database.py         # Database abstraction layer
├── utils/
│   └── seed.py             # Database seeding (SQLite)
├── static/
│   ├── css/
│   │   └── style.css       # Custom luxury theme CSS
│   ├── js/
│   │   └── main.js         # Frontend JavaScript
│   └── images/
│       ├── hotel-banner.jpeg
│       ├── logos/
│       │   └── hotel-logo.jpeg
│       └── rooms/          # Room images directory
├── templates/
│   ├── base.html           # Base template with nav/footer
│   ├── auth/
│   │   ├── signin.html     # Sign-in role selection
│   │   ├── login.html      # Login form
│   │   └── register.html   # Guest registration
│   ├── public/
│   │   ├── index.html      # Homepage
│   │   ├── about.html      # About page
│   │   ├── rooms.html      # Rooms listing
│   │   ├── room_detail.html # Room detail
│   │   ├── availability.html # Availability search
│   │   ├── contact.html    # Contact page
│   │   ├── privacy.html    # Privacy policy
│   │   ├── terms.html      # Terms & conditions
│   │   ├── cancellation.html # Cancellation policy
│   │   └── faq.html        # FAQ
│   ├── admin/
│   │   ├── dashboard.html  # Admin dashboard
│   │   ├── customers.html  # Customer management
│   │   ├── rooms.html      # Room management
│   │   ├── bookings.html   # Booking management
│   │   ├── invoices.html   # Invoice list
│   │   ├── invoice_detail.html # Invoice detail/print
│   │   ├── settings.html   # Hotel settings
│   │   └── audit_logs.html # Audit logs
│   ├── staff/
│   │   └── dashboard.html  # Staff dashboard
│   ├── guest/
│   │   ├── dashboard.html  # Guest dashboard
│   │   ├── book.html       # Booking form
│   │   └── booking_confirmation.html # Confirmation
│   └── errors/
│       ├── 404.html        # Custom 404
│       ├── 403.html        # Custom 403
│       └── 500.html        # Custom 500
├── tests/                  # Test files
└── docs/                   # Documentation
```

---

## Installation

### Prerequisites
- Python 3.8 or higher
- MySQL 8.x (for production) or SQLite (built-in for development)
- pip (Python package manager)

### Quick Start (Development with SQLite)

```bash
# 1. Clone or extract the project
cd regalia-hotel

# 2. Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# 3. Install dependencies
pip install flask flask-wtf flask-session mysql-connector-python python-dotenv werkzeug bcrypt

# 4. Create .env file
cp .env.example .env
# Edit .env with your settings (SECRET_KEY at minimum)

# 5. Run the application
python app.py

# 6. Open browser
# Navigate to http://localhost:5000
```

### Production Setup (MySQL)

```bash
# 1. Install MySQL 8.x and create the database
mysql -u root -p < schema.sql
mysql -u root -p regalia_hotel < seed_data.sql

# 2. Configure .env
DB_HOST=localhost
DB_PORT=3306
DB_NAME=regalia_hotel
DB_USER=root
DB_PASSWORD=your_secure_password
SECRET_KEY=your-random-secret-key-generate-this

# 3. Run with production server
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

---

## Database Setup

### MySQL Workbench Setup

1. Open MySQL Workbench and connect to your local MySQL server
2. Go to **File → Open SQL Script** and open `schema.sql`
3. Execute the script to create the database and tables
4. Open and execute `seed_data.sql` to populate rooms and categories
5. Verify tables: `users`, `roles`, `customers`, `rooms`, `bookings`, `invoices`, etc.

### MySQL Workbench Verification

After running the application, verify data with:

```sql
USE regalia_hotel;

-- Check rooms
SELECT room_number, suite_category, nightly_rate, status FROM rooms ORDER BY room_number;

-- Check customers
SELECT * FROM customers ORDER BY created_at DESC;

-- Check bookings
SELECT b.booking_ref, c.full_name, r.room_number, b.status 
FROM bookings b 
JOIN customers c ON b.customer_id = c.id 
JOIN rooms r ON b.room_id = r.id;

-- Check audit logs
SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 20;
```

---

## Default Credentials

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@regaliahotel.com | Admin@2024 |
| Staff | staff@regaliahotel.com | Staff@2024 |
| Staff | manager@regaliahotel.com | Manager@2024 |

**⚠️ IMPORTANT:** Change all default passwords immediately in production!

### Creating a Guest Account
Visit `/register` to create a new guest account, or use the Sign In → Guest Login → Create Account flow.

---

## User Roles & Permissions

| Feature | Admin | Staff | Guest |
|---------|-------|-------|-------|
| View homepage/rooms | ✅ | ✅ | ✅ |
| Search availability | ✅ | ✅ | ✅ |
| Admin Dashboard | ✅ | ❌ | ❌ |
| Staff Dashboard | ✅ | ✅ | ❌ |
| Guest Dashboard | ❌ | ❌ | ✅ |
| Manage Customers | ✅ | ✅ | ❌ |
| Manage Rooms | ✅ | Status only | ❌ |
| Update Room Prices | ✅ | ❌ | ❌ |
| Manage Bookings | ✅ | ✅ | Own only |
| Check-in/Check-out | ✅ | ✅ | ❌ |
| Generate Invoices | ✅ | ✅ | ❌ |
| Mark Payments | ✅ | ✅ | ❌ |
| View Audit Logs | ✅ | ❌ | ❌ |
| Hotel Settings | ✅ | ❌ | ❌ |
| Cancel Booking | Any | Any | Own only |
| Make Booking | ✅ | ✅ | ✅ |

---

## Room Inventory

### Floor 1 — Classic Suites (5 rooms)
| Room | Category | Rate/Night | Occupancy |
|------|----------|-----------|-----------|
| 101 | Classic Suite | ₹8,500 | 2 |
| 102 | Classic Suite | ₹8,500 | 2 |
| 103 | Classic Suite | ₹9,000 | 2 |
| 104 | Classic Suite | ₹8,500 | 2 |
| 105 | Classic Suite | ₹8,500 | 2 |

### Floor 2 — Deluxe Suites (5 rooms)
| Room | Category | Rate/Night | Occupancy |
|------|----------|-----------|-----------|
| 201 | Deluxe Suite | ₹12,500 | 3 |
| 202 | Deluxe Suite | ₹12,500 | 3 |
| 203 | Deluxe Suite | ₹13,000 | 3 |
| 204 | Deluxe Suite | ₹12,500 | 3 |
| 205 | Deluxe Suite | ₹12,500 | 3 |

### Floor 3 — Premium & Executive Suites (5 rooms)
| Room | Category | Rate/Night | Occupancy |
|------|----------|-----------|-----------|
| 301 | Premium Suite | ₹16,000 | 3 |
| 302 | Premium Suite | ₹16,000 | 3 |
| 303 | Executive Suite | ₹18,500 | 3 |
| 304 | Executive Suite | ₹18,500 | 3 |
| 305 | Premium Suite | ₹16,500 | 3 |

### Floor 4 — Presidential & Royal Suites (4 rooms)
| Room | Category | Rate/Night | Occupancy |
|------|----------|-----------|-----------|
| 401 | Presidential Suite | ₹45,000 | 4 |
| 402 | Presidential Suite | ₹45,000 | 4 |
| 403 | Royal Suite | ₹28,000 | 4 |
| 404 | Royal Suite | ₹28,000 | 4 |

### Floor 5 — Ultra-Premium Royal Suites (3 rooms + 1 Grand Presidential)
| Room | Category | Rate/Night | Occupancy |
|------|----------|-----------|-----------|
| 501 | Royal Suite | ₹32,000 | 4 |
| 502 | Royal Suite | ₹30,000 | 4 |
| 503 | Presidential Suite | ₹50,000 | 6 |

**Total: 23 rooms across 5 floors**

---

## Security Features

### Implemented Security Controls
1. **Password Security** — Werkzeug's `generate_password_hash` (PBKDF2)
2. **CSRF Protection** — Flask-WTF CSRF tokens on all forms
3. **SQL Injection Prevention** — Parameterized queries only
4. **XSS Prevention** — Jinja2 auto-escaping
5. **Role-Based Access Control** — Decorators on all protected routes
6. **Session Management** — Configurable timeout, secure logout
7. **Login Rate Limiting** — Account lockout after 5 failed attempts
8. **Input Validation** — Server-side validation on all inputs
9. **Output Escaping** — All user content properly escaped
10. **Audit Logging** — All significant actions logged
11. **No Hardcoded Secrets** — Environment variables only
12. **IDOR Protection** — Ownership checks on bookings
13. **Price Manipulation Prevention** — Server-side calculations only
14. **Double Booking Prevention** — Database overlap checking

### Security Testing Checklist
- [ ] SQL injection attempts on all form inputs
- [ ] XSS attempts on all text fields
- [ ] CSRF token removal on forms
- [ ] Direct URL access to admin pages as guest
- [ ] Session hijacking attempts
- [ ] Price manipulation in booking forms
- [ ] IDOR on booking/customer IDs
- [ ] Brute force login attempts
- [ ] File upload abuse (if applicable)

---

## Testing

### Manual Testing Procedures

1. **Registration Test**: Visit `/register`, create account with valid data
2. **Login Tests**: Test all three login categories with default credentials
3. **Customer CRUD**: Add, update, delete customers in admin dashboard
4. **Room Search**: Filter rooms by floor, category, price
5. **Availability**: Search available rooms for various date ranges
6. **Booking**: Complete a full booking as a guest
7. **Cancellation**: Cancel a pending booking
8. **Check-in/Check-out**: Process guest through full stay cycle
9. **Invoice**: Verify invoice generation and payment marking
10. **Authorization**: Verify guests cannot access admin pages
11. **Responsive**: Test on mobile, tablet, desktop viewports

### Automated Testing

Create `tests/test_app.py`:

```python
import pytest
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_homepage(client):
    response = client.get('/')
    assert response.status_code == 200

def test_rooms_page(client):
    response = client.get('/rooms')
    assert response.status_code == 200

def test_signin_page(client):
    response = client.get('/signin')
    assert response.status_code == 200

def test_admin_redirect(client):
    response = client.get('/admin/dashboard')
    assert response.status_code == 302  # Redirect to login
```

---

## Deployment

### Production Deployment Checklist

- [ ] Change `SECRET_KEY` to a secure random value
- [ ] Change all default passwords
- [ ] Configure MySQL database
- [ ] Set `FLASK_ENV=production`
- [ ] Enable HTTPS (SSL/TLS certificate)
- [ ] Configure reverse proxy (Nginx/Apache)
- [ ] Set up application server (Gunicorn/uWSGI)
- [ ] Configure firewall rules
- [ ] Set up database backups
- [ ] Configure log rotation
- [ ] Verify GSTIN and tax settings
- [ ] Legal review of policies
- [ ] Performance testing

### Nginx Configuration Example

```nginx
server {
    listen 443 ssl;
    server_name regaliahotel.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Database Backup

```bash
# MySQL backup
mysqldump -u root -p regalia_hotel > backup_$(date +%Y%m%d).sql

# SQLite backup
cp regalia_hotel.db backup_$(date +%Y%m%d).db
```

---

## Known Limitations

1. **Payment Gateway**: No real payment gateway integration. Manual payment workflow only.
2. **Email Notifications**: No email sending configured. Would require SMTP setup.
3. **Real-time Updates**: No WebSocket/SSE for real-time dashboard updates.
4. **File Uploads**: Room images use external URLs. Local upload not implemented.
5. **Multi-language**: English only. No i18n support.
6. **Reporting**: Basic statistics only. No advanced reporting or analytics.
7. **Rate Management**: No dynamic pricing or seasonal rate automation.
8. **Channel Management**: No OTA (Online Travel Agency) integration.
9. **Legal Compliance**: Policy content should be reviewed by a legal professional.
10. **Accessibility**: Basic accessibility but no WCAG 2.1 AA certification.

### Recommendations for Production
- Integrate Razorpay/Stripe for payments
- Configure SendGrid/AWS SES for emails
- Add Redis for caching and sessions
- Implement Celery for background tasks
- Add monitoring (Sentry, New Relic)
- Conduct professional security audit
- Obtain legal review of all policies
- Perform load testing
- Add CDN for static assets

---

## License

Proprietary — All rights reserved. Created for Regalia Hotel, Kolkata.

---

## Support

For technical support or questions:
- **Email**: info@regaliahotel.com
- **Phone**: +91 33 1234 5678
- **Address**: Royal Avenue, Kolkata, West Bengal, India - 700046

---

*Built with ❤️ for Regalia Hotel, Kolkata*
