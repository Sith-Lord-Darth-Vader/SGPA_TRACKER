from flask import Flask, render_template, request, redirect, url_for
import pymysql

app = Flask(__name__)

# MySQL database configuration (replace with your actual credentials)
DB_HOST = 'localhost'
DB_USER = 'root'
DB_PASSWORD = 'Hmk@Sql@User007'
DB_NAME = 'sgpa_tracker_db'

def get_db_connection():
    """Establishes and returns a MySQL database connection."""
    try:
        conn = pymysql.connect(host=DB_HOST,
                               user=DB_USER,
                               password=DB_PASSWORD,
                               db=DB_NAME,
                               cursorclass=pymysql.cursors.DictCursor)
        return conn
    except pymysql.Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

def calculate_required_sa(fa1, fa2, desired_sgpa, num_subjects):
    """Calculates the average required SA marks per subject (out of 60)."""
    # Assuming each subject has equal credit and full marks of 100 (20 FA1 + 20 FA2 + 60 SA)
    # and contributes to SGPA on a 0-10 grade point scale.
    # A simplified linear mapping is used here. Adjust based on your actual grading policy.
    total_desired_grade_points = desired_sgpa * num_subjects
    earned_grade_points_fa = ((fa1 + fa2) / 10) if fa1 is not None and fa2 is not None else 0
    remaining_grade_points_needed = total_desired_grade_points - earned_grade_points_fa * num_subjects
    if remaining_grade_points_needed <= 0:
        return 0
    required_sa_avg_percentage = (remaining_grade_points_needed / (num_subjects * 0.6 * 10)) * 60 if (num_subjects * 0.6 * 10) > 0 else 0
    return max(0, min(60, required_sa_avg_percentage))

def get_study_advice(required_sa_avg):
    """Provides basic study advice based on required SA marks."""
    if required_sa_avg <= 30:
        return "Your current FA performance suggests you are in a good position. Focus on maintaining consistency for the SA."
    elif 30 < required_sa_avg <= 45:
        return "To achieve your desired SGPA, you'll need to perform moderately well in the SA. Focus on understanding core concepts."
    elif 45 < required_sa_avg <= 55:
        return "Significant effort is required for the SA to reach your target SGPA. Identify weak areas and practice extensively."
    else:
        return "You need to aim for a high score in the SA. Dedicate ample time for thorough preparation and revision."

def compare_with_previous(branch, semester, subject_fa_averages):
    """Compares the current submission with previous records (basic example)."""
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cursor:
                comparison_data = {}
                for subject, avg_fa in subject_fa_averages.items():
                    if avg_fa is not None:
                        query = """
                            SELECT AVG((sm.fa1_marks + sm.fa2_marks) / 2) AS avg_prev_fa
                            FROM sgpa_data sd
                            JOIN subject_marks sm ON sd.id = sm.sgpa_data_id
                            WHERE sd.branch = %s AND sd.semester = %s AND sm.subject_name = %s
                        """
                        cursor.execute(query, ( branch, semester, subject))
                        result = cursor.fetchone()
                        comparison_data[subject] = result['avg_prev_fa'] if result['avg_prev_fa'] is not None else "No previous data"
                    else:
                        comparison_data[subject] = "FA marks not provided"
                return comparison_data
        except pymysql.Error as e:
            print(f"Error comparing with previous data: {e}")
            return None
        finally:
            conn.close()
    return None

@app.route('/')
def index():
    """Renders the HTML form for branch and semester selection."""
    return render_template('index.html')

@app.route('/get_subjects', methods=['POST'])
def get_subjects():
    """Returns the HTML form for entering marks based on branch and semester."""
    name = request.form['name']
    PRN = request.form['PRN']
    branch = request.form['branch']
    semester = request.form['semester']

    subject_data = {
        "MECHANICAL": {
            "Sem 1": ["LAUC", "Engg Physics", "Manufacturing Technology", "IKS"],
            "Sem 2": ["MC", "Engg Chemistry", "Thermodynamics", "FES", "German/Japnese/English/BST"]
        },
        "E&TC": {
            "Sem 1": ["LAUC", "Engg Physics", "BEEE", "PPS", "IKS"],
            "Sem 2": ["MC", "Engg Chemistry", "Digital System", "NT", "German/Japnese/English/BST"]
        },
        "AIML": {
            "Sem 1": ["LAUC", "Engg Physics", "COOS","Discrete Mathematics","IKS"],
            "Sem 2": ["MC","Engg Chemistry","Data Science","SE","German/BST/English/Japnese"]
        },
        "CIVIL": {
            "Sem 1": ["LAUC", "Engg Chemistry", "Engg Mechanics", "ECE","IKS"],
            "Sem 2": ["MC", "Eng Physics", "Surveying", "EGMC", "German/Japnese/English/BST"]
        },
        "IT": {
            "Sem 1": ["LAUC", "Engg Chemistry", "DECO", "Discrete Mathematics"],
            "Sem 2": ["MC", "Eng Physics", "POPL", "German/Japnese/English/BST"]
        },
        "COMPUTER": {
            "Sem 1": ["LAUC", "Engg Chemistry", "DECO", "CPPS", "German/Japnese/English/BST"],
            "Sem 2": ["MC", "Eng Physics", "Discrete Math", "CPPS", "OPPS","IKS"]
        },
        "COMPUTER(R)": {
            "Sem 1": ["LAUC", "Engg Chemistry", "DECO", "CPPS", "German/Japnese/English/BST"],
            "Sem 2": ["MC", "Eng Physics", "Discrete Math", "CPPS", "OPPS","IKS"]
        }
    }

    subjects = subject_data.get(branch, {}).get(semester, [])
    if subjects:
        return render_template('marks_form.html',name=name, PRN=PRN, branch=branch, semester=semester, subjects=subjects)
    else:
        return "Invalid Branch or Semester selected."

@app.route('/submit_marks', methods=['POST'])
def submit_marks():
    """Handles the form submission, stores data, and calculates required SA marks."""
    if request.method == 'POST':
        name = request.form['name']
        PRN = request.form['PRN']
        branch = request.form['branch']
        semester = request.form['semester']
        fa1_marks = [int(x) if x else None for x in request.form.getlist('fa1[]')]
        fa2_marks = [int(x) if x else None for x in request.form.getlist('fa2[]')]
        desired_sgpa = float(request.form['desired_sgpa'])
        subject_names = request.form.getlist('subject_name[]')

        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cursor:
                    # Insert general form information
                    cursor.execute("""
                        INSERT INTO sgpa_data (name, PRN, branch, semester)
                        VALUES (%s, %s, %s, %s)
                    """, (name, PRN, branch, semester))
                    sgpa_data_id = conn.insert_id()     # Get the id of the newly inserted row

                    subject_fa_averages = {}
                    for i in range(len(subject_names)):
                        subject_name = subject_names[i]
                        mark1 = fa1_marks[i] if i < len(fa1_marks) else None
                        mark2 = fa2_marks[i] if i < len(fa2_marks) else None
                        cursor.execute("""
                            INSERT INTO subject_marks (sgpa_data_id, subject_name, fa1_marks, fa2_marks)
                            VALUES (%s, %s, %s, %s)
                        """, (sgpa_data_id, subject_name, mark1, mark2))
                        subject_fa_averages[subject_name] = (mark1 + mark2) / 2 if mark1 is not None and mark2 is not None else None

                conn.commit()

                # Calculate required SA marks and study advice (average across subjects)
                num_subjects = len(subject_names)
                avg_fa1 = sum(m for m in fa1_marks if m is not None) / len([m for m in fa1_marks if m is not None]) if any(fa1_marks) else 0
                avg_fa2 = sum(m for m in fa2_marks if m is not None) / len([m for m in fa2_marks if m is not None]) if any(fa2_marks) else 0
                required_sa_avg = calculate_required_sa(avg_fa1, avg_fa2, desired_sgpa, num_subjects)
                study_advice = get_study_advice(required_sa_avg)

                # Compare with previous records
                comparison_info = compare_with_previous(branch, semester, subject_fa_averages)

                return render_template('result.html',
                                       name = name,
                                       PRN = PRN,
                                       branch=branch,
                                       semester=semester,
                                       desired_sgpa=desired_sgpa,
                                       required_sa_avg=required_sa_avg,
                                       study_advice=study_advice,
                                       comparison_info=comparison_info)

            except pymysql.Error as e:
                conn.rollback()
                return f"Error inserting data into MySQL: {e}"
            finally:
                conn.close()
        else:
            return "Failed to connect to the database."
    return redirect(url_for('index'))

@app.route('/view_all_entries')
def view_all_entries():
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT
                        sd.id AS submission_id,
                        sd.name,
                        sd.PRN,
                        sd.branch,
                        sd.semester,
                        sm.subject_name,
                        sm.fa1_marks,
                        sm.fa2_marks,
                        sd.submission_timestamp
                    FROM
                        sgpa_data sd
                    JOIN
                        subject_marks sm ON sd.id = sm.sgpa_data_id
                    ORDER BY
                        sd.submission_timestamp DESC, sd.id, sm.subject_name;
                """)
                all_entries_data = cursor.fetchall()

                # Process the data to group by submission ID
                processed_entries = {}
                for row in all_entries_data:
                    submission_id = row['submission_id']
                    if submission_id not in processed_entries:
                        processed_entries[submission_id] = {
                            'name' : row['name'],
                            'PRN' : row['PRN'],
                            'branch': row['branch'],
                            'semester': row['semester'],
                            'timestamp': row['submission_timestamp'],
                            'subjects': {}
                        }
                    processed_entries[submission_id]['subjects'][row['subject_name']] = {
                        'fa1': row['fa1_marks'],
                        'fa2': row['fa2_marks']
                    }

                return render_template('all_entries.html', entries=processed_entries)
        except pymysql.Error as e:
            return f"Error fetching all entries: {e}"
        finally:
            conn.close()
    else:
        return "Failed to connect to the database."
    
if __name__ == '__main__':
    app.run(debug=True)