from app import create_app

app = create_app()

if __name__ == "__main__":
    # Run Flask directly with debug enabled
    app.run(host="0.0.0.0", port=5000)