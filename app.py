import streamlit as st
import pandas as pd
from datetime import date
import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv
from database import get_connection
from auth import register_user, login_user

# OpenCV camera barcode scanner
try:
    import cv2
    import numpy as np
    BARCODE_SCANNER_AVAILABLE = hasattr(cv2, "barcode_BarcodeDetector")
except Exception:
    BARCODE_SCANNER_AVAILABLE = False


# ---------------- PAGE SETTINGS ----------------

st.set_page_config(
    page_title="Food Expiry Tracker",
    page_icon="🍎",
    layout="wide"
)


# ---------------- HELPER FUNCTION ----------------

def get_status(expiry_date, today):
    days_left = (expiry_date - today).days

    if days_left < 0:
        return "Expired", "🔴 EXPIRED", f"Expired {-days_left} day(s) ago."
    elif days_left == 0:
        return "Expires Today", "🔴 EXPIRES TODAY", "Use this item today."
    elif days_left <= 3:
        return "Expiring Soon", "🟠 EXPIRING SOON", f"Only {days_left} day(s) remaining."
    elif days_left <= 7:
        return "Expiring This Week", "🟡 EXPIRING THIS WEEK", f"{days_left} day(s) remaining."
    else:
        return "Fresh", "🟢 FRESH", f"{days_left} day(s) remaining."


def close_connection(connection, cursor):
    try:
        cursor.close()
    except Exception:
        pass

    try:
        connection.close()
    except Exception:
        pass


# ---------------- USER EMAIL SETTINGS ----------------

def get_user_email(user_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "SELECT notification_email FROM users WHERE id = %s",
        (user_id,)
    )

    result = cursor.fetchone()
    close_connection(connection, cursor)

    return result[0] if result else ""


def save_user_email(user_id, email):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE users
        SET notification_email = %s
        WHERE id = %s
        """,
        (email, user_id)
    )

    connection.commit()
    close_connection(connection, cursor)


# ---------------- EMAIL FUNCTION ----------------

def send_expiry_email(items, today, receiver_email):
    load_dotenv()

    sender_email = os.getenv("SMTP_EMAIL")
    app_password = os.getenv("SMTP_APP_PASSWORD")

    if not sender_email or not app_password or not receiver_email:
        return False, "Check your .env file settings."

    alert_items = []

    for item in items:
        days_left = (item["expiry_date"] - today).days

        if days_left <= 7:
            if days_left < 0:
                status = f"Expired {-days_left} day(s) ago"
            elif days_left == 0:
                status = "Expires today"
            else:
                status = f"Expires in {days_left} day(s)"

            alert_items.append(
                f"- {item['food_name']} | "
                f"Quantity: {item['quantity']} | "
                f"Expiry Date: {item['expiry_date']} | "
                f"{status}"
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


# ---------------- SESSION STATE ----------------

if "user" not in st.session_state:
    st.session_state.user = None


# ---------------- LOGIN AND REGISTRATION ----------------

if st.session_state.user is None:

    st.title("🍎 Food Expiry Tracker")
    st.write("Smart food management and expiry monitoring system")

    login_tab, register_tab = st.tabs(["🔐 Login", "📝 Register"])

    with login_tab:
        st.subheader("Login to Your Account")

        username = st.text_input("Username", key="login_username")
        password = st.text_input(
            "Password",
            type="password",
            key="login_password"
        )

        if st.button("🔐 Login", use_container_width=True):

            if not username.strip() or not password:
                st.warning("Please enter username and password.")
            else:
                try:
                    user = login_user(username.strip(), password)

                    if user:
                        st.session_state.user = user
                        st.success("Login successful!")
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")

                except Exception as e:
                    st.error(f"Login error: {e}")

    with register_tab:
        st.subheader("Create a New Account")

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

        if st.button("📝 Register", use_container_width=True):

            if not new_username.strip() or not new_password:
                st.warning("Please fill in all fields.")
            elif new_password != confirm_password:
                st.error("Passwords do not match.")
            elif len(new_password) < 6:
                st.warning("Password must contain at least 6 characters.")
            else:
                try:
                    success = register_user(
                        new_username.strip(),
                        new_password
                    )

                    if success:
                        st.success(
                            "Registration successful! You can now log in."
                        )
                    else:
                        st.error(
                            "Username already exists or registration failed."
                        )

                except Exception as e:
                    st.error(f"Registration error: {e}")

    st.stop()


# ---------------- USER DETAILS ----------------

user_id = st.session_state.user["id"]
username = st.session_state.user["username"]


# ---------------- SIDEBAR EMAIL SETTINGS ----------------

with st.sidebar:
    st.header("📧 Email Settings")
    st.write("Choose where expiry reports should be sent.")

    saved_email = get_user_email(user_id)

    notification_email = st.text_input(
        "Notification Email",
        value=saved_email,
        placeholder="Enter your email address"
    )

    if st.button("💾 Save Email", use_container_width=True):
        if not notification_email.strip() or "@" not in notification_email:
            st.error("Please enter a valid email address.")
        else:
            save_user_email(
                user_id,
                notification_email.strip()
            )
            st.success("Email saved successfully!")


# ---------------- HEADER ----------------

st.markdown(
    """
    <div style="text-align:center; padding:15px 0 25px 0;">
        <h1>🍎 Food Expiry Tracker</h1>
        <p style="font-size:18px;">
            Smart food management and expiry monitoring system
        </p>
    </div>
    """,
    unsafe_allow_html=True
)

user_col, logout_col = st.columns([4, 1])

with user_col:
    st.success(f"👤 Logged in as: {username}")

with logout_col:
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.user = None
        st.rerun()


with st.expander("ℹ️ How does this system work?"):
    st.write("""
    1. Register or log in to your account.
    2. Add food items with quantity and dates.
    3. Information is stored in MySQL.
    4. Expiry status is calculated automatically.
    5. Expiry alerts are displayed.
    6. Search, filter, edit, and delete food items.
    7. Download a CSV report.
    8. View expiry analytics using a chart.
    """)


# ---------------- ADD FOOD ITEM ----------------

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
        value=date.today()
    )

    expiry_date = st.date_input(
        "Expiry Date",
        value=date.today()
    )


if st.button(
    "➕ Add Food Item",
    type="primary",
    use_container_width=True
):

    if not food_name.strip():
        st.warning("Please enter the food name.")

    elif expiry_date < purchase_date:
        st.error("Expiry date cannot be before purchase date.")

    else:
        connection = None
        cursor = None

        try:
            connection = get_connection()
            cursor = connection.cursor()

            cursor.execute(
                """
                INSERT INTO food_items
                (food_name, quantity, purchase_date, expiry_date, barcode, user_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    food_name.strip(),
                    quantity,
                    purchase_date,
                    expiry_date,
                    barcode.strip() or None,
                    user_id
                )
            )

            connection.commit()
            st.success("✅ Food item added successfully!")
            st.rerun()

        except Exception as e:
            st.error(f"Database error: {e}")

        finally:
            close_connection(connection, cursor)


# ---------------- FETCH USER FOOD ITEMS ----------------

food_items = []
connection = None
cursor = None

try:
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT *
        FROM food_items
        WHERE user_id = %s
        ORDER BY expiry_date ASC
        """,
        (user_id,)
    )

    food_items = cursor.fetchall()

except Exception as e:
    st.error(f"Database error: {e}")

finally:
    close_connection(connection, cursor)


# ---------------- CAMERA BARCODE SCANNER ----------------

st.divider()
st.header("📷 Scan Food Barcode")

st.write(
    "Allow camera access, capture the barcode, and the system will "
    "try to find the matching food item."
)

if not BARCODE_SCANNER_AVAILABLE:
    st.warning(
        "Camera barcode scanning is unavailable. "
        "Please install OpenCV with: python -m pip install opencv-contrib-python"
    )
else:
    camera_photo = st.camera_input("Capture barcode")

    if camera_photo is not None:
        try:
            image_bytes = camera_photo.getvalue()
            image_array = np.frombuffer(image_bytes, dtype=np.uint8)
            frame = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

            detector = cv2.barcode_BarcodeDetector()
            result = detector.detectAndDecode(frame)

            # OpenCV versions can return slightly different result formats.
            decoded_values = []

            if isinstance(result, tuple):
                for value in result:
                    if isinstance(value, str) and value.strip():
                        decoded_values.append(value.strip())
                    elif isinstance(value, (list, tuple)):
                        decoded_values.extend(
                            str(item).strip()
                            for item in value
                            if isinstance(item, str) and item.strip()
                        )
            elif isinstance(result, str) and result.strip():
                decoded_values.append(result.strip())

            # Remove duplicate values while preserving order.
            decoded_values = list(dict.fromkeys(decoded_values))

            if not decoded_values:
                st.warning(
                    "No barcode detected. Keep the barcode clear, "
                    "well-lit, horizontal, and inside the camera frame."
                )
            else:
                scanned_value = decoded_values[0]
                st.session_state["scanned_barcode"] = scanned_value
                st.success(f"✅ Barcode detected: {scanned_value}")

                matching_items = [
                    item for item in food_items
                    if str(item.get("barcode") or "").strip() == scanned_value
                ]

                if matching_items:
                    st.subheader("🔎 Matching Food Item")

                    for matched_item in matching_items:
                        matched_status, matched_label, matched_message = get_status(
                            matched_item["expiry_date"],
                            date.today()
                        )

                        st.info(
                            f"🍎 {matched_item['food_name']}\n\n"
                            f"📦 Quantity: {matched_item['quantity']}\n\n"
                            f"📅 Expiry Date: {matched_item['expiry_date']}\n\n"
                            f"{matched_label} — {matched_message}"
                        )
                else:
                    st.warning(
                        "Barcode detected, but no matching food item was found "
                        "in your account. Add this barcode to a food item first."
                    )

        except Exception as error:
            st.error(f"Barcode scanning error: {error}")

# ---------------- CLASSIFY ITEMS ----------------

today = date.today()

expired_items = []
today_items = []
soon_items = []
week_items = []
fresh_items = []

for item in food_items:
    days_left = (item["expiry_date"] - today).days

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


# ---------------- DASHBOARD ----------------

st.divider()
st.header("📊 Dashboard")

dashboard1, dashboard2, dashboard3, dashboard4 = st.columns(4)

with dashboard1:
    st.metric("📦 Total Items", len(food_items))

with dashboard2:
    st.metric("🔴 Expired", len(expired_items))

with dashboard3:
    st.metric(
        "🟠 Expiring Soon",
        len(today_items) + len(soon_items)
    )

with dashboard4:
    st.metric("🟢 Fresh", len(fresh_items))


# ---------------- EXPIRY ALERTS ----------------

st.divider()
st.header("🚨 Expiry Alerts")

if expired_items:
    st.error(f"🔴 {len(expired_items)} item(s) have expired.")

    for item in expired_items:
        days = (today - item["expiry_date"]).days
        st.write(
            f"🔴 **{item['food_name']}** — expired {days} day(s) ago."
        )

if today_items:
    st.warning(f"⚠️ {len(today_items)} item(s) expire today.")

    for item in today_items:
        st.write(
            f"🔴 **{item['food_name']}** — expires today."
        )

if soon_items:
    st.warning(
        f"🟠 {len(soon_items)} item(s) expire within 3 days."
    )

    for item in soon_items:
        days = (item["expiry_date"] - today).days
        st.write(
            f"🟠 **{item['food_name']}** — {days} day(s) remaining."
        )

if week_items:
    st.info(
        f"🟡 {len(week_items)} item(s) expire within 7 days."
    )

    for item in week_items:
        days = (item["expiry_date"] - today).days
        st.write(
            f"🟡 **{item['food_name']}** — {days} day(s) remaining."
        )

if not expired_items and not today_items and not soon_items and not week_items:
    if food_items:
        st.success("✅ No food items are expiring within 7 days.")
    else:
        st.info("📭 Add food items to receive expiry alerts.")


# ---------------- EMAIL EXPIRY REPORT ----------------

st.divider()
st.header("📧 Email Expiry Report")

st.write(
    "Send an email containing food items "
    "that are expired or expiring within 7 days."
)

if st.button(
    "📧 Send Expiry Report by Email",
    use_container_width=True
):
    receiver_email = get_user_email(user_id)

    if not receiver_email:
        st.warning(
            "Please save your notification email in the sidebar first."
        )
    else:
        with st.spinner("Sending email..."):
            success, email_message = send_expiry_email(
                food_items,
                today,
                receiver_email
            )

        if success:
            st.success(email_message)
        else:
            st.warning(email_message)


# ---------------- DOWNLOAD REPORT ----------------

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
            "Status": status
        })

    report_df = pd.DataFrame(report_data)
    csv_file = report_df.to_csv(index=False)

    st.download_button(
        label="📥 Download CSV Report",
        data=csv_file,
        file_name="food_expiry_report.csv",
        mime="text/csv",
        use_container_width=True
    )

else:
    st.info("Add food items to download a report.")


# ---------------- FOOD EXPIRY ANALYTICS ----------------

st.divider()
st.header("📊 Food Expiry Analytics")

if food_items:

    analytics_data = []

    for item in food_items:
        status, _, _ = get_status(item["expiry_date"], today)

        analytics_data.append({
            "Food Name": item["food_name"],
            "Status": status
        })

    analytics_df = pd.DataFrame(analytics_data)

    status_order = [
        "Expired",
        "Expires Today",
        "Expiring Soon",
        "Expiring This Week",
        "Fresh"
    ]

    status_count = (
        analytics_df["Status"]
        .value_counts()
        .reindex(status_order, fill_value=0)
    )

    st.subheader("📈 Food Items by Expiry Status")
    st.bar_chart(status_count)

    st.subheader("📋 Status Summary")

    summary_df = status_count.reset_index()
    summary_df.columns = ["Status", "Number of Items"]

    st.dataframe(
        summary_df,
        use_container_width=True,
        hide_index=True
    )

else:
    st.info("Add food items to view analytics.")


# ---------------- SEARCH AND FILTER ----------------

st.divider()
st.header("🔍 Search & Filter")

search_col, filter_col = st.columns(2)

with search_col:
    search_text = st.text_input(
        "Search food by name",
        placeholder="Example: Milk"
    )

with filter_col:
    filter_status = st.selectbox(
        "Filter by status",
        [
            "All",
            "Expired",
            "Expires Today",
            "Expiring Soon",
            "Expiring This Week",
            "Fresh"
        ]
    )


filtered_items = []

for item in food_items:

    if search_text.lower() not in item["food_name"].lower():
        continue

    item_status, _, _ = get_status(item["expiry_date"], today)

    if filter_status != "All" and item_status != filter_status:
        continue

    filtered_items.append(item)


# ---------------- DISPLAY FOOD ITEMS ----------------

st.divider()
st.header("📋 Your Food Items")

if not filtered_items:

    st.info("📭 No matching food items found.")

else:

    for item in filtered_items:

        item_status, display_status, message = get_status(
            item["expiry_date"],
            today
        )

        with st.container(border=True):

            item_col1, item_col2, item_col3 = st.columns(3)

            with item_col1:
                st.subheader(f"🍎 {item['food_name']}")
                st.write(f"📦 Quantity: {item['quantity']}")
                st.write(f"📦 Barcode: {item.get('barcode') or 'Not added'}")

            with item_col2:
                st.write(
                    f"🛒 Purchase Date: {item['purchase_date']}"
                )
                st.write(
                    f"📅 Expiry Date: {item['expiry_date']}"
                )

            with item_col3:
                st.write(f"### {display_status}")
                st.write(message)

            edit_col, delete_col = st.columns(2)

            with edit_col:
                if st.button(
                    "✏️ Edit",
                    key=f"edit_{item['id']}",
                    use_container_width=True
                ):
                    st.session_state[
                        f"editing_{item['id']}"
                    ] = True

            with delete_col:
                if st.button(
                    "🗑️ Delete",
                    key=f"delete_{item['id']}",
                    use_container_width=True
                ):

                    connection = None
                    cursor = None

                    try:
                        connection = get_connection()
                        cursor = connection.cursor()

                        cursor.execute(
                            """
                            DELETE FROM food_items
                            WHERE id = %s AND user_id = %s
                            """,
                            (item["id"], user_id)
                        )

                        connection.commit()
                        st.success("✅ Food item deleted!")
                        st.rerun()

                    except Exception as e:
                        st.error(f"Delete error: {e}")

                    finally:
                        close_connection(connection, cursor)

            # ---------------- EDIT FORM ----------------

            if st.session_state.get(
                f"editing_{item['id']}",
                False
            ):

                st.divider()
                st.subheader("✏️ Edit Food Item")

                edit_col1, edit_col2 = st.columns(2)

                with edit_col1:
                    new_name = st.text_input(
                        "Food Name",
                        value=item["food_name"],
                        key=f"name_{item['id']}"
                    )

                    new_quantity = st.number_input(
                        "Quantity",
                        min_value=1,
                        value=int(item["quantity"]),
                        key=f"quantity_{item['id']}"
                    )

                    new_barcode = st.text_input(
                        "📦 Barcode Number",
                        value=item.get("barcode") or "",
                        key=f"barcode_{item['id']}"
                    )

                with edit_col2:
                    new_purchase_date = st.date_input(
                        "Purchase Date",
                        value=item["purchase_date"],
                        key=f"purchase_{item['id']}"
                    )

                    new_expiry_date = st.date_input(
                        "Expiry Date",
                        value=item["expiry_date"],
                        key=f"expiry_{item['id']}"
                    )

                save_col, cancel_col = st.columns(2)

                with save_col:

                    if st.button(
                        "💾 Save Changes",
                        key=f"save_{item['id']}",
                        use_container_width=True
                    ):

                        if not new_name.strip():
                            st.warning("Please enter a food name.")

                        elif new_expiry_date < new_purchase_date:
                            st.error(
                                "Expiry date cannot be before purchase date."
                            )

                        else:

                            connection = None
                            cursor = None

                            try:
                                connection = get_connection()
                                cursor = connection.cursor()

                                cursor.execute(
                                    """
                                    UPDATE food_items
                                    SET food_name = %s,
                                        quantity = %s,
                                        purchase_date = %s,
                                        expiry_date = %s,
                                        barcode = %s
                                    WHERE id = %s AND user_id = %s
                                    """,
                                    (
                                        new_name.strip(),
                                        new_quantity,
                                        new_purchase_date,
                                        new_expiry_date,
                                        new_barcode.strip() or None,
                                        item["id"],
                                        user_id
                                    )
                                )

                                connection.commit()

                                st.session_state[
                                    f"editing_{item['id']}"
                                ] = False

                                st.success("✅ Food item updated!")
                                st.rerun()

                            except Exception as e:
                                st.error(f"Update error: {e}")

                            finally:
                                close_connection(connection, cursor)

                with cancel_col:

                    if st.button(
                        "❌ Cancel",
                        key=f"cancel_{item['id']}",
                        use_container_width=True
                    ):

                        st.session_state[
                            f"editing_{item['id']}"
                        ] = False

                        st.rerun()


# ---------------- FOOTER ----------------

st.divider()

st.markdown(
    """
    <div style="text-align:center;">
        <p>🍎 <b>Food Expiry Tracking System</b></p>
        <p>Built using Python • Streamlit • MySQL</p>
    </div>
    """,
    unsafe_allow_html=True
)