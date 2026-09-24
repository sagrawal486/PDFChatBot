from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.documents import router as document_router
from app.api.health import router as health_router
from app.api.questions import router as question_router
from app.api.users import router as users_router
from app.core.settings import settings

app = FastAPI(title=settings.APP_NAME, version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(document_router)
app.include_router(question_router)


@app.get("/")
async def root():
    return {"message": "AI PDF Chatbot API is running"}
