import subprocess
import os

def run_frontend():
    # Set working directory to the frontend folder
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    # Check for node_modules
    if not os.path.exists("node_modules"):
        print(">>> node_modules not found. Installing dependencies...")
        try:
            subprocess.run(["npm", "install"], check=True, shell=True)
        except subprocess.CalledProcessError as e:
            print(f">>> Error during npm install: {e}")
            input("Press Enter to exit...")
            return

    print(">>> Starting Vite development server...")
    print(">>> Press Ctrl+C to stop the server.\n")
    
    # Run the server synchronously (blocking). 
    # This keeps the window open, shows logs, and handles Ctrl+C automatically.
    try:
        subprocess.run(["npm", "run", "dev"], shell=True)
    except KeyboardInterrupt:
        print("\n>>> Server stopped by user.")

if __name__ == "__main__":
    try:
        run_frontend()
    except Exception as e:
        print(f"\n>>> An unexpected error occurred: {e}")
        input("Press Enter to exit...")
