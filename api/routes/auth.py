"""
auth.py — User Authentication and Registration Routes.
"""
from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies import get_chat_store, get_current_user
from api.schemas import (
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from src.security import create_access_token, hash_password, verify_password
from storage import ChatStore

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(
    payload: UserRegisterRequest,
    store: ChatStore = Depends(get_chat_store),
):
    """
    Registers a new user account with hashed password credentials.
    """
    # Check if username exists
    if store.get_user_by_username(payload.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username '{payload.username}' is already taken.",
        )

    # Check if email exists
    if store.get_user_by_email(payload.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Email '{payload.email}' is already registered.",
        )

    hashed = hash_password(payload.password)
    user = store.create_user(
        username=payload.username,
        email=payload.email,
        hashed_password=hashed,
        role="user",
    )
    return UserResponse(
        user_id=user["user_id"],
        username=user["username"],
        email=user["email"],
        role=user["role"],
        created_at=user["created_at"],
    )


@router.post("/login", response_model=TokenResponse)
def login_user(
    payload: UserLoginRequest,
    store: ChatStore = Depends(get_chat_store),
):
    """
    Authenticates user credentials and issues a signed JWT access token.
    """
    # Lookup by username or email
    user = store.get_user_by_username(payload.username_or_email)
    if not user:
        user = store.get_user_by_email(payload.username_or_email)

    if not user or not verify_password(payload.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        user_id=user["user_id"],
        username=user["username"],
        role=user.get("role", "user"),
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user["user_id"],
        username=user["username"],
        role=user.get("role", "user"),
    )


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(
    current_user: dict = Depends(get_current_user),
):
    """
    Returns the profile information of the currently authenticated user.
    """
    return UserResponse(
        user_id=current_user["user_id"],
        username=current_user["username"],
        email=current_user["email"],
        role=current_user.get("role", "user"),
        created_at=current_user["created_at"],
    )
