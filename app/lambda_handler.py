"""AWS Lambda entry point for the FastAPI application."""

from mangum import Mangum

from app.dependencies.supabase import init_supabase_client
from app.main import app

# Initialize the shared client once per Lambda execution environment. The FastAPI
# lifespan is disabled in Mangum so this is not repeated for every invocation.
init_supabase_client()

handler = Mangum(app, lifespan="off")
