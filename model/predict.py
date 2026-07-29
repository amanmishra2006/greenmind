import tensorflow as tf
from PIL import Image, ImageOps
import numpy as np

interpreter = tf.lite.Interpreter(model_path="model/model.tflite")
interpreter.allocate_tensors()

input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()

with open("model/labels.txt", "r") as f:
    class_names = [line.strip() for line in f.readlines()]

def predict_plant(image_path):
    image = Image.open(image_path).convert("RGB")
    size = (224, 224)
    image = ImageOps.fit(image, size, Image.Resampling.LANCZOS)

    image_array = np.asarray(image)
    normalized_image_array = (image_array.astype(np.float32) / 127.5) - 1
    data = np.expand_dims(normalized_image_array, axis=0)

    interpreter.set_tensor(input_details[0]['index'], data)
    interpreter.invoke()
    prediction = interpreter.get_tensor(output_details[0]['index'])

    index = np.argmax(prediction)
    class_name = class_names[index].split(" ", 1)[1]
    confidence_score = prediction[0][index]

    return class_name, confidence_score