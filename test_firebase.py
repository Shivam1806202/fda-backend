import firebase_admin
from firebase_admin import credentials, storage

cred = credentials.Certificate("firebase_key.json")

firebase_admin.initialize_app(cred, {
    'storageBucket': 'uploadpdf-c94b4.appspot.com'
})

bucket = storage.bucket()

blob = bucket.blob("test/test.txt")
blob.upload_from_string("Hello Firebase 🚀")

# 🔥 IMPORTANT
blob.make_public()

print("File URL:", blob.public_url)