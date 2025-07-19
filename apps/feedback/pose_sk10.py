import asyncio, json, numpy as np, tensorflow as tf, threading
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from aiortc.contrib.media import MediaRelay
from aiohttp import web
import aiohttp_cors
import socketio
import cv2, mediapipe as mp
from av import VideoFrame
from collections import deque
from queue import Queue
from pymongo import MongoClient
import time

# ✅ 운동명-한글 매핑
exercise_kor_map = {
    "burpee": "버피 테스트",
    "cross_lunge": "크로스 런지",
    "knee_pushup": "니 푸시업",
    "pushup": "푸시업",
    "plank": "플랭크",
    "side_lunge": "사이드 런지"
}
# exercise 값에 따라 실제 파일명 매핑
model_map = {
    "burpee": "burpeetest.h5",
    "cross_lunge": "crosslunge.h5",
    "knee_pushup": "kneepushup.h5",
    "plank": "plank.h5",
    "pushup": "pushup.h5",
    "side_lunge": "sidelunge.h5"
}

data_map = {
    "burpee": "training_data_burpeetest.json",
    "cross_lunge": "training_data_crosslunge.json",
    "knee_pushup": "training_data_kneepushup.json",
    "plank": "training_data_plank.json",
    "pushup": "training_data_pushup.json",
    "side_lunge": "training_data_sidelunge.json"
}

# ✅ MongoDB 연결
client = MongoClient("mongodb+srv://data1234:Atlas1234@cluster0.rkveizh.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")

# ✅ SocketIO 연결
sio = socketio.Client()
try:
    sio.connect("http://localhost:5001")
    print("✅ SocketIO 연결됨")
except Exception as e:
    print("❌ SocketIO 연결 실패:", e)

# ✅ Mediapipe 설정
mp_pose = mp.solutions.pose
pose = mp_pose.Pose()
REFERENCE_WIDTH, REFERENCE_HEIGHT = 1920, 1080

# 내부 상태
last_predictions = deque(maxlen=5)
feedback_queue = Queue()
frame_count = 0
capture_interval = 120

LANDMARK_IDS = {
    "Nose": 0, "Left Eye": 2, "Right Eye": 5, "Left Ear": 7, "Right Ear": 8,
    "Left Shoulder": 11, "Right Shoulder": 12, "Left Elbow": 13, "Right Elbow": 14,
    "Left Wrist": 15, "Right Wrist": 16, "Left Hip": 23, "Right Hip": 24,
    "Left Knee": 25, "Right Knee": 26, "Left Ankle": 27, "Right Ankle": 28,
    "Left Foot": 31, "Right Foot": 32
}
VIRTUAL_POINTS = ["Neck", "Waist", "Back", "Left Palm", "Right Palm"]

# 🔄 피드백 송신 쓰레드
def send_feedback_worker():
    while True:
        msg = feedback_queue.get()
        if msg is None:
            break
        print("📤", msg)
        sio.emit("feedback", {"message": msg})
        time.sleep(0.01)
        feedback_queue.task_done()

threading.Thread(target=send_feedback_worker, daemon=True).start()

# 🧠 정규화
def normalize(pose_dict):
    ls = pose_dict.get("Left Shoulder")
    rs = pose_dict.get("Right Shoulder")
    if not ls or not rs:
        return None
    cx = (ls[0] + rs[0]) / 2
    cy = (ls[1] + rs[1]) / 2
    w = ((ls[0] - rs[0])**2 + (ls[1] - rs[1])**2)**0.5
    if w == 0: return None
    return {k: [(x - cx)/w, (y - cy)/w] for k, (x, y) in pose_dict.items()}

# 📈 예측 호출
def process_pose(frame, count):
    pose_dict = {}
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = pose.process(rgb)

    if results and results.pose_landmarks:
        landmarks = results.pose_landmarks.landmark
        for name, idx in LANDMARK_IDS.items():
            x = int(landmarks[idx].x * REFERENCE_WIDTH)
            y = int(landmarks[idx].y * REFERENCE_HEIGHT)
            pose_dict[name] = [x, y]

        def avg(p1, p2): return [(p1[0]+p2[0])//2, (p1[1]+p2[1])//2]
        if "Left Shoulder" in pose_dict and "Right Shoulder" in pose_dict:
            pose_dict["Neck"] = avg(pose_dict["Left Shoulder"], pose_dict["Right Shoulder"])
        if "Left Hip" in pose_dict and "Right Hip" in pose_dict:
            pose_dict["Waist"] = avg(pose_dict["Left Hip"], pose_dict["Right Hip"])
        if "Neck" in pose_dict and "Waist" in pose_dict:
            pose_dict["Back"] = avg(pose_dict["Neck"], pose_dict["Waist"])
        if "Left Wrist" in pose_dict:
            pose_dict["Left Palm"] = pose_dict["Left Wrist"]
        if "Right Wrist" in pose_dict:
            pose_dict["Right Palm"] = pose_dict["Right Wrist"]

        globals()["db"]["skeleton_data"].insert_one({"frame": count, "landmarks": pose_dict})

        if count % capture_interval == 0:
            threading.Thread(target=predict_in_background, args=(pose_dict,)).start()

# ✅ 예측 백그라운드
def predict_in_background(pose_dict):
    norm = normalize(pose_dict)
    if not norm:
        print("⚠️ 어깨 좌표 부족 - 예측 스킵")
        return
    try:
        keys = list(LANDMARK_IDS.keys()) + VIRTUAL_POINTS
        vector = [norm[k] for k in keys if k in norm]
        input_vector = np.array(vector).flatten().reshape(1, -1)

        _, cond_pred = globals()["model"].predict(input_vector)
        exercise_kor = globals()["exercise_kor"]
        last_predictions.append(exercise_kor)

        if last_predictions.count(exercise_kor) >= 2:
            relevant_conditions = []
            for d in globals()["all_data"]:
                if d["exercise"] == exercise_kor:
                    relevant_conditions = list(d["labels"].keys())
                    break
            feedback_queue.put(f"📌 피드백 - 운동: {exercise_kor}")
            for i, cond in enumerate(globals()["condition_keys"]):
                if cond not in relevant_conditions:
                    continue
                status = "✅" if cond_pred[0][i] >= 0.5 else "❌"
                feedback_queue.put(f"{status} {cond}")
        else:
            print("⏳ 예측 누적 중...", list(last_predictions))
    except Exception as e:
        print("❌ 예측 오류:", e)

# 🎥 비디오 트랙
class VideoTrack(VideoStreamTrack):
    def __init__(self, relay, track, model, all_data, exercise_kor, condition_keys):
        super().__init__()
        self.track = relay.subscribe(track)
        globals()["model"] = model
        globals()["all_data"] = all_data
        globals()["exercise_kor"] = exercise_kor
        globals()["condition_keys"] = condition_keys
    async def recv(self):
        global frame_count
        frame = await self.track.recv()
        img = frame.to_ndarray(format="bgr24")
        frame_count += 1
        process_pose(img, frame_count)
        return frame

# WebRTC offer 처리
relay = MediaRelay()
pcs = set()

# ✅ offer 함수
async def offer(request):
    params = await request.json() 
    user_id = params.get("user_id")  
    globals()["db"] = client[f"userdb_{user_id}"]

    print("🧪 전달받은 JSON:", params)
    print("🧪 전달받은 user_id:", user_id)

    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])
    exercise = params.get("exercise")
    model_path = model_map.get(exercise)
    data_path = data_map.get(exercise)
    
    if not model_path or not data_path:
        return web.Response(status=400, text=f"❌ 지원되지 않는 운동명입니다: {exercise}")

    exercise_kor = exercise_kor_map.get(exercise, "알 수 없음")

    # 🔥 모델/데이터 로드
    model = tf.keras.models.load_model(model_path)
    with open("condition_keys.json", "r", encoding="utf-8") as f:
        condition_keys = json.load(f)
    with open(data_path, "r", encoding="utf-8") as f:
        all_data = json.load(f)

    pc = RTCPeerConnection()
    pcs.add(pc)

    @pc.on("track")
    def on_track(track):
        if track.kind == "video":
            pc.addTrack(VideoTrack(relay, track, model, all_data, exercise_kor, condition_keys))

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.Response(
        content_type="application/json",
        text=json.dumps({"sdp": pc.localDescription.sdp, "type": pc.localDescription.type})
    )

# 서버 실행
app = web.Application()
app.router.add_post("/offer", offer)

cors = aiohttp_cors.setup(app, defaults={
    "*": aiohttp_cors.ResourceOptions(
        allow_credentials=True,
        expose_headers="*",
        allow_headers="*",
    )
})
for route in list(app.router.routes()):
    cors.add(route)

print("🌐 WebRTC 서버 실행 중...")
web.run_app(app, port=8080)
