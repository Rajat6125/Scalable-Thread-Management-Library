from flask import Flask, request, jsonify
import logging
from backend_core import ProcessController

# Disable Flask's default terminal spam so it doesn't mess up your console
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)

@app.route('/api/set_priority', methods=['POST'])
def set_priority():
    data = request.json
    if not data or 'pid' not in data or 'nice_value' not in data:
        return jsonify({"success": False, "error": "Missing pid or nice_value"}), 400
        
    pid = data['pid']
    nice_val = data['nice_value']
    
    # Call your existing backend logic!
    success, msg = ProcessController.execute_action(pid, "nice", nice_value=nice_val)
    
    return jsonify({"success": success, "message": msg})

def start_api_server():
    print("🚀 Local API Server running on http://127.0.0.1:5000")
    # Run on port 5000, accessible only from this computer
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)