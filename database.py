from sqlalchemy import create_engine
from urllib.parse import quote_plus

password = "Shreya2008@26#P4"
encoded_password = quote_plus(password)

DATABASE_URL = (
    f"mysql+pymysql://root:{encoded_password}"
    f"@localhost:3306/kabadiwala_db"
)

engine = create_engine(DATABASE_URL)