from database import create_connection


# ==========================================
# Add a new user
# ==========================================
def add_user():

    try:
        name = input("Enter your name: ").strip()

        age = int(input("Enter your age: "))

        if age <= 0:
            print("\nAge must be greater than 0.")
            return

        gender = input("Enter your gender: ").strip()

        height = float(input("Enter your height in meters: "))

        if height <= 0:
            print("\nHeight must be greater than 0.")
            return

        weight = float(input("Enter your weight in kg: "))

        if weight <= 0:
            print("\nWeight must be greater than 0.")
            return

    except ValueError:
        print("\nPlease enter valid numbers.")
        return

    # Calculate BMI
    bmi = weight / (height * height)

    # Convert height to centimeters
    height_cm = height * 100

    # Calculate BMR
    if gender.lower() == "male":
        bmr = (10 * weight) + (6.25 * height_cm) - (5 * age) + 5
    else:
        bmr = (10 * weight) + (6.25 * height_cm) - (5 * age) - 161

    # Estimate daily calories
    daily_calories = bmr * 1.2

    connection = create_connection()
    cursor = connection.cursor()

    query = """
        INSERT INTO users
        (name, age, gender, height, weight, bmi, daily_calories)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """

    values = (
        name,
        age,
        gender,
        height,
        weight,
        bmi,
        daily_calories
    )

    cursor.execute(query, values)
    connection.commit()

    print("\nUser added successfully!")
    print("BMI:", round(bmi, 2))
    print("Estimated Daily Calories:", round(daily_calories))

    cursor.close()
    connection.close()


# ==========================================
# View all users
# ==========================================
def view_users():

    connection = create_connection()
    cursor = connection.cursor()

    query = "SELECT * FROM users"
    cursor.execute(query)

    users = cursor.fetchall()

    if not users:
        print("\nNo users found.")

    else:
        print("\n===== All Users =====")

        for user in users:
            print(user)

    cursor.close()
    connection.close()


# ==========================================
# Search user by ID
# ==========================================
def search_user():

    try:
        user_id = int(input("Enter user ID to search: "))

    except ValueError:
        print("\nPlease enter a valid user ID.")
        return

    connection = create_connection()
    cursor = connection.cursor()

    query = """
        SELECT * FROM users
        WHERE user_id = %s
    """

    cursor.execute(query, (user_id,))

    user = cursor.fetchone()

    if user:

        print("\n===== User Found =====")
        print("User ID:", user[0])
        print("Name:", user[1])
        print("Age:", user[2])
        print("Gender:", user[3])
        print("Height:", user[4], "m")
        print("Weight:", user[5], "kg")
        print("BMI:", round(user[6], 2))
        print("Daily Calories:", round(user[7]))

    else:
        print("\nUser not found.")

    cursor.close()
    connection.close()


# ==========================================
# Update user
# ==========================================
def update_user():

    try:
        user_id = int(input("Enter user ID to update: "))

        name = input("Enter new name: ").strip()

        age = int(input("Enter new age: "))

        if age <= 0:
            print("\nAge must be greater than 0.")
            return

        gender = input("Enter new gender: ").strip()

        height = float(input("Enter new height in meters: "))

        if height <= 0:
            print("\nHeight must be greater than 0.")
            return

        weight = float(input("Enter new weight in kg: "))

        if weight <= 0:
            print("\nWeight must be greater than 0.")
            return

    except ValueError:
        print("\nPlease enter valid values.")
        return

    # Calculate BMI
    bmi = weight / (height * height)

    # Convert height to centimeters
    height_cm = height * 100

    # Calculate BMR
    if gender.lower() == "male":
        bmr = (10 * weight) + (6.25 * height_cm) - (5 * age) + 5
    else:
        bmr = (10 * weight) + (6.25 * height_cm) - (5 * age) - 161

    # Calculate estimated calories
    daily_calories = bmr * 1.2

    connection = create_connection()
    cursor = connection.cursor()

    query = """
        UPDATE users
        SET name = %s,
            age = %s,
            gender = %s,
            height = %s,
            weight = %s,
            bmi = %s,
            daily_calories = %s
        WHERE user_id = %s
    """

    values = (
        name,
        age,
        gender,
        height,
        weight,
        bmi,
        daily_calories,
        user_id
    )

    cursor.execute(query, values)
    connection.commit()

    if cursor.rowcount > 0:

        print("\nUser updated successfully!")
        print("New BMI:", round(bmi, 2))
        print("New Estimated Daily Calories:", round(daily_calories))

    else:
        print("\nUser not found.")

    cursor.close()
    connection.close()


# ==========================================
# Delete user
# ==========================================
def delete_user():

    try:
        user_id = int(input("Enter user ID to delete: "))

    except ValueError:
        print("\nPlease enter a valid user ID.")
        return

    connection = create_connection()
    cursor = connection.cursor()

    # Check whether user exists
    check_query = """
        SELECT * FROM users
        WHERE user_id = %s
    """

    cursor.execute(check_query, (user_id,))
    user = cursor.fetchone()

    if not user:

        print("\nUser not found.")

    else:

        print("\n===== User Found =====")
        print("Name:", user[1])
        print("Age:", user[2])
        print("Weight:", user[5], "kg")

        confirmation = input(
            "Are you sure you want to delete this user? (yes/no): "
        )

        if confirmation.lower() == "yes":

            # Delete fitness records first
            delete_records_query = """
                DELETE FROM fitness_records
                WHERE user_id = %s
            """

            cursor.execute(delete_records_query, (user_id,))

            # Delete user
            delete_user_query = """
                DELETE FROM users
                WHERE user_id = %s
            """

            cursor.execute(delete_user_query, (user_id,))

            connection.commit()

            print("\nUser deleted successfully!")

        else:
            print("\nDelete operation cancelled.")

    cursor.close()
    connection.close()


# ==========================================
# Add fitness record
# ==========================================
def add_fitness_record():

    try:
        user_id = int(input("Enter user ID: "))

        record_date = input("Enter date (YYYY-MM-DD): ").strip()

        steps = int(input("Enter steps: "))

        if steps < 0:
            print("\nSteps cannot be negative.")
            return

        distance = float(input("Enter distance in km: "))

        if distance < 0:
            print("\nDistance cannot be negative.")
            return

        workout_minutes = int(input("Enter workout minutes: "))

        if workout_minutes < 0:
            print("\nWorkout minutes cannot be negative.")
            return

        calories_burned = float(input("Enter calories burned: "))

        if calories_burned < 0:
            print("\nCalories burned cannot be negative.")
            return

    except ValueError:
        print("\nPlease enter valid values.")
        return

    connection = create_connection()
    cursor = connection.cursor()

    query = """
        INSERT INTO fitness_records
        (user_id, record_date, steps, distance, workout_minutes, calories_burned)
        VALUES (%s, %s, %s, %s, %s, %s)
    """

    values = (
        user_id,
        record_date,
        steps,
        distance,
        workout_minutes,
        calories_burned
    )

    cursor.execute(query, values)
    connection.commit()

    print("\nFitness record added successfully!")

    cursor.close()
    connection.close()


# ==========================================
# View all fitness records
# ==========================================
def view_fitness_records():

    connection = create_connection()
    cursor = connection.cursor()

    query = "SELECT * FROM fitness_records"
    cursor.execute(query)

    records = cursor.fetchall()

    if not records:

        print("\nNo fitness records found.")

    else:

        print("\n===== All Fitness Records =====")

        for record in records:
            print(record)

    cursor.close()
    connection.close()


# ==========================================
# View fitness records for a specific user
# ==========================================
def view_user_fitness_records():

    try:
        user_id = int(input("Enter user ID: "))

    except ValueError:
        print("\nPlease enter a valid user ID.")
        return

    connection = create_connection()
    cursor = connection.cursor()

    query = """
        SELECT *
        FROM fitness_records
        WHERE user_id = %s
    """

    cursor.execute(query, (user_id,))

    records = cursor.fetchall()

    if not records:

        print("\nNo fitness records found for this user.")

    else:

        print("\n===== User Fitness Records =====")

        for record in records:
            print(record)

    cursor.close()
    connection.close()


# ==========================================
# Main Menu
# ==========================================
while True:

    print("\n========== FITTRACK ==========")
    print("1. Add User")
    print("2. View Users")
    print("3. Search User")
    print("4. Update User")
    print("5. Delete User")
    print("6. Add Fitness Record")
    print("7. View All Fitness Records")
    print("8. View User Fitness Records")
    print("9. Exit")

    choice = input("Enter your choice: ")

    if choice == "1":
        add_user()

    elif choice == "2":
        view_users()

    elif choice == "3":
        search_user()

    elif choice == "4":
        update_user()

    elif choice == "5":
        delete_user()

    elif choice == "6":
        add_fitness_record()

    elif choice == "7":
        view_fitness_records()

    elif choice == "8":
        view_user_fitness_records()

    elif choice == "9":
        print("\nThank you for using FitTrack!")
        break

    else:
        print("\nInvalid choice. Please try again.")