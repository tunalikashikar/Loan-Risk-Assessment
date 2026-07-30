from flask import Flask, render_template, request
import pickle
import numpy as np
import mysql.connector
import logging
from dotenv import load_dotenv
import os

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

# Load model and encoder
model = pickle.load(open('loan_model.pkl', 'rb'))
le_property = pickle.load(open('label_encoder_property.pkl', 'rb'))

# Temporary check


def establish_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password=os.getenv("DB_PASSWORD"), 
        database="loan_db"
    )

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/predict', methods=['POST'])
def predict():
    try:
        # Capture Inputs
        name = request.form['applicant_name']
        income = int(request.form.get('income') or 0)
        employment_status = request.form['employment_status']
        credit_score = int(request.form.get('credit_score') or 0)
        existing_loan_count = int(request.form.get('existing_loan_count') or 0)
        employment_length = int(request.form.get('employment_length') or 0)
        loan_amount_requested = int(request.form.get('loan_amount_requested') or 0)
        savings = int(request.form.get('savings') or 0)
        dependents = int(request.form.get('dependents') or 0)

        # Server-side validation (backup to HTML validation)
        if income < 0 or existing_loan_count < 0 or employment_length < 0 or loan_amount_requested < 0 or savings < 0 or dependents < 0:
            return "Invalid input: values cannot be negative.", 400
        if credit_score < 300 or credit_score > 900:
            return "Invalid input: Credit score must be between 300 and 900.", 400

        # Encode employment status
        employment_status_enc = le_property.transform([employment_status])[0]

        # Prepare features for the model (8 features, matching training order)
        features = np.array([[income, employment_status_enc, credit_score, existing_loan_count,
                               employment_length, loan_amount_requested, savings, dependents]])

        # Get probability of approval from the model
        probability_approved = model.predict_proba(features)[0][1] * 100
        probability = round(probability_approved, 2)

        # Decision and risk logic
        decision = "Approved" if probability_approved >= 50 else "Rejected"
        risk_of_default = "Low" if probability_approved >= 60 else "High"

        # Database Logging
        try:
            conn = establish_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO applications (applicant_name, income, employment_status, credit_score, existing_loan_count, employment_length, loan_amount_requested, savings, dependents, prediction_result) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (name, income, employment_status, credit_score, existing_loan_count, employment_length, loan_amount_requested, savings, dependents, decision)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error(f"DB Error: {e}")

        # Return to template with results
        return render_template('result.html', name=name, decision=decision,
                                probability=probability, risk=risk_of_default)

    except Exception as e:
        logging.error(f"Prediction Error: {e}")
        return "An error occurred while processing your request.", 500


from flask import jsonify

@app.route('/api/predict', methods=['POST'])
def api_predict():
    try:
        data = request.get_json()
        income = int(data.get('income', 0))
        employment_status = data.get('employment_status')
        credit_score = int(data.get('credit_score', 0))
        existing_loan_count = int(data.get('existing_loan_count', 0))
        employment_length = int(data.get('employment_length', 0))
        loan_amount_requested = int(data.get('loan_amount_requested', 0))
        savings = int(data.get('savings', 0))
        dependents = int(data.get('dependents', 0))

        employment_status_enc = le_property.transform([employment_status])[0]
        features = np.array([[income, employment_status_enc, credit_score, existing_loan_count,
                               employment_length, loan_amount_requested, savings, dependents]])

        probability_approved = model.predict_proba(features)[0][1] * 100
        probability = round(probability_approved, 2)
        decision = "Approved" if probability_approved >= 50 else "Rejected"
        risk_of_default = "Low" if probability_approved >= 60 else "High"

        return jsonify({
            "decision": decision,
            "probability": probability,
            "risk_of_default": risk_of_default
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
 app.run(debug=True)