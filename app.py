from flask import Flask, request, render_template_string, render_template
import os
import requests
from ollama import Client
from werkzeug.utils import secure_filename
from PIL import Image
import pytesseract

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


app = Flask(__name__)
client = Client()

def build_prompt(question: str, marks: str, keypoints: str, answer: str) -> str:
        return f"question: {question}\nmarks: {marks}\nkey: {keypoints}\nanswer: {answer}"

@app.route("/", methods=["GET", "POST"])
def home(): 
        result = None
        question = marks = keypoints = answer = ""
        if request.method == "POST":
                question = request.form.get("question", "").strip()
                marks = request.form.get("marks", "").strip() or "0"
                keypoints = request.form.get("keypoints", "").strip()
                answer = request.form.get("answer", "").strip()

                prompt = build_prompt(question, marks, keypoints, answer)
                print(prompt)

                ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
                model = os.getenv("OLLAMA_MODEL", "easy-eval")
                payload = {
                        "model": model,
                        "messages": [
                                {"role": "user", "content": prompt}
                        ]
                }

                try:
                        o = client.generate(model=model, prompt=prompt)
                        if isinstance(o, dict):
                                result = o.get('response') or str(o)
                                if isinstance(result, str) and result.startswith('response:'):
                                        result = result[9:]
                        else:
                                result = str(o)
                except Exception as e:
                        result = f"Request to Ollama failed: {e}"

        return render_template('home.html', result=result, question=question, marks=marks, keypoints=keypoints, answer=answer)

@app.route('/img', methods=['GET', 'POST'])
def image_answer():
        result = None
        question = marks = keypoints = ""
        extracted_text = None
        filename = None

        if request.method == 'POST':
                question = request.form.get("question", "").strip()
                marks = request.form.get("marks", "").strip() or "0"
                keypoints = request.form.get("keypoints", "").strip()

                if 'answer_image' not in request.files:
                        result = 'No image uploaded'
                        return render_template('home_image.html', result=result, question=question, marks=marks, keypoints=keypoints)

                file = request.files['answer_image']
                if file.filename == '':
                        result = 'No selected file'
                        return render_template('home_image.html', result=result, question=question, marks=marks, keypoints=keypoints)

                if not allowed_file(file.filename):
                        result = 'Invalid file type'
                        return render_template('home_image.html', result=result, question=question, marks=marks, keypoints=keypoints)

                filename = secure_filename(file.filename)
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                file.save(filepath)

                try:
                        img = Image.open(filepath)
                        extracted_text = pytesseract.image_to_string(img)
                except Exception as e:
                        result = f'OCR failed: {e}'
                        return render_template('home_image.html', result=result, question=question, marks=marks, keypoints=keypoints)

                prompt = build_prompt(question, marks, keypoints, extracted_text)
                model = os.getenv("OLLAMA_MODEL", "easy-eval")

                try:
                        o = client.generate(model=model, prompt=prompt)
                        result = o['response'][8:]
                except Exception as e:
                        result = f"Request to Ollama failed: {e}"

        return render_template('home_image.html', result=result, question=question, marks=marks, keypoints=keypoints, extracted_text=extracted_text, filename=filename)


if __name__ == "__main__":
        app.run(debug=True, host="127.0.0.1", port=5000)