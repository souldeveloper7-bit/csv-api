
# CSV API

Flask API for importing CSV files into SQLite
and returning paginated JSON records.

## Features
- CSV file upload
- Multiple CSV imports
- Batch database insertion
- JSON records
- Pagination
- API key authentication

## Endpoints

GET /

GET /api/health

POST /admin/upload

GET /api/count

GET /api/records?page=1&per_page=20

## Authentication

Protected endpoints require:

X-API-Key: YOUR_SECRET_KEY

## Environment variables

API_KEY=your_secret_key

DB_PATH=/var/data/csv_api.db
