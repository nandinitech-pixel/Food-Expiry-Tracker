import os
import smtplib
from datetime import date
from email.message import EmailMessage

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from database import get_connection
from auth import register_user, login_user


# ============================================================
# BARCODE SCANNER
# ============================================================

try:
    import cv2
    import numpy as np

    BARCODE_SCANNER_AVAILABLE = hasattr(cv2, "barcode_BarcodeDetector")
except Exception:
    BARCODE_SCANNER_AVAILABLE = False


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Food Expiry Tracker",
    page_icon="🍎",
    layout="wide",
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def as_date(value):
    if isinstance(value, date):
        return value

    return date.fromisoformat(str(value)[:10])


def get_status(expiry_date, today):
    expiry_date = as_date(expiry_date)
    days_left = (expiry_date - today).days

    if days_left < 0:
        return "Expired", "🔴 EXPIRED", f"Expired {-days_left} day(s) ago."

    if days_left == 0:
        return "Expires Today", "🔴 EXPIRES TODAY", "Use this item today."

    if days_left <= 3:
        return (
            "Expiring Soon",
            "🟠 EXPIRING SOON",
            f"Only {days_left} day(s) remaining."
        )

    if days_left <= 7:
        return (
            "Expiring This Week",
            "🟡 EXPIRING THIS WEEK",
            f"{days_left} day(s) remaining."
        )

    return (
        "Fresh",
        "🟢 FRESH",
        f"{days_left} day(s) remaining."
    )


def get_action_display(action):
    """Convert database action into user-friendly display text."""

    if action == "Recycle":
        return "♻️ Recycle"

    if action == "Return":
        return "↩️ Return"

    if action == "Discard":
        return "🗑️ Discard"

    return "🗑️ Discard"


# ============================================================
# USER EMAIL FUNCTIONS
# ============================================================

def get_user_email(user_id):
    supabase = get_connection()

    response = (
        supabase.table("users")
        .select("notification_email")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )

    if response.data:
        return response.data[0].get("notification_email") or ""

    return ""


def save_user_email(user_id, email):
    supabase = get_connection()

    supabase.table("users").update({
        "notification_email": email
    }).eq("id", user_id).execute()


# ============================================================
# FOOD ITEM FUNCTIONS
# ============================================================

def fetch_food_items(user_id):
    supabase = get_connection()

    response = (
        supabase.table("food_items")
        .select("*")
        .eq("user_id", user_id)
        .order("expiry_date")
        .execute()
    )

    return response.data or []


def add_food_item(
    user_id,
    food_name,
    quantity,
    purchase_date,
    expiry_date,
    barcode,
    disposal_action
):
    supabase = get_connection()

    response = supabase.table("food_items").insert({
        "food_name": food_name,
        "quantity": int(quantity),
        "purchase_date": purchase_date.isoformat(),
        "expiry_date": expiry_date.isoformat(),
        "barcode": barcode or None,
        "disposal_action": disposal_action,
        "user_id": user_id,
    }).execute()

    return bool(response.data)


def update_food_item(
    item_id,
    user_id,
    food_name,
    quantity,
    purchase_date,
    expiry_date,
    barcode,
    disposal_action
):
    supabase = get_connection()

    response = (
        supabase.table("food_items")
        .update({
            "food_name": food_name,
            "quantity": int(quantity),
            "purchase_date": purchase_date.isoformat(),
            "expiry_date": expiry_date.isoformat(),
            "barcode": barcode or None,
            "disposal_action": disposal_action,
        })
        .eq("id", item_id)
        .eq("user_id", user_id)
        .execute()
    )

    return bool(response.data)


def delete_food_item(item_id, user_id):
    supabase = get_connection()

    response = (
        supabase.table("food_items")
        .delete()
        .eq("id", item_id)
        .eq("user_id", user_id)
        .execute()
    )

    return bool(response.data)


# ============================================================
# EMAIL FUNCTION
# ============================================================

def send_expiry_email(items, today, receiver_email):
    load_dotenv()

    sender_email = os.getenv("SMTP_EMAIL")
    app_password = os.getenv("SMTP_APP_PASSWORD")

    if not sender_email or not app_password or not receiver_email:
        return False, "Email settings are missing. Check your .env file."

    alert_items = []

    for item in items:

        expiry = as_date(item["expiry_date"])
        days_left = (expiry - today).days

        if days_left <= 7:

            if days_left < 0:
                status = f"Expired {-days_left} day(s) ago"

            elif days_left == 0:
                status = "Expires today"

            else:
                status = f"Expires in {days_left} day(s)"

            action = item.get("disposal_action") or "Discard"

            alert_items.append(
                f"- {item['food_name']} | "
                f"Quantity: {item['quantity']} | "
                f"Expiry Date: {expiry} | "
                f"{status} | "
                f"Action: {action}"
            )

    if not alert_items:
        return False, "No items are expiring within 7 days."

    message = EmailMessage()

    message["Subject"] = "Food Expiry Alert Report"
    message["From"] = sender_email
    message["To"] = receiver_email

    message.set_content(
        "Food Expiry Tracking Report\n\n"
        "Items requiring attention:\n\n"
        + "\n".join(alert_items)
    )

    try:

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:

            server.login(sender_email, app_password)

            server.send_message(message)

        return True, "Email sent successfully!"

    except Exception as error:

        return False, f"Email error: {error}"


# ============================================================
# SESSION STATE
# ============================================================

if "user" not in st.session_state:
    st.session_state.user = None


# ============================================================
# LOGIN / REGISTER
# ============================================================

if st.session_state.user is None:

    st.title("🍎 Food Expiry Tracker")

    st.write(
        "Smart food management and expiry monitoring system"
    )

    login_tab, register_tab = st.tabs(
        ["🔐 Login", "📝 Register"]
    )

    # --------------------------------------------------------
    # LOGIN
    # --------------------------------------------------------

    with login_tab:

        username = st.text_input(
            "Username",
            key="login_username"
        )

        password = st.text_input(
            "Password",
            type="password",
            key="login_password"
        )

        if st.button(
            "🔐 Login",
            use_container_width=True
        ):

            if not username.strip() or not password:

                st.warning(
                    "Please enter username and password."
                )

            else:

                try:

                    user = login_user(
                        username.strip(),
                        password
                    )

                    if user:

                        st.session_state.user = user

                        st.rerun()

                    else:

                        st.error(
                            "Invalid username or password."
                        )

                except Exception as error:

                    st.error(
                        f"Login error: {error}"
                    )

    # --------------------------------------------------------
    # REGISTER
    # --------------------------------------------------------

    with register_tab:

        new_username = st.text_input(
            "Create Username",
            key="register_username"
        )

        new_password = st.text_input(
            "Create Password",
            type="password",
            key="register_password"
        )

        confirm_password = st.text_input(
            "Confirm Password",
            type="password",
            key="confirm_password"
        )

        notification_email = st.text_input(
            "Notification Email (optional)",
            key="register_email"
        )

        if st.button(
            "📝 Register",
            use_container_width=True
        ):

            if not new_username.strip() or not new_password:

                st.warning(
                    "Please fill in username and password."
                )

            elif new_password != confirm_password:

                st.error(
                    "Passwords do not match."
                )

            elif len(new_password) < 6:

                st.warning(
                    "Password must contain at least 6 characters."
                )

            else:

                try:

                    success = register_user(
                        new_username.strip(),
                        new_password,
                        notification_email.strip()
                    )

                    if success:

                        st.success(
                            "Registration successful! You can now log in."
                        )

                    else:

                        st.error(
                            "Username already exists or registration failed."
                        )

                except Exception as error:

                    st.error(
                        f"Registration error: {error}"
                    )

    st.stop()


# ============================================================
# CURRENT USER
# ============================================================

user_id = st.session_state.user["id"]
username = st.session_state.user["username"]
today = date.today()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("📧 Email Settings")

    saved_email = get_user_email(user_id)

    notification_email = st.text_input(
        "Notification Email",
        value=saved_email,
        placeholder="Enter your email"
    )

    if st.button(
        "💾 Save Email",
        use_container_width=True
    ):

        if "@" not in notification_email or not notification_email.strip():

            st.error(
                "Please enter a valid email address."
            )

        else:

            try:

                save_user_email(
                    user_id,
                    notification_email.strip()
                )

                st.success(
                    "Email saved successfully!"
                )

            except Exception as error:

                st.error(
                    f"Could not save email: {error}"
                )


# ============================================================
# HEADER
# ============================================================

st.markdown(
    "<div style='text-align:center; padding:15px 0 25px 0;'>"
    "<h1>🍎 Food Expiry Tracker</h1>"
    "<p style='font-size:18px;'>"
    "Smart food management and expiry monitoring system"
    "</p>"
    "</div>",
    unsafe_allow_html=True,
)


# ============================================================
# USER / LOGOUT
# ============================================================

user_col, logout_col = st.columns([4, 1])

with user_col:

    st.success(
        f"👤 Logged in as: {username}"
    )

with logout_col:

    if st.button(
        "🚪 Logout",
        use_container_width=True
    ):

        st.session_state.user = None

        st.rerun()


# ============================================================
# HOW SYSTEM WORKS
# ============================================================

with st.expander("ℹ️ How does this system work?"):

    st.write(
        "1. Register or log in.\n"
        "2. Add food items with dates.\n"
        "3. Select whether the item should be recycled, returned, or discarded.\n"
        "4. Data is stored in Supabase.\n"
        "5. Expiry status is calculated automatically.\n"
        "6. Search, filter, edit, delete, email and download reports."
    )


# ============================================================
# ADD FOOD ITEM
# ============================================================

st.header("➕ Add Food Item")

add_col1, add_col2 = st.columns(2)


with add_col1:

    food_name = st.text_input(
        "Food Name",
        placeholder="Example: Milk"
    )

    quantity = st.number_input(
        "Quantity",
        min_value=1,
        step=1
    )

    barcode = st.text_input(
        "📦 Barcode Number",
        placeholder="Optional barcode"
    )


with add_col2:

    purchase_date = st.date_input(
        "Purchase Date",
        value=today
    )

    expiry_date = st.date_input(
        "Expiry Date",
        value=today
    )

    disposal_action = st.selectbox(
        "♻️ What should happen to this item?",
        [
            "Recycle",
            "Return",
            "Discard"
        ],
        format_func=lambda x: {
            "Recycle": "♻️ Recycle",
            "Return": "↩️ Return",
            "Discard": "🗑️ Discard"
        }[x]
    )


# ============================================================
# ADD BUTTON
# ============================================================

if st.button(
    "➕ Add Food Item",
    type="primary",
    use_container_width=True
):

    if not food_name.strip():

        st.warning(
            "Please enter the food name."
        )

    elif expiry_date < purchase_date:

        st.error(
            "Expiry date cannot be before purchase date."
        )

    else:

        try:

            if add_food_item(
                user_id,
                food_name.strip(),
                quantity,
                purchase_date,
                expiry_date,
                barcode.strip(),
                disposal_action
            ):

                st.success(
                    f"✅ Food item added successfully! "
                    f"Action: {get_action_display(disposal_action)}"
                )

                st.rerun()

            else:

                st.error(
                    "Food item could not be added."
                )

        except Exception as error:

            st.error(
                f"Database error: {error}"
            )


# ============================================================
# FETCH FOOD ITEMS
# ============================================================

try:

    food_items = fetch_food_items(user_id)

except Exception as error:

    food_items = []

    st.error(
        f"Could not load food items: {error}"
    )


# ============================================================
# BARCODE SCANNER
# ============================================================

st.divider()

st.header("📷 Scan Food Barcode")

if not BARCODE_SCANNER_AVAILABLE:

    st.info(
        "Barcode scanner unavailable. "
        "Install: python -m pip install opencv-contrib-python"
    )

else:

    camera_photo = st.camera_input(
        "Capture barcode"
    )

    if camera_photo is not None:

        try:

            image_array = np.frombuffer(
                camera_photo.getvalue(),
                dtype=np.uint8
            )

            frame = cv2.imdecode(
                image_array,
                cv2.IMREAD_COLOR
            )

            detector = cv2.barcode_BarcodeDetector()

            result = detector.detectAndDecode(frame)

            decoded_values = []

            if isinstance(result, tuple):

                for value in result:

                    if isinstance(value, str) and value.strip():

                        decoded_values.append(
                            value.strip()
                        )

                    elif isinstance(value, (list, tuple)):

                        decoded_values.extend(
                            str(x).strip()
                            for x in value
                            if isinstance(x, str)
                            and x.strip()
                        )

            elif isinstance(result, str) and result.strip():

                decoded_values.append(
                    result.strip()
                )

            decoded_values = list(
                dict.fromkeys(decoded_values)
            )

            if not decoded_values:

                st.warning(
                    "No barcode detected. "
                    "Try better lighting and keep it inside the frame."
                )

            else:

                scanned_value = decoded_values[0]

                st.success(
                    f"✅ Barcode detected: {scanned_value}"
                )

                matches = [
                    x for x in food_items
                    if str(x.get("barcode") or "").strip()
                    == scanned_value
                ]

                if matches:

                    for item in matches:

                        _, label, message = get_status(
                            item["expiry_date"],
                            today
                        )

                        action = item.get(
                            "disposal_action"
                        ) or "Discard"

                        st.info(
                            f"🍎 {item['food_name']} | "
                            f"📦 {item['quantity']} | "
                            f"📅 {item['expiry_date']}\n\n"
                            f"{label} — {message}\n\n"
                            f"Recommended Action: "
                            f"{get_action_display(action)}"
                        )

                else:

                    st.warning(
                        "Barcode detected, but no matching item "
                        "was found in your account."
                    )

        except Exception as error:

            st.error(
                f"Barcode scanning error: {error}"
            )


# ============================================================
# CATEGORIZE ITEMS
# ============================================================

expired_items = []
today_items = []
soon_items = []
week_items = []
fresh_items = []

for item in food_items:

    days_left = (
        as_date(item["expiry_date"]) - today
    ).days

    if days_left < 0:

        expired_items.append(item)

    elif days_left == 0:

        today_items.append(item)

    elif days_left <= 3:

        soon_items.append(item)

    elif days_left <= 7:

        week_items.append(item)

    else:

        fresh_items.append(item)


# ============================================================
# DASHBOARD
# ============================================================

st.divider()

st.header("📊 Dashboard")

d1, d2, d3, d4 = st.columns(4)

d1.metric(
    "📦 Total Items",
    len(food_items)
)

d2.metric(
    "🔴 Expired",
    len(expired_items)
)

d3.metric(
    "🟠 Expiring Soon",
    len(today_items) + len(soon_items)
)

d4.metric(
    "🟢 Fresh",
    len(fresh_items)
)


# ============================================================
