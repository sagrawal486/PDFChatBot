from fastapi import FastAPI
from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.documents import router as document_router
from app.core.settings import settings

app = FastAPI(title=settings.APP_NAME,version="1.0.0",)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(
    document_router
)
@app.get("/")
async def root():
    return {"message": "AI PDF Chatbot API is running"}






