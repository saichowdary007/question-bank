from db import delete_all_questions, client

def main():
    """Connects to the database and deletes all questions."""
    print("Connecting to the database...")
    try:
        # Check if the server is available
        client.server_info()
        print("Database connection successful.")
    except Exception as e:
        print(f"Database connection failed: {e}")
        print("Please ensure your MongoDB server is running.")
        return

    confirm = input("Are you sure you want to delete all questions from the database? (y/n): ")
    if confirm.lower() != 'y':
        print("Operation cancelled.")
        return

    print("Attempting to delete all questions...")
    try:
        deleted_count = delete_all_questions()
        print(f"✅ Successfully deleted {deleted_count} questions from the 'questions' collection.")
    except Exception as e:
        print(f"❌ An error occurred while deleting questions: {e}")
    finally:
        client.close()
        print("Database connection closed.")

if __name__ == "__main__":
    main() 