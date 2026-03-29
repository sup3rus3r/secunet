from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from bson import ObjectId


class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, handler):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, schema, handler):
        return {"type": "string"}


class UserMongo(BaseModel):
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    username: str
    email: str
    role: str
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str},
    }


class UserCollection:
    collection_name = "users"

    @classmethod
    async def create_indexes(cls, db):
        collection = db[cls.collection_name]
        await collection.create_index("username", unique=True)
        await collection.create_index("email", unique=True)

    @classmethod
    async def find_by_username(cls, db, username: str) -> Optional[dict]:
        collection = db[cls.collection_name]
        return await collection.find_one({"username": username})

    @classmethod
    async def find_by_email(cls, db, email: str) -> Optional[dict]:
        collection = db[cls.collection_name]
        return await collection.find_one({"email": email})

    @classmethod
    async def create(cls, db, user_data: dict) -> dict:
        collection = db[cls.collection_name]
        result = await collection.insert_one(user_data)
        user_data["_id"] = result.inserted_id
        return user_data

    @classmethod
    async def find_by_id(cls, db, user_id: str) -> Optional[dict]:
        collection = db[cls.collection_name]
        return await collection.find_one({"_id": ObjectId(user_id)})

    @classmethod
    async def update_role(cls, db, user_id: str, new_role: str) -> Optional[dict]:
        collection = db[cls.collection_name]
        result = await collection.find_one_and_update(
            {"_id": ObjectId(user_id)},
            {"$set": {"role": new_role}},
            return_document=True
        )
        return result


class APIClientMongo(BaseModel):
    """API client model for MongoDB."""
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    name            : str
    client_id       : str
    hashed_secret   : str
    created_by      : str 
    is_active       : bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str},
    }


class APIClientCollection:
    """Collection helper for API clients in MongoDB."""
    collection_name = "api_clients"

    @classmethod
    async def create_indexes(cls, db):
        collection = db[cls.collection_name]
        await collection.create_index("client_id", unique=True)

    @classmethod
    async def find_by_client_id(cls, db, client_id: str) -> Optional[dict]:
        collection = db[cls.collection_name]
        return await collection.find_one({"client_id": client_id, "is_active": True})

    @classmethod
    async def find_by_user(cls, db, user_id: str) -> list[dict]:
        collection = db[cls.collection_name]
        cursor = collection.find({"created_by": user_id})
        return await cursor.to_list(length=100)

    @classmethod
    async def create(cls, db, client_data: dict) -> dict:
        collection = db[cls.collection_name]
        result = await collection.insert_one(client_data)
        client_data["_id"] = result.inserted_id
        return client_data

    @classmethod
    async def deactivate(cls, db, client_id: str, user_id: str) -> bool:
        collection = db[cls.collection_name]
        result = await collection.update_one(
            {"client_id": client_id, "created_by": user_id},
            {"$set": {"is_active": False}}
        )
        return result.modified_count > 0
