# FitTrack – Fitness & Health Tracker

FitTrack is a console-based fitness and health tracking application built using Python and MySQL.

The application allows users to manage their basic health information and record their daily fitness activities.

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

## Project Structure

```text
FitTrack/
│
├── .gitignore
├── database.py
├── main.py
├── README.md
├── requirements.txt
└── .env