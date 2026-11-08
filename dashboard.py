import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, timedelta
from dotenv import load_dotenv
from ai_coach import ask_fittrack_ai
from fittrack_core import *

load_dotenv()
st.set_page_config(page_title="FitTrack", page_icon="🏃", layout="wide")
st.title("🏃 FitTrack")
st.caption("Fitness, health habits and personal progress dashboard")

try:
    ensure_upgrade_tables()
    users = get_users()
except Exception as exc:
    st.error("MySQL connection failed. Check that MySQL is running and your .env settings are correct.")
    st.code("DB_HOST=localhost\nDB_USER=root\nDB_PASSWORD=your_password\nDB_NAME=fittrack")
    st.exception(exc)
    st.stop()

with st.sidebar:
    st.header("Profile")
    with st.expander("Create profile"):
        with st.form("new_user"):
            name = st.text_input("Name")
            age = st.number_input("Age", 18, 100, 22)
            gender = st.selectbox("Gender for BMR estimate", ["Male", "Female"])
            height = st.number_input("Height (cm)", 100.0, 230.0, 170.0)
            weight = st.number_input("Weight (kg)", 25.0, 300.0, 70.0)
            submit = st.form_submit_button("Create profile")
        if submit:
            try:
                uid = create_user(name, int(age), gender, height / 100, weight)
                save_weight(uid, date.today(), weight)
                st.success("Profile created.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    if not users:
        st.info("Create your first profile to continue.")
        st.stop()
    mapping = {f"{u['name']} (ID {u['user_id']})": u for u in users}
    user = mapping[st.selectbox("Choose profile", list(mapping))]
    activity_level = st.selectbox("Activity level", list(ACTIVITY_FACTORS))

uid = int(user["user_id"])
bmi = calculate_bmi(float(user["weight"]), float(user["height"]))
bmr = calculate_bmr(int(user["age"]), str(user["gender"]), float(user["weight"]), float(user["height"]))
tdee = calculate_daily_calories(bmr, activity_level)
records = get_fitness_records(uid)
habits = get_health_logs(uid)
weights = get_weight_history(uid)
goals = get_goals(uid)

a, b, c, d = st.columns(4)
a.metric("BMI estimate", f"{bmi:.1f}")
b.metric("BMR estimate", f"{bmr:,.0f} kcal/day")
c.metric("Daily energy estimate", f"{tdee:,.0f} kcal/day")
d.metric("Activity records", len(records))
st.caption(f"BMI reference: {bmi_category(bmi)}. BMI and calorie figures are estimates, not diagnoses.")

t_overview, t_activity, t_habits, t_goals, t_ai = st.tabs(["Overview", "Activity", "Health habits", "Goals", "AI Coach"])

with t_overview:
    st.subheader("Progress overview")
    df = pd.DataFrame(records)
    if not df.empty:
        df["record_date"] = pd.to_datetime(df["record_date"])
        x, y = st.columns(2)
        x.plotly_chart(px.bar(df.sort_values("record_date"), x="record_date", y="steps", title="Daily steps"), use_container_width=True)
        y.plotly_chart(px.line(df.sort_values("record_date"), x="record_date", y="workout_minutes", markers=True, title="Workout minutes"), use_container_width=True)
        st.dataframe(df.sort_values("record_date", ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info("No activity records yet. Add your first record in Activity.")
    wdf = pd.DataFrame(weights)
    if not wdf.empty:
        wdf["log_date"] = pd.to_datetime(wdf["log_date"])
        st.plotly_chart(px.line(wdf.sort_values("log_date"), x="log_date", y="weight_kg", markers=True, title="Weight history"), use_container_width=True)

with t_activity:
    st.subheader("Log activity")
    with st.form("activity_form"):
        day = st.date_input("Date", date.today())
        steps = st.number_input("Steps", min_value=0, value=0, step=500)
        distance = st.number_input("Distance (km)", min_value=0.0, value=0.0)
        minutes = st.number_input("Workout minutes", min_value=0, value=0, step=5)
        burned = st.number_input("Estimated calories burned", min_value=0.0, value=0.0)
        save = st.form_submit_button("Save activity")
    if save:
        try:
            add_fitness_record(uid, day, int(steps), float(distance), int(minutes), float(burned))
            st.success("Activity saved.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

with t_habits:
    st.subheader("Daily health habits")
    with st.form("habit_form"):
        day = st.date_input("Log date", date.today())
        water = st.number_input("Water / fluids (ml)", min_value=0, value=0, step=250)
        sleep = st.number_input("Sleep (hours)", min_value=0.0, max_value=24.0, value=0.0, step=0.5)
        mood = st.selectbox("Mood", ["Not recorded", "Good", "Okay", "Low energy", "Stressed"])
        notes = st.text_area("Notes")
        save = st.form_submit_button("Save habits")
    if save:
        try:
            save_health_log(uid, day, int(water), float(sleep), "" if mood == "Not recorded" else mood, notes)
            st.success("Habit log saved.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    st.subheader("Record weight")
    with st.form("weight_form"):
        day = st.date_input("Weight date", date.today(), key="weight_date")
        kg = st.number_input("Weight (kg)", min_value=25.0, max_value=300.0, value=float(user["weight"]))
        save = st.form_submit_button("Save weight")
    if save:
        try:
            save_weight(uid, day, float(kg))
            st.success("Weight saved.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if habits:
        st.dataframe(pd.DataFrame(habits), use_container_width=True, hide_index=True)

with t_goals:
    st.subheader("Fitness goals")
    with st.form("goal_form"):
        kind = st.selectbox("Goal type", ["Daily steps", "Water intake (ml)", "Workout minutes", "Target weight (kg)"])
        target = st.number_input("Target value", min_value=0.1, value=8000.0)
        deadline = st.date_input("Target date", date.today() + timedelta(days=30))
        save = st.form_submit_button("Add goal")
    if save:
        try:
            create_goal(uid, kind, float(target), deadline)
            st.success("Goal created.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    for goal in goals:
        x, y = st.columns([4, 1])
        x.write(f"{goal['goal_type']}: {goal['target_value']} by {goal['target_date']} ({goal['status']})")
        if goal["status"] == "active" and y.button("Complete", key=f"goal_{goal['goal_id']}"):
            update_goal_status(int(goal["goal_id"]), "completed")
            st.rerun()

with t_ai:
    st.subheader("FitTrack AI Coach")
    st.info("General fitness education only. Not medical diagnosis or treatment.")
    question = st.text_area("Ask about your habits or activity", max_chars=1200)
    if st.button("Ask FitTrack AI", disabled=not question.strip()):
        context = f"Age {user['age']}; height {user['height']}m; weight {user['weight']}kg; BMI {bmi:.1f}; BMR {bmr:.0f}; estimated daily energy {tdee:.0f}; recent activities {records[:10]}; habits {habits[:10]}; goals {goals}."
        with st.spinner("Preparing response..."):
            answer, provider = ask_fittrack_ai(question, context)
        st.write(answer)
        st.caption(f"Response source: {provider}")

st.divider()
st.caption("FitTrack is an educational tracker. BMI, BMR, calorie and activity values are estimates.")