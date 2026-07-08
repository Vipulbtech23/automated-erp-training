import streamlit as st
import pandas as pd
from firebase_admin import firestore


def normalize_email(email):
    return str(email).strip().lower()


def create_notification(db, email, title, message, notif_type="info"):
    email = normalize_email(email)

    db.collection("notifications").document().set({
        "email": email,
        "title": title,
        "message": message,
        "type": notif_type,
        "is_read": False,
        "created_at": firestore.SERVER_TIMESTAMP
    })


def create_bulk_notification(db, emails, title, message, notif_type="info"):
    count = 0

    for email in emails:
        if str(email).strip() and str(email).lower() != "nan":
            create_notification(db, email, title, message, notif_type)
            count += 1

    return count


def get_student_notifications(db, email):
    email = normalize_email(email)

    docs = (
        db.collection("notifications")
        .where("email", "==", email)
        .stream()
    )

    rows = []

    for d in docs:
        data = d.to_dict()
        rows.append({
            "id": d.id,
            "title": data.get("title", ""),
            "message": data.get("message", ""),
            "type": data.get("type", "info"),
            "is_read": data.get("is_read", False),
            "created_at": data.get("created_at")
        })

    rows = sorted(rows, key=lambda x: str(x["created_at"]), reverse=True)

    return rows


def mark_notification_read(db, notif_id):
    db.collection("notifications").document(notif_id).update({
        "is_read": True
    })


def student_notification_panel(db, student):
    st.title("🔔 Notifications")

    email = normalize_email(student["Email"])
    notifications = get_student_notifications(db, email)

    if not notifications:
        st.info("No notifications yet.")
        return

    unread = len([n for n in notifications if not n["is_read"]])
    st.metric("Unread Notifications", unread)

    for n in notifications:
        status = "🟢 Unread" if not n["is_read"] else "⚪ Read"

        st.markdown("---")
        st.subheader(f"{status} — {n['title']}")
        st.write(n["message"])
        st.caption(f"Type: {n['type']} | Time: {n['created_at']}")

        if not n["is_read"]:
            if st.button("Mark as Read", key=n["id"]):
                mark_notification_read(db, n["id"])
                st.success("Marked as read")
                st.rerun()


def admin_notification_panel(db, df):
    st.title("📢 Admin Notification Center")

    tab1, tab2 = st.tabs(["📨 Send Notification", "📋 Notification Logs"])

    with tab1:
        target = st.radio("Send To", ["All Students", "Selected Student"])

        title = st.text_input("Notification Title", "Important Update")
        message = st.text_area("Notification Message", "Please check your dashboard.")
        notif_type = st.selectbox(
            "Notification Type",
            ["info", "quiz", "report", "attendance", "warning", "success"]
        )

        if target == "Selected Student":
            student_name = st.selectbox("Select Student", df["Name"])
            email = df[df["Name"] == student_name].iloc[0]["Email"]

            if st.button("Send Notification"):
                create_notification(db, email, title, message, notif_type)
                st.success(f"Notification sent to {student_name}")

        else:
            if st.button("Send To All Students"):
                emails = df["Email"].astype(str).str.strip().str.lower().tolist()
                count = create_bulk_notification(db, emails, title, message, notif_type)
                st.success(f"Notification sent to {count} students")

    with tab2:
        docs = db.collection("notifications").stream()

        rows = []

        for d in docs:
            data = d.to_dict()
            rows.append({
                "Email": data.get("email"),
                "Title": data.get("title"),
                "Message": data.get("message"),
                "Type": data.get("type"),
                "Read": data.get("is_read"),
                "Created At": str(data.get("created_at"))
            })

        if rows:
            log_df = pd.DataFrame(rows)
            st.dataframe(log_df, use_container_width=True)

            st.download_button(
                "⬇ Download Notification Logs",
                log_df.to_csv(index=False).encode("utf-8"),
                "notification_logs.csv",
                "text/csv"
            )
        else:
            st.info("No notifications found.")