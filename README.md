# PST Pooled Stocktake Team - Flask Application

Flask-based web application for PST Pooled Stocktake Team with PostgreSQL authentication and B2S stocktake management.

## Features

### Authentication
- User authentication with PostgreSQL database
- Secure session management (24-hour lifetime)
- Logout functionality

### Dashboard
- Responsive home page with sidebar navigation
- Menu sections for different stocktake categories (B2S, OFM, SSP, CFR, PWB)
- Real-time clock display

### B2S Stocktake Management
- **Search CNTNUM**: Query and display stocktake details including store code, date, branch name, count step, status, and block counts
- **Create CNTNUM**: Generate new count numbers with validation against planall2 table
- **Create Master Database**: Generate SQLite master database (.db file) with:
  - Stocktake information
  - Location masters
  - User data (employees + generated users)
  - PDA masters with product information
- **Download Master.db**: Download generated database files
- **Add Location**: Import Excel files to add location data to location_master table
- **Close Location**: Import Excel files to close locations in location_close table
- **Update SOH**: Import Excel files to update stock on hand in b2s_soh table

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create required directories:
```bash
mkdir -p uploads stocktake_databases
```

3. Configure database connection in `app.py` (already configured with provided credentials)

4. Run the application:
```bash
# For development with debug mode
FLASK_ENV=development python app.py

# For production (debug mode disabled)
python app.py
```

5. Access the application at: http://localhost:5000

## Database Configuration

The application connects to PostgreSQL with the following configuration:
- Host: 157.85.98.51
- Database: postgres
- User: postgres
- Password: 20020015
- Port: 5432

### Required Tables
- `auth_user` - User authentication
- `stocktakeid` - Stocktake records
- `planall2` - Planning data
- `location_master` - Location data
- `location_close` - Closed locations
- `b2s_soh` - Stock on hand
- `b2s_block_veno` - Blocked vendors
- `b2s_block_sku` - Blocked SKUs
- `b2s_master` - Product master data
- `employees` - Employee information

## Usage

### Login
1. Navigate to the login page
2. Enter your username and password
3. After successful authentication, you'll be redirected to the home page

### B2S Stocktake Operations

#### Create New Stocktake
1. Click on "B2S - Book to Stationery" in the sidebar
2. Fill in the Create B2S Stocktake form:
   - BU: B2S (pre-filled)
   - STCODE: Store code
   - ATYPE: Select 3F or 3Q
   - CNTDATE: Select count date
3. Click "Create CNTNUM" button
4. System will generate and display the CNTNUM

#### Search Existing Stocktake
1. Enter CNTNUM in the search field
2. Click "Search" button
3. System will populate all fields with stocktake data

#### Create Master Database
1. Search for a CNTNUM first
2. Click "Create Master" button
3. Wait for the database creation process to complete
4. System will generate a .db file in the stocktake_databases folder

#### Download Master Database
1. Ensure CNTNUM exists and master has been created
2. Click "Download Master.db" button
3. File will be downloaded to your computer

#### Import Location Data
1. Prepare Excel file with columns: `location_no`, `cntnum`
2. Click "Add Location" button
3. Select your Excel file
4. System will import and validate the data

#### Close Locations
1. Prepare Excel file with columns: `location_no`, `cntnum`
2. Click "Close Location" button
3. Select your Excel file
4. System will import closed location data

#### Update SOH
1. Prepare Excel file with `cntnum` column and other SOH data
2. Click "Update SOH" button
3. Select your Excel file
4. System will replace existing data for the CNTNUM

## File Structure

```
pst_stocktake_python_flask/
├── app.py                  # Main Flask application with API endpoints
├── requirements.txt        # Python dependencies
├── python_cdoe_model/     # Reference Python scripts
│   ├── create_cntnum.py   # CNTNUM creation logic
│   ├── b2s_create_master.py # Master database creation
│   └── db_connect.py      # Database connection helper
├── templates/
│   ├── login.html         # Login page template
│   └── home.html          # Home page with B2S interface
├── static/
│   └── styles/
│       └── style.css      # CSS styling
├── uploads/               # Temporary upload folder
└── stocktake_databases/   # Generated database files
```

## API Endpoints

### B2S Operations
- `POST /api/b2s/search` - Search for CNTNUM details
- `POST /api/b2s/create_cntnum` - Create new CNTNUM
- `POST /api/b2s/create_master` - Generate master database
- `GET /api/b2s/download_master/<cntnum>` - Download database file
- `POST /api/b2s/add_location` - Import location data from Excel
- `POST /api/b2s/close_location` - Import close location data from Excel
- `POST /api/b2s/update_soh` - Update SOH from Excel

## Security Notes

- Session secret key should be set via environment variable in production
- **Important**: Current implementation uses plain text password comparison. For production use, implement password hashing (e.g., bcrypt, argon2) for secure password storage
- **Important**: Database credentials are currently hardcoded in `app.py`. For production, move these to environment variables using `python-dotenv` or a secure configuration management system
- Use HTTPS in production environment
- Implement rate limiting for login attempts to prevent brute force attacks
- File upload validation should be enhanced for production use
- Maximum file upload size is set to 16MB

debug code
set DB_USER=prthanapat
set DB_HOST=103.22.182.82
set DB_NAME=pstdb4
set DB_PASSWORD=20020015
set SECRET_KEY=your-super-secret-key
set FLASK_ENV=development
python app.py
