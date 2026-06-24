import os
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, accuracy_score
import pickle

print("=" * 50)
print("   FAKE NEWS DETECTOR — Model Training")
print("=" * 50)

# -----------------------------
# LOAD DATASET
# -----------------------------
print("\n📂 Loading dataset...")

fake = pd.read_csv("dataset/Fake.csv")
real = pd.read_csv("dataset/True.csv")

fake["label"] = 0
real["label"] = 1

data = pd.concat([fake, real]).sample(frac=1, random_state=42).reset_index(drop=True)

print(f"   Fake news samples : {len(fake)}")
print(f"   Real news samples : {len(real)}")
print(f"   Total samples     : {len(data)}")

# -----------------------------
# PREPARE
# -----------------------------
X = data["text"].fillna("")
y = data["label"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# -----------------------------
# VECTORIZE (TF-IDF)
# -----------------------------
print("\n🔤 Vectorizing with TF-IDF...")
vectorizer = TfidfVectorizer(stop_words="english", max_df=0.7)
X_train_v  = vectorizer.fit_transform(X_train)
X_test_v   = vectorizer.transform(X_test)

# -----------------------------
# TRAIN
# -----------------------------
print("🤖 Training Logistic Regression model...")
model = LogisticRegression(max_iter=1000)
model.fit(X_train_v, y_train)

# -----------------------------
# EVALUATE
# -----------------------------
y_pred   = model.predict(X_test_v)
accuracy = accuracy_score(y_test, y_pred)

print(f"\n✅ Accuracy : {accuracy * 100:.2f}%")
print("\n📊 Classification Report:")
print(classification_report(y_test, y_pred, target_names=["Fake", "Real"]))

# -----------------------------
# SAVE
# -----------------------------
os.makedirs("model", exist_ok=True)
pickle.dump(model,      open("model/model.pkl",      "wb"))
pickle.dump(vectorizer, open("model/vectorizer.pkl", "wb"))

print("💾 model/model.pkl      — saved")
print("💾 model/vectorizer.pkl — saved")
print("\n🎉 Done! Now run:  python app.py")
print("=" * 50)
