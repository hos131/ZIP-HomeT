from flask import Flask, request, jsonify
import json
import os

app = Flask(__name__)

# JSON 파일 저장 경로 설정
UPLOAD_FOLDER = "./uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/upload', methods=['POST'])
def upload_json():
    """
    라즈베리파이에서 JSON 파일을 업로드하고, 내용을 화면에 표시하는 기능만 수행합니다.
    """
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # 파일을 지정된 경로에 저장
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)

    # JSON 파일 읽기
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
            print("Received JSON Data:", json.dumps(data, indent=4))  # 콘솔에 JSON 내용 표시
    except Exception as e:
        return jsonify({"error": f"Failed to read JSON file: {str(e)}"}), 500

    return jsonify({"message": "File uploaded successfully", "data": data}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
