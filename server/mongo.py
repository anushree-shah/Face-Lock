from flask import Flask, jsonify, request
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token
from dotenv import load_dotenv
from flask_mail import Mail, Message
import pyotp
import os
import base64

from flask_cors import cross_origin
import cv2
import face_recognition
from PIL import Image
import numpy as np
import io

load_dotenv()

app = Flask(__name__)

mail = Mail(app)

mailpswd = os.getenv("MAILPSWD")

app.config["MAIL_SERVER"] = 'smtp.gmail.com'
app.config["MAIL_PORT"] = 465
app.config["MAIL_USERNAME"] = 'projecttrial30@gmail.com'
app.config['MAIL_PASSWORD'] = 'jihfydnmtvttitlj'  
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
mail = Mail(app)
otp_secret = pyotp.random_base32()

db = os.getenv("DB")

app.config['MONGO_DBNAME'] = 'facedata'
app.config['MONGO_URI'] = db
app.config['JWT_SECRET_KEY'] = 'secret'

client = MongoClient(app.config['MONGO_URI'])
db = client[app.config['MONGO_DBNAME']]

bcrypt = Bcrypt(app)
jwt = JWTManager(app)

CORS(app)

from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

encryption_key = b'MyNewSecretEncryptionKey'
salt = b'MyRandomSalt'
kdf = PBKDF2HMAC(
    algorithm=hashes.SHA256(),
    length=32,
    salt=salt,
    iterations=100000,
    backend=default_backend()
)
key = base64.urlsafe_b64encode(kdf.derive(encryption_key))
f = Fernet(key)


# def encrypt_data(data):
#     encrypted_data = f.encrypt(data.encode())
#     return base64.urlsafe_b64encode(salt + encrypted_data).decode()

# def decrypt_data(encrypted_data):
#     encrypted_data = base64.urlsafe_b64decode(encrypted_data.encode())
#     decrypted_data = f.decrypt(encrypted_data[len(salt):])
#     return decrypted_data.decode()

def encrypt_data(data):
    return data
    encrypted_data = f.encrypt(data)
    return base64.urlsafe_b64encode(encrypted_data).decode()

def decrypt_data(encrypted_data):
    try:
        encrypted_data = base64.urlsafe_b64decode(encrypted_data)
        decrypted_data = f.decrypt(encrypted_data)
        return decrypted_data.decode()
    except:
        # Handle the InvalidToken exception here
        # For example, you can return None or an error message
        return None



def base64_to_numpy(base64_string):
    # Remove the data URL prefix
    encoded_image = base64_string.split(",")[1]

    # Decode the base64 string to bytes
    image_bytes = base64.b64decode(encoded_image)

    # Create a BytesIO object to wrap the image bytes
    image_stream = io.BytesIO(image_bytes)

    # Open the image using PIL (Python Imaging Library)
    pil_image = Image.open(image_stream)

    # Convert PIL image to NumPy array
    numpy_array = np.array(pil_image)

    return numpy_array

@app.route('/extract-faces', methods=["POST"])
@cross_origin()
def send_encooding():
    faces = db.faces

    # Get the frames from the request
    # frames = request.form.getlist('frames')
    frame = request.get_json()['frame']
    print("FRAMES ARE ",frame)

    image = base64_to_numpy(frame)
    rgb_frame = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # Detect faces in the frame
    face_locations = face_recognition.face_locations(rgb_frame)
    face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

    # Initialize arrays to store encodings and locations
    encodings = []
    locations = []
        # Iterate over detected faces
    for face_encoding, face_location in zip(face_encodings, face_locations):
                # Append encoding and location to arrays
        encodings.append(face_encoding.tolist())
        locations.append(face_location)
    response_data = {
        'encodings': encodings,
        'locations': locations
    }
    return jsonify(response_data)

@app.route('/users/register', methods=["POST"])
@cross_origin()
def register():
    users = db.users
    username = request.get_json()['username']
    email = request.get_json()['email']
    account = encrypt_data(request.get_json()['account'])
    password = bcrypt.generate_password_hash(request.get_json()['password']).decode('utf-8')
    facialRecognitionEnabled = request.get_json()['facialRecognitionEnabled']
    threshold = request.get_json()['threshold']
    created = datetime.utcnow()
    encodings = request.get_json()['encodings']
    locations = request.get_json()['locations']

    user_id = users.insert_one({
        'username': username,
        'email': email,
        'account': account,
        'password': password,
        'facialRecognitionEnabled': facialRecognitionEnabled,
        'threshold': threshold,
        'created': created,
        'encodings': encodings,
        'locations': locations,
    }).inserted_id

    new_user = users.find_one({'_id': ObjectId(user_id)})

    result = {'email': new_user['email'] + ' registered'}

    return jsonify({'result': result})

@app.route('/users/login', methods=['POST'])
def login():
    users = db.users
    username = request.get_json()['username']
    password = request.get_json()['password']
    result = ""

    response = users.find_one({'username': username})
    if response:
        # acnt = decrypt_data(response['account'])  
        acnt = 1234
        if bcrypt.check_password_hash(response['password'], password):
            access_token = create_access_token(identity={
                'username': response['username'],
                'account': acnt 
            })
            result = jsonify({'token': access_token})
        else:
            result = jsonify({"error": "Invalid username and password"})
    else:
        result = jsonify({"result": "No results found"})
    return result
     
@app.route('/txn/transaction', methods=['POST'])
def transaction():
    users = db.users
    txn = db.txn
    username = request.get_json()['username']
    account = encrypt_data( request.get_json()['account'])
    reciever_name = encrypt_data(request.get_json()['reciever_name'])
    recieveraccount_number = encrypt_data(request.get_json()['recieveraccount_number'])
    amount = request.get_json()['amount']

    response = users.find_one({'username': username})
  
    email = response['email']
    totp = pyotp.TOTP(otp_secret)
    otp = totp.now()
    try:
        msg = Message(subject='OTP', sender='projecttrial30@gmail.com', recipients=[email])
        msg.body = str(otp)
        mail.send(msg)
        print('result: OTP sent')
    except Exception as e:
        print(e)
        print('result: Error occurred while sending OTP')

    txn_id = txn.insert_one({
        'username': username,
        'account': account,
        'reciever_name': reciever_name,
        'recieveraccount_number': recieveraccount_number,
        'amount': amount,
    }).inserted_id

    new_txn = txn.find_one({'_id': ObjectId(txn_id)})

    result = {'username': new_txn['username'] + ' new transaction'}
    return jsonify({'result': result})


@app.route('/verify', methods=['POST'])
def validate():
    user_otp = request.get_json()['otp']
    totp = pyotp.TOTP(otp_secret, interval=30)
    generated_otp = totp.now()  # OTP generated during the transaction process
    print("Generated OTP:", generated_otp)
    print("User OTP:", user_otp)
    
    if totp.verify(user_otp, valid_window=1):  # Specify a valid window of 1 to allow for minor time variations
        return jsonify({'message': 'OTP is correct'})
    else:
        return jsonify({'message': 'OTP is incorrect'})


if __name__ == '__main__':
    app.run(debug=True,port=5000)
