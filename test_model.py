from ollama import Client
import ollama
import os
import base64

def image_to_base64(image_path):
    with open(image_path, "rb") as img_file:
        encoded = base64.b64encode(img_file.read())
        return encoded.decode("utf-8")

# Usage
# image_base64 = image_to_base64("images/photo.jpg")
# print(image_base64)



model = "glm-ocr"
img = image_to_base64("uploads/test_img_1.jpeg")
img_path = './uploads/test_img_1.jpeg'
prompt = f"Text Recognition: ./{img_path}"

response = ollama.chat(
                        model,
                        messages=[
                           {
                           'role':'user',
                           'content':'Text Recognition: ',
                           'images':[img_path]
                            }
                        ]
                       )

print(response['message']['content'])