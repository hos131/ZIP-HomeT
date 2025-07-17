from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # CORS 허용을 위해 반드시 먼저 선언된 app에 적용

socketio = SocketIO(app, cors_allowed_origins="*")

@app.route("/")
def index():
    return "SocketIO 서버 작동 중"

@socketio.on("connect")
def handle_connect():
    print("🔌 클라이언트 연결됨")

@app.route('/select', methods=['POST'])
def select_exercise():
    data = request.get_json()
    exercise = data.get("exercise")
    print(f"✅ 선택된 운동: {exercise}")
    return jsonify({"status": "ok"})

@socketio.on("feedback")
def handle_feedback(data):
    message = data.get("message")
    print(f"📨 피드백 수신: {message}")
    emit("feedback", {"message": message}, broadcast=True)

@socketio.on("frame")
def handle_frame(data):
    emit("frame", data, broadcast=True)

if __name__ == "__main__":
    print("🔥 서버 시작 중... http://localhost:5001 접속 가능")
    socketio.run(app, host="0.0.0.0", port=5001)
