import tensorflow as tf

model = tf.keras.models.load_model("model/keras_model.h5", compile=False)

converter = tf.lite.TFLiteConverter.from_keras_model(model)
tflite_model = converter.convert()

with open("model/model.tflite", "wb") as f:
    f.write(tflite_model)

print("Model converted to TFLite successfully!")