from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..core.security import authenticate_operator, create_access_token, get_current_operator


router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(credentials: LoginRequest):
    if not authenticate_operator(credentials.username, credentials.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid operator credentials")
    return {"access_token": create_access_token(credentials.username), "token_type": "bearer", "operator": credentials.username}


@router.get("/me")
def current_operator(operator=Depends(get_current_operator)):
    return {"username": operator["sub"], "expires_at": operator["exp"]}
