#!/bin/bash
# Simple startup script for Mac/Linux
# Usage: bash start.sh

echo "🚀 Starting Football Rating System..."
echo ""

# Check if Flask is installed
if ! python3 -c "import flask" 2>/dev/null; then
    echo "❌ Flask not found. Installing..."
    pip3 install flask
    echo ""
fi

# Check if database exists
if [ ! -f "ratings.db" ]; then
    echo "📊 First run detected - database will be created automatically"
    echo ""
fi

echo "✅ Starting server on http://localhost:5000"
echo ""
echo "📱 To share with friends:"
echo "   1. Install ngrok: https://ngrok.com/download"
echo "   2. In a new terminal, run: ngrok http 5000"
echo "   3. Share the https:// URL ngrok provides"
echo ""
echo "Press Ctrl+C to stop the server"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Start the Flask app
python3 app.py