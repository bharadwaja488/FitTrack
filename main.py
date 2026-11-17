from database import create_connection
from math import isfinite


def _read_number(prompt, label, minimum, maximum, integer=False):
    raw = input(prompt).strip()
    try:
        value = int(raw) if integer else float(raw)
    except ValueError:
        kind = "a whole number" if integer else "a number"
        raise ValueError(f"{label} must be {kind}.")
    try:
        finite = isfinite(float(value))
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError(f"{label} must be a finite number.")
    if value < minimum or value > maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}.")
    return value


# ==========================================
# Add a new user
# ==========================================
def add_user():

    try:
        name = input("Enter your name: ").strip()

        age = _read_number("Enter your age: ", "Age", 1, 120, integer=True)

        gender = input("Enter your gender: ").strip()
        if gender.lower() not in {"male", "female"}:
            print("\nGender must be Male or Female.")
            return

        height = _read_number("Enter your height in meters: ", "Height", 0.01, 3)
        weight = _read_number("Enter your weight in kg: ", "Weight", 1, 500)

    except ValueError as error:
        print(f"\n{error}")
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

        age = _read_number("Enter new age: ", "Age", 1, 120, integer=True)

        gender = input("Enter new gender: ").strip()
        if gender.lower() not in {"male", "female"}:
            print("\nGender must be Male or Female.")
            return
        height = _read_number("Enter new height in meters: ", "Height", 0.01, 3)
        weight = _read_number("Enter new weight in kg: ", "Weight", 1, 500)

    except ValueError as error:
        print(f"\n{error}")
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

    conn = create_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        user = cursor.fetchone()
        if not user:
            print("\nUser not found.")
            return

        # account_id exists after the web-app migration. Checking the column
        # keeps the original console usable on an unmigrated legacy database.
        cursor.execute("SHOW COLUMNS FROM users LIKE %s", ("account_id",))
        has_account_column = cursor.fetchone() is not None
        if has_account_column:
            cursor.execute("SELECT account_id FROM users WHERE user_id = %s", (user_id,))
            ownership = cursor.fetchone()
            if ownership and ownership[0] is not None:
                conn.rollback()
                print("\nThis profile belongs to a FitTrack web account. No changes were made.")
                print("The account owner must delete it from the website Settings page.")
                return

        # Finish the display-only read transaction before waiting for input.
        # Ownership is checked again under a row lock immediately before writes.
        conn.commit()

        print("\n===== User Found =====")
        print("Name:", user[1])
        print("Age:", user[2])
        print("Weight:", user[5], "kg")
        confirmation = input("Are you sure you want to delete this user? (yes/no): ")
        if confirmation.lower() != "yes":
            conn.rollback()
            print("\nDelete operation cancelled.")
            return

        try:
            if has_account_column:
                cursor.execute("SELECT account_id FROM users WHERE user_id = %s FOR UPDATE", (user_id,))
                locked_profile = cursor.fetchone()
                if locked_profile is None:
                    conn.rollback()
                    print("\nUser not found. No changes were made.")
                    return
                if locked_profile[0] is not None:
                    conn.rollback()
                    print("\nThis profile now belongs to a FitTrack web account. No changes were made.")
                    print("The account owner must delete it from the website Settings page.")
                    return
            else:
                cursor.execute("SELECT user_id FROM users WHERE user_id = %s FOR UPDATE", (user_id,))
                if cursor.fetchone() is None:
                    conn.rollback()
                    print("\nUser not found. No changes were made.")
                    return

            cursor.execute("DELETE FROM fitness_records WHERE user_id = %s", (user_id,))
            cursor.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
            conn.commit()
            print("\nUser deleted successfully!")
        except Exception:
            conn.rollback()
            print("\nThe user could not be deleted because related records still exist. No changes were made.")
    except Exception:
        conn.rollback()
        print("\nThe user could not be deleted. No changes were made.")
    finally:
        cursor.close()
        conn.close()


# ==========================================
# Add fitness record
# ==========================================
def add_fitness_record():

    try:
        user_id = int(input("Enter user ID: "))

        record_date = input("Enter date (YYYY-MM-DD): ").strip()

        steps = _read_number("Enter steps: ", "Steps", 0, 200000, integer=True)
        distance = _read_number("Enter distance in km: ", "Distance", 0, 1000)
        workout_minutes = _read_number("Enter workout minutes: ", "Workout minutes", 0, 1440, integer=True)
        calories_burned = _read_number("Enter calories burned: ", "Calories burned", 0, 10000)

    except ValueError as error:
        print(f"\n{error}")
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
def main():
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


if __name__ == "__main__":
    main()
