from app import app

# This is only used for local development
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)