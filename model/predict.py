from tensorflow.keras.models import load_model
from PIL import Image, ImageOps
import numpy as np

model = load_model("model/keras_model.h5", compile=False)

with open("model/labels.txt", "r") as f:
    class_names = [line.strip() for line in f.readlines()]

def predict_plant(image_path):
    image = Image.open(image_path).convert("RGB")
    size = (224, 224)
    image = ImageOps.fit(image, size, Image.Resampling.LANCZOS)

    image_array = np.asarray(image)
    normalized_image_array = (image_array.astype(np.float32) / 127.5) - 1
    data = np.expand_dims(normalized_image_array, axis=0)

    prediction = model.predict(data)
    index = np.argmax(prediction)
    class_name = class_names[index].split(" ", 1)[1]
    confidence_score = prediction[0][index]

    return class_name, confidence_score