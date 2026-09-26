from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from database import engine


class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    phone: str = Field(pattern=r"^[6-9]\d{9}$")
    role: str = Field(pattern=r"^(collector|recycler|admin)$")

class OTPVerify(BaseModel):
    phone: str
    otp: str

class LotCreate(BaseModel):
    collector_id: int
    material_id: int
    weight: float = Field(gt=0)

class RecyclerCreate(BaseModel):
    user_id: int
    name: str = Field(min_length=2, max_length=100)
    location: str = Field(min_length=2, max_length=255)
    authorization_status: str = Field(
        pattern=r"^(authorized|pending|rejected)$"
    )
    pickup_available: bool



app = FastAPI()

@app.post("/auth/verify-otp")
def verify_otp(data: OTPVerify):

    DEMO_OTP = "123456"

    if data.otp != DEMO_OTP:
        raise HTTPException(
            status_code=401,
            detail="Invalid OTP"
        )

    return {
        "message": "OTP verified successfully",
        "phone": data.phone
    }


@app.get("/")
def home():
    return {"message": "Kabadiwala Connect API is running"}

# for the users table
# get from users table
@app.get("/users")
def get_users():

    with engine.connect() as connection:
        result = connection.execute(
            text("SELECT id, name, phone, role FROM users")
        )

        users = result.mappings().all()

    return users

# post (create user) to users table
@app.post("/users")
def create_user(user: UserCreate):

    with engine.connect() as connection:

        existing_user = connection.execute(
            text("SELECT id FROM users WHERE phone = :phone"),
            {"phone": user.phone}
        ).first()

        if existing_user:
            raise HTTPException(
                status_code=409,
                detail="Phone number already registered"
            )

        connection.execute(
            text("""
                INSERT INTO users (name, phone, role)
                VALUES (:name, :phone, :role)
            """),
            {
                "name": user.name,
                "phone": user.phone,
                "role": user.role
            }
        )

        connection.commit()

    return {
        "message": "User created successfully"
    }

@app.get("/users/{user_id}")
def get_user(user_id: int):

    with engine.connect() as connection:
        result = connection.execute(
            text("""
                SELECT id, name, phone, role
                FROM users
                WHERE id = :user_id
            """),
            {"user_id": user_id}
        )

        user = result.mappings().first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return user

@app.get("/materials")
def get_materials():

    with engine.connect() as connection:
        result = connection.execute(
            text("""
                SELECT id, name, category
                FROM materials
                ORDER BY category, name
            """)
        )

        materials = result.mappings().all()

    return materials

@app.post("/lots")
def create_lot(lot: LotCreate):

    with engine.connect() as connection:

        # Check collector
        collector = connection.execute(
            text("""
                SELECT id
                FROM users
                WHERE id = :collector_id
                AND role = 'collector'
            """),
            {"collector_id": lot.collector_id}
        ).first()

        if not collector:
            raise HTTPException(
                status_code=404,
                detail="Collector not found"
            )

        # Check material
        material = connection.execute(
            text("""
                SELECT id, name
                FROM materials
                WHERE id = :material_id
            """),
            {"material_id": lot.material_id}
        ).mappings().first()

        if not material:
            raise HTTPException(
                status_code=404,
                detail="Material not found"
            )

        # Create lot
        result = connection.execute(
            text("""
                INSERT INTO lots
                (collector_id, material_id, weight, status)
                VALUES
                (:collector_id, :material_id, :weight, 'pending')
            """),
            {
                "collector_id": lot.collector_id,
                "material_id": lot.material_id,
                "weight": lot.weight
            }
        )

        connection.commit()

        return {
            "message": "E-waste lot created successfully",
            "lot_id": result.lastrowid
        }

@app.get("/lots")
def get_lots():
    with engine.connect() as connection:
        result = connection.execute(
            text("""
                SELECT
                    lots.id,
                    users.name AS collector_name,
                    materials.name AS material,
                    lots.weight,
                    lots.estimated_value,
                    lots.status,
                    lots.created_at
                FROM lots
                JOIN users
                    ON lots.collector_id = users.id
                JOIN materials
                    ON lots.material_id = materials.id
                ORDER BY lots.created_at DESC
            """)
        )

        lots = result.mappings().all()

    return lots

@app.post("/recyclers")
def create_recycler(recycler: RecyclerCreate):

    with engine.connect() as connection:

        # Check that the user exists and has recycler role
        user = connection.execute(
            text("""
                SELECT id
                FROM users
                WHERE id = :user_id
                AND role = 'recycler'
            """),
            {"user_id": recycler.user_id}
        ).first()

        if not user:
            raise HTTPException(
                status_code=404,
                detail="Recycler user not found"
            )

        # Check if recycler profile already exists
        existing = connection.execute(
            text("""
                SELECT id
                FROM recyclers
                WHERE user_id = :user_id
            """),
            {"user_id": recycler.user_id}
        ).first()

        if existing:
            raise HTTPException(
                status_code=409,
                detail="Recycler profile already exists"
            )

        # Create recycler profile
        result = connection.execute(
            text("""
                INSERT INTO recyclers
                (user_id, name, location, authorization_status, pickup_available)
                VALUES
                (:user_id, :name, :location, :authorization_status, :pickup_available)
            """),
            {
                "user_id": recycler.user_id,
                "name": recycler.name,
                "location": recycler.location,
                "authorization_status": recycler.authorization_status,
                "pickup_available": recycler.pickup_available
            }
        )

        connection.commit()

        return {
            "message": "Recycler created successfully",
            "recycler_id": result.lastrowid
        }

@app.get("/recyclers")
def get_recyclers():

    with engine.connect() as connection:
        result = connection.execute(
            text("""
                SELECT
                    recyclers.id,
                    recyclers.name,
                    recyclers.location,
                    recyclers.authorization_status,
                    recyclers.pickup_available
                FROM recyclers
                ORDER BY recyclers.id
            """)
        )

        recyclers = result.mappings().all()

    return recyclers

@app.post("/recyclers/{recycler_id}/materials")
def add_recycler_material(recycler_id: int, material_id: int):

    with engine.connect() as connection:

        # Check recycler
        recycler = connection.execute(
            text("""
                SELECT id
                FROM recyclers
                WHERE id = :recycler_id
            """),
            {"recycler_id": recycler_id}
        ).first()

        if not recycler:
            raise HTTPException(
                status_code=404,
                detail="Recycler not found"
            )

        # Check material
        material = connection.execute(
            text("""
                SELECT id
                FROM materials
                WHERE id = :material_id
            """),
            {"material_id": material_id}
        ).first()

        if not material:
            raise HTTPException(
                status_code=404,
                detail="Material not found"
            )

        # Check duplicate mapping
        existing = connection.execute(
            text("""
                SELECT *
                FROM recycler_materials
                WHERE recycler_id = :recycler_id
                AND material_id = :material_id
            """),
            {
                "recycler_id": recycler_id,
                "material_id": material_id
            }
        ).first()

        if existing:
            raise HTTPException(
                status_code=409,
                detail="Material already added for this recycler"
            )

        connection.execute(
            text("""
                INSERT INTO recycler_materials
                (recycler_id, material_id)
                VALUES
                (:recycler_id, :material_id)
            """),
            {
                "recycler_id": recycler_id,
                "material_id": material_id
            }
        )

        connection.commit()

    return {
        "message": "Material added to recycler successfully"
    }