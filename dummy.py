from flask import Flask, request, render_template, redirect, flash, url_for
from werkzeug.utils import secure_filename
from PIL import Image
import pytesseract
import os
import subprocess
import json


UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.secret_key = 'change-this-secret'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        roll = (request.form.get('roll') or '').strip()
        if not roll:
            flash('Please enter roll number')
            return redirect(request.url)

        if 'image' not in request.files:
            flash('No image uploaded')
            return redirect(request.url)

        file = request.files['image']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)

        if not allowed_file(file.filename):
            flash('Invalid file type')
            return redirect(request.url)

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        try:
            img = Image.open(filepath)
            text = pytesseract.image_to_string(img)
        except Exception as e:
            flash(f'OCR error: {e}')
            return redirect(request.url)

        found = roll in text
        return render_template('index.html', extracted_text=text, roll=roll, found=found, filename=filename)

    return render_template('index.html')


# Chat endpoints: render page and API that forwards user input to the local Ollama client
@app.route('/chat', methods=['GET'])
def chat_page():
    return render_template('chatbot.html')


@app.route('/chat', methods=['POST'])
def chat_api():
    data = request.get_json(force=True, silent=True) or {}
    message = (data.get('message') or '').strip()
    model = (data.get('model') or 'llama2').strip()

    if not message:
        return {"error": "No message provided"}, 400

    # Try using the ollama Python client first
    try:
        import ollama
        response_text = None

        # Support several possible client interfaces
        if hasattr(ollama, 'Ollama'):
            client = ollama.Ollama()
            if hasattr(client, 'query'):
                resp = client.query(model, message)
                response_text = resp if isinstance(resp, str) else (resp.get('response') if isinstance(resp, dict) else str(resp))
            elif hasattr(client, 'generate'):
                gen = client.generate(model=model, prompt=message)
                if isinstance(gen, dict):
                    response_text = gen.get('output') or gen.get('response') or str(gen)
                elif hasattr(gen, '__iter__'):
                    # concatenate generator/delta chunks
                    chunks = []
                    for c in gen:
                        if isinstance(c, dict):
                            chunks.append(c.get('content') or c.get('text') or str(c))
                        else:
                            chunks.append(str(c))
                    response_text = ''.join(chunks)
                else:
                    response_text = str(gen)
            elif hasattr(client, 'completions'):
                res = client.completions.create(model=model, prompt=message)
                if isinstance(res, dict):
                    response_text = (res.get('choices') or [{}])[0].get('message', {}).get('content') or str(res)
                else:
                    response_text = str(res)
        elif hasattr(ollama, 'query'):
            resp = ollama.query(model, message)
            response_text = resp if isinstance(resp, str) else (resp.get('response') if isinstance(resp, dict) else str(resp))
        else:
            raise RuntimeError('Installed ollama package has no compatible API')

        if not response_text:
            raise RuntimeError('No response from ollama client')

        return {"response": response_text}

    except Exception as e:
        # Fallback to calling the ollama CLI via subprocess when client is not available or fails
        try:
            cmd = ["ollama", "query", model, message]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if proc.returncode != 0:
                return {"error": proc.stderr.strip() or "ollama returned non-zero exit"}, 500
            response_text = proc.stdout.strip()
            return {"response": response_text}
        except Exception as e2:
            return {"error": f"ollama client error: {e}; fallback error: {e2}"}, 500


if __name__ == '__main__':
    app.run(debug=True)
