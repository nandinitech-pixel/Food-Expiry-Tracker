from werkzeug.security import generate_password_hash, check_password_hash
from database import get_connection


def register_user(username, password, notification_email=""):
    supabase = get_connection()

    existing = (
        supabase.table("users")
        .select("id")
        .eq("username", username)
        .execute()
    )

    if existing.data:
        return False

    hashed_password = generate_password_hash(password)

    response = (
        supabase.table("users")
        .insert({
            "username": username,
            "password": hashed_password,
            "notification_email": notification_email,
        })
        .execute()
    )

    return bool(response.data)


def login_user(username, password):
    supabase = get_connection()

    response = (
        supabase.table("users")
        .select("*")
        .eq("username", username)
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    user = response.data[0]

    if check_password_hash(user.get("password", ""), password):
        return user

    return None
