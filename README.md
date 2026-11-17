# FitTrack – Fitness & Health Tracker

FitTrack contains two applications:

- **Python/MySQL console application:** the original command-line program in `main.py` and `database.py` for managing users and fitness records. Its features and source are preserved below.
- **Flask/React web application:** a personal account-based app for goals, health metrics, activity tracking, history, and account settings. See [README_WEB.md](README_WEB.md) for web setup and configuration.

## Original console application

## Features

- Add a new user
- View all users
- Search user by ID
- Update user information
- Delete user
- Calculate BMI
- Calculate estimated daily calorie requirement
- Add fitness records
- View all fitness records
- View fitness records for a specific user
- Basic input validation
- MySQL database integration

## Technologies Used

- Python
- MySQL
- MySQL Connector for Python
- python-dotenv

## Database

FitTrack uses MySQL to store user information and fitness records.

### Tables

#### users

Stores:

- User ID
- Name
- Age
- Gender
- Height
- Weight
- BMI
- Estimated daily calories

#### fitness_records

Stores:

- Record ID
- User ID
- Record date
- Steps
- Distance
- Workout minutes
- Calories burned

The `user_id` connects fitness records with the corresponding user.

## Original console project structure

The current repository also contains `backend/` (Flask API and migrations), `frontend/` (React/Vite), and `README_WEB.md`. The real `.env` is local configuration and must not be committed; `.env.example` is the safe local template.

```text
FitTrack/
│
├── .gitignore
├── database.py
├── main.py
├── README.md
├── requirements.txt
└── .env
