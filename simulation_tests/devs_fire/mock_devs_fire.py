from flask import Flask, request, jsonify

app = Flask(__name__)

# Store session tokens in memory
tokens = set()

@app.route("/api/connectToServer", methods=["POST"])
def connect():
    token = "mock-token-12345"
    tokens.add(token)
    return token

@app.route("/api/setMultiParameters", methods=["POST"])
def set_params():
    token = request.args.get("userToken")
    if token not in tokens:
        return "Invalid token", 403
    # Just acknowledge
    return "OK"

@app.route("/api/runSimulation", methods=["POST"])
@app.route("/api/continueSimulation", methods=["POST"])
def run_sim():
    token = request.args.get("userToken")
    if token not in tokens:
        return "Invalid token", 403
    # Return fake burned cells
    fake_ops = [{"x": i, "y": i, "Operation": "BurnTeam"} for i in range(0, 50)]
    return jsonify(fake_ops)

@app.route("/api/getPerimeterCells", methods=["POST"])
def perimeter():
    token = request.args.get("userToken")
    if token not in tokens:
        return "Invalid token", 403
    # Return fake perimeter points
    perimeter = [0,0, 0,49, 49,49, 49,0]
    return jsonify(perimeter)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8084)