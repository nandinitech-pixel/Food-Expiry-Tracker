import os
import smtplib
from datetime import date
from email.message import EmailMessage

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from database import get_connection
from auth import register_user, login_user

try:
    import cv2
    import numpy as np
    BARCODE_SCANNER_AVAILABLE = hasattr(cv2, "barcode_BarcodeDetector")
except Exception:
    BARCODE_SCANNER_AVAILABLE = False

st.set_page_config(
    page_title="Food Expiry Tracker",
    page_icon="🍎",
    layout="wide",
)


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
        return "Expiring Soon", "🟠 EXPIRING SOON", f"Only {days_left} day(s) remaining."
    if days_left <= 7:
        return "Expiring This Week", "🟡 EXPIRING THIS WEEK", f"{days_left} day(s) remaining."
    return "Fresh", "🟢 FRESH", f"{days_left} day(s) remaining."


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


def add_food_item(user_id, food_name, quantity, purchase_date, expiry_date, barcode):
    supabase = get_connection()
    response = supabase.table("food_items").insert({
        "food_name": food_name,
        "quantity": int(quantity),
        "purchase_date": purchase_date.isoformat(),
        "expiry_date": expiry_date.isoformat(),
        "barcode": barcode or None,
        "user_id": user_id,
    }).execute()
    return bool(response.data)


def update_food_item(item_id, user_id, food_name, quantity, purchase_date, expiry_date, barcode):
    supabase = get_connection()
    response = (
        supabase.table("food_items")
        .update({
            "food_name": food_name,
            "quantity": int(quantity),
            "purchase_date": purchase_date.isoformat(),
            "expiry_date": expiry_date.isoformat(),
            "barcode": barcode or None,
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
            alert_items.append(
                f"- {item['food_name']} | Quantity: {item['quantity']} | "
                f"Expiry Date: {expiry} | {status}"
            )

    if not alert_items:
        return False, "No items are expiring within 7 days."

    message = EmailMessage()
    message["Subject"] = "Food Expiry Alert Report"
    message["From"] = sender_email
    message["To"] = receiver_email
    message.set_content(
        "Food Expiry Tracking Report\n\nItems requiring attention:\n\n"
        + "\n".join(alert_items)
    )

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, app_password)
            server.send_message(message)
        return True, "Email sent successfully!"
    except Exception as error:
        return False, f"Email error: {error}"


if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    st.title("🍎 Food Expiry Tracker")
    st.write("Smart food management and expiry monitoring system")
    login_tab, register_tab = st.tabs(["🔐 Login", "📝 Register"])

    with login_tab:
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("🔐 Login", use_container_width=True):
            if not username.strip() or not password:
                st.warning("Please enter username and password.")
            else:
                try:
                    user = login_user(username.strip(), password)
                    if user:
                        st.session_state.user = user
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")
                except Exception as error:
                    st.error(f"Login error: {error}")

    with register_tab:
        new_username = st.text_input("Create Username", key="register_username")
        new_password = st.text_input("Create Password", type="password", key="register_password")
        confirm_password = st.text_input("Confirm Password", type="password", key="confirm_password")
        notification_email = st.text_input("Notification Email (optional)", key="register_email")

        if st.button("📝 Register", use_container_width=True):
            if not new_username.strip() or not new_password:
                st.warning("Please fill in username and password.")
            elif new_password != confirm_password:
                st.error("Passwords do not match.")
            elif len(new_password) < 6:
                st.warning("Password must contain at least 6 characters.")
            else:
                try:
                    success = register_user(
                        new_username.strip(), new_password, notification_email.strip()
                    )
                    if success:
                        st.success("Registration successful! You can now log in.")
                    else:
                        st.error("Username already exists or registration failed.")
                except Exception as error:
                    st.error(f"Registration error: {error}")
    st.stop()

user_id = st.session_state.user["id"]
username = st.session_state.user["username"]
today = date.today()

with st.sidebar:
    st.header("📧 Email Settings")
    saved_email = get_user_email(user_id)
    notification_email = st.text_input(
        "Notification Email", value=saved_email, placeholder="Enter your email"
    )
    if st.button("💾 Save Email", use_container_width=True):
        if "@" not in notification_email or not notification_email.strip():
            st.error("Please enter a valid email address.")
        else:
            try:
                save_user_email(user_id, notification_email.strip())
                st.success("Email saved successfully!")
            except Exception as error:
                st.error(f"Could not save email: {error}")

st.markdown(
    "<div style='text-align:center; padding:15px 0 25px 0;'>"
    "<h1>🍎 Food Expiry Tracker</h1>"
    "<p style='font-size:18px;'>Smart food management and expiry monitoring system</p>"
    "</div>",
    unsafe_allow_html=True,
)

user_col, logout_col = st.columns([4, 1])
with user_col:
    st.success(f"👤 Logged in as: {username}")
with logout_col:
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.user = None
        st.rerun()

with st.expander("ℹ️ How does this system work?"):
    st.write(
        "1. Register or log in.\n"
        "2. Add food items with dates.\n"
        "3. Data is stored in Supabase.\n"
        "4. Expiry status is calculated automatically.\n"
        "5. Search, filter, edit, delete, email and download reports."
    )

st.header("➕ Add Food Item")
add_col1, add_col2 = st.columns(2)
with add_col1:
    food_name = st.text_input("Food Name", placeholder="Example: Milk")
    quantity = st.number_input("Quantity", min_value=1, step=1)
    barcode = st.text_input("📦 Barcode Number", placeholder="Optional barcode")
with add_col2:
    purchase_date = st.date_input("Purchase Date", value=today)
    expiry_date = st.date_input("Expiry Date", value=today)

if st.button("➕ Add Food Item", type="primary", use_container_width=True):
    if not food_name.strip():
        st.warning("Please enter the food name.")
    elif expiry_date < purchase_date:
        st.error("Expiry date cannot be before purchase date.")
    else:
        try:
            if add_food_item(user_id, food_name.strip(), quantity, purchase_date, expiry_date, barcode.strip()):
                st.success("✅ Food item added successfully!")
                st.rerun()
            else:
                st.error("Food item could not be added.")
        except Exception as error:
            st.error(f"Database error: {error}")

try:
    food_items = fetch_food_items(user_id)
except Exception as error:
    food_items = []
    st.error(f"Could not load food items: {error}")

st.divider()
st.header("📷 Scan Food Barcode")
if not BARCODE_SCANNER_AVAILABLE:
    st.info("Barcode scanner unavailable. Install: python -m pip install opencv-contrib-python")
else:
    camera_photo = st.camera_input("Capture barcode")
    if camera_photo is not None:
        try:
            image_array = np.frombuffer(camera_photo.getvalue(), dtype=np.uint8)
            frame = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            detector = cv2.barcode_BarcodeDetector()
            result = detector.detectAndDecode(frame)
            decoded_values = []
            if isinstance(result, tuple):
                for value in result:
                    if isinstance(value, str) and value.strip():
                        decoded_values.append(value.strip())
                    elif isinstance(value, (list, tuple)):
                        decoded_values.extend(str(x).strip() for x in value if isinstance(x, str) and x.strip())
            elif isinstance(result, str) and result.strip():
                decoded_values.append(result.strip())
            decoded_values = list(dict.fromkeys(decoded_values))
            if not decoded_values:
                st.warning("No barcode detected. Try better lighting and keep it inside the frame.")
            else:
                scanned_value = decoded_values[0]
                st.success(f"✅ Barcode detected: {scanned_value}")
                matches = [x for x in food_items if str(x.get("barcode") or "").strip() == scanned_value]
                if matches:
                    for item in matches:
                        _, label, message = get_status(item["expiry_date"], today)
                        st.info(f"🍎 {item['food_name']} | 📦 {item['quantity']} | 📅 {item['expiry_date']}\n\n{label} — {message}")
                else:
                    st.warning("Barcode detected, but no matching item was found in your account.")
        except Exception as error:
            st.error(f"Barcode scanning error: {error}")

expired_items, today_items, soon_items, week_items, fresh_items = [], [], [], [], []
for item in food_items:
    days_left = (as_date(item["expiry_date"]) - today).days
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

st.divider()
st.header("📊 Dashboard")
d1, d2, d3, d4 = st.columns(4)
d1.metric("📦 Total Items", len(food_items))
d2.metric("🔴 Expired", len(expired_items))
d3.metric("🟠 Expiring Soon", len(today_items) + len(soon_items))
d4.metric("🟢 Fresh", len(fresh_items))

st.divider()
st.header("🚨 Expiry Alerts")
for title, items, message_type in [
    ("Expired", expired_items, "error"),
    ("Expires today", today_items, "warning"),
    ("Expiring within 3 days", soon_items, "warning"),
    ("Expiring within 7 days", week_items, "info"),
]:
    if items:
        getattr(st, message_type)(f"{title}: {len(items)} item(s)")
        for item in items:
            expiry = as_date(item["expiry_date"])
            days = (expiry - today).days
            st.write(f"**{item['food_name']}** — expiry date: {expiry} ({days} day(s) relative to today)")
if not any([expired_items, today_items, soon_items, week_items]):
    st.success("✅ No food items are expiring within 7 days.") if food_items else st.info("📭 Add food items to receive expiry alerts.")

st.divider()
st.header("📧 Email Expiry Report")
if st.button("📧 Send Expiry Report by Email", use_container_width=True):
    receiver_email = get_user_email(user_id)
    if not receiver_email:
        st.warning("Please save your notification email in the sidebar first.")
    else:
        with st.spinner("Sending email..."):
            success, message = send_expiry_email(food_items, today, receiver_email)
        (st.success if success else st.warning)(message)

st.divider()
st.header("📥 Download Food Report")
if food_items:
    report_data = []
    for item in food_items:
        status, _, _ = get_status(item["expiry_date"], today)
        report_data.append({
            "Food Name": item["food_name"],
            "Quantity": item["quantity"],
            "Purchase Date": item["purchase_date"],
            "Expiry Date": item["expiry_date"],
            "Barcode": item.get("barcode", ""),
            "Status": status,
        })
    st.download_button(
        "📥 Download CSV Report",
        pd.DataFrame(report_data).to_csv(index=False),
        "food_expiry_report.csv",
        "text/csv",
        use_container_width=True,
    )
else:
    st.info("Add food items to download a report.")

st.divider()
st.header("📊 Food Expiry Analytics")
if food_items:
    statuses = [get_status(item["expiry_date"], today)[0] for item in food_items]
    order = ["Expired", "Expires Today", "Expiring Soon", "Expiring This Week", "Fresh"]
    counts = pd.Series(statuses).value_counts().reindex(order, fill_value=0)
    st.bar_chart(counts)
    summary = counts.reset_index()
    summary.columns = ["Status", "Number of Items"]
    st.dataframe(summary, use_container_width=True, hide_index=True)
else:
    st.info("Add food items to view analytics.")

st.divider()
st.header("🔍 Search, Edit & Delete")
search_text = st.text_input("Search food by name", placeholder="Example: Milk")
filter_status = st.selectbox("Filter by status", ["All", "Expired", "Expires Today", "Expiring Soon", "Expiring This Week", "Fresh"])
filtered_items = []
for item in food_items:
    if search_text.lower() not in item["food_name"].lower():
        continue
    status, _, _ = get_status(item["expiry_date"], today)
    if filter_status != "All" and status != filter_status:
        continue
    filtered_items.append(item)

for item in filtered_items:
    item_id = item["id"]
    status, label, message = get_status(item["expiry_date"], today)
    with st.expander(f"{label} — {item['food_name']} (ID: {item_id})"):
        st.write(f"Quantity: {item['quantity']}")
        st.write(f"Purchase date: {item['purchase_date']}")
        st.write(f"Expiry date: {item['expiry_date']}")
        st.write(f"Barcode: {item.get('barcode') or 'Not available'}")
        st.write(message)

        edit_col, delete_col = st.columns(2)
        with edit_col:
            with st.form(f"edit_form_{item_id}"):
                edit_name = st.text_input("Food Name", value=item["food_name"], key=f"name_{item_id}")
                edit_quantity = st.number_input("Quantity", min_value=1, value=int(item["quantity"]), step=1, key=f"qty_{item_id}")
                edit_purchase = st.date_input("Purchase Date", value=as_date(item["purchase_date"]), key=f"purchase_{item_id}")
                edit_expiry = st.date_input("Expiry Date", value=as_date(item["expiry_date"]), key=f"expiry_{item_id}")
                edit_barcode = st.text_input("Barcode", value=item.get("barcode") or "", key=f"barcode_{item_id}")
                save_edit = st.form_submit_button("💾 Update")
                if save_edit:
                    if not edit_name.strip():
                        st.error("Food name is required.")
                    elif edit_expiry < edit_purchase:
                        st.error("Expiry date cannot be before purchase date.")
                    else:
                        try:
                            if update_food_item(item_id, user_id, edit_name.strip(), edit_quantity, edit_purchase, edit_expiry, edit_barcode.strip()):
                                st.success("Item updated successfully!")
                                st.rerun()
                            else:
                                st.error("Item could not be updated.")
                        except Exception as error:
                            st.error(f"Update error: {error}")
        with delete_col:
            st.write("Delete this item permanently.")
            if st.button("🗑️ Delete", key=f"delete_{item_id}"):
                try:
                    if delete_food_item(item_id, user_id):
                        st.success("Item deleted successfully!")
                        st.rerun()
                    else:
                        st.error("Item could not be deleted.")
                except Exception as error:
                    st.error(f"Delete error: {error}")
