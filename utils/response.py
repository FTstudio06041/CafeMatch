from flask import jsonify

def success_response(data=None, message=None, code=200):
    response = {}
    if data is not None:
        response.update(data)
    if message:
        response["message"] = message
    
    # Some older APIs in this project expect success flag
    if "success" not in response:
        response["success"] = True
        
    return jsonify(response), code

def error_response(message, code=400):
    return jsonify({
        "success": False,
        "error": message,
        "message": message  # For backwards compatibility with system.py
    }), code
