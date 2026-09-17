from database import get_connection
from werkzeug.security import generate_password_hash, check_password_hash


def register_user(username, password):
    connection = get_connection()
    cursor = connection.cursor()

    hashed_password = generate_password_hash(password)

    try:
        cursor.execute(
            """
            INSERT INTO users (username, password)
            VALUES (%s, %s)
            """,
            (username, hashed_password)
        )

        connection.commit()
        return True

    except Exception:
        return False

    finally:
        cursor.close()
        connection.close()


def login_user(username, password):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT * FROM users
        WHERE username = %s
        """,
        (username,)
    )

    user = cursor.fetchone()

    cursor.close()
    connection.close()

    if user and check_password_hash(
        user["password"],
        password
    ):
        return user

    return None