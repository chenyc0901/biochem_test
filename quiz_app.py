import streamlit as st
import pandas as pd
import random
import os
import plotly.express as px
from PIL import Image
import openai

EXCEL_FILE = "test_with_answers_classified_semantic.xlsx"
DEFAULT_API_KEY = "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"

# ... (Previous functions unchanged) ...

def get_study_advice(wrong_df, api_key):
    """
    Call OpenAI API to get study advice based on wrong answers.
    """
    if not api_key:
        return "Please enter an OpenAI API Key."
    
    try:
        client = openai.OpenAI(api_key=api_key)
        
        # summarizing the mistakes
        mistakes_summary = ""
        for idx, row in wrong_df.iterrows():
            mistakes_summary += f"- Topic: {row['Category']}\n  Question: {row['Question']}\n  Correct Answer: {row['Correct Answer']}\n\n"
            
        prompt = f"""
我是一位正在學習生物化學的學生。我剛完成了一個測驗，並答錯了以下問題：

{mistakes_summary}

請分析這些錯誤。
1. 識別我需要複習的弱點領域或概念。
2. 針對每個弱點領域提供具體的學習建議或需要重點關注的主題。
3. 請使用鼓勵且簡潔的方式回答。

請用繁體中文回答。
"""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful biochemistry tutor."},
                {"role": "user", "content": prompt}
            ]
        )
        
        return response.choices[0].message.content
    except Exception as e:
        return f"Error getting advice: {e}"

# ... (Existing main function parts) ...

    # Inside main(), at the end where results are shown:
    else:
        # Result Screen
        score = st.session_state.score
        total = len(st.session_state.questions)
        st.balloons()
        st.success(f"Quiz Completed! Your Score: {score} / {total}")
        
        # Analysis
        wrong_data = []
        for idx, q in enumerate(st.session_state.questions):
            user_ans = st.session_state.user_answers.get(idx)
            if user_ans != q['answer']:
                wrong_data.append({
                    "Question": q['Question'],
                    "Category": q['分類'] if pd.notna(q['分類']) else "Unclassified",
                    "Your Answer": user_ans,
                    "Correct Answer": q['answer'],
                    "Option A": q['A'],
                    "Option B": q['B'],
                    "Option C": q['C'],
                    "Option D": q['D']
                })
        
        if wrong_data:
            st.subheader("Analysis of Incorrect Answers")
            wrong_df = pd.DataFrame(wrong_data)
            
            # Bar Chart
            category_counts = wrong_df['Category'].value_counts().reset_index()
            category_counts.columns = ['Category', 'Count']
            
            fig = px.bar(category_counts, x='Category', y='Count', title="Wrong Answers by Category")
            st.plotly_chart(fig)
            
            st.write("### Detailed Review")
            st.dataframe(wrong_df)
            
            st.divider()
            st.subheader("🤖 AI Study Advisor")
            
            api_key = st.text_input("Enter OpenAI API Key for Study Advice:", type="password")
            
            if st.button("Get Study Advice"):
                with st.spinner("Analyzing your answers..."):
                    advice = get_study_advice(wrong_df, api_key)
                    st.markdown(advice)
            
        else:
            st.write("Perfect Score! Well done!")

        if st.button("Restart Quiz"):
            st.session_state.quiz_started = False
            st.session_state.finished = False
            st.rerun()


def load_data():
    if not os.path.exists(EXCEL_FILE):
        st.error(f"File not found: {EXCEL_FILE}")
        return None
    try:
        df = pd.read_excel(EXCEL_FILE)
        return df
    except Exception as e:
        st.error(f"Error loading file: {e}")
        return None

def init_session_state():
    if 'quiz_started' not in st.session_state:
        st.session_state.quiz_started = False
    if 'questions' not in st.session_state:
        st.session_state.questions = []
    if 'current_index' not in st.session_state:
        st.session_state.current_index = 0
    if 'user_answers' not in st.session_state:
        st.session_state.user_answers = {}
    if 'score' not in st.session_state:
        st.session_state.score = 0
    if 'finished' not in st.session_state:
        st.session_state.finished = False

def start_quiz(df):
    # Select 20 random questions
    # Ensure we have enough questions
    n_questions = min(20, len(df))
    # Sample
    questions = df.sample(n=n_questions).to_dict('records')
    
    st.session_state.questions = questions
    st.session_state.quiz_started = True
    st.session_state.current_index = 0
    st.session_state.user_answers = {}
    st.session_state.score = 0
    st.session_state.finished = False

def submit_answer(selected_option):
    # Determine current question
    idx = st.session_state.current_index
    q = st.session_state.questions[idx]
    
    # Store answer
    st.session_state.user_answers[idx] = selected_option
    
    # Check if correct (optional here, usually done at end, but we store it)
    pass

def next_question():
    st.session_state.current_index += 1

def prev_question():
    if st.session_state.current_index > 0:
        st.session_state.current_index -= 1

def finish_quiz():
    st.session_state.finished = True
    # Calculate score
    correct = 0
    for idx, q in enumerate(st.session_state.questions):
        user_ans = st.session_state.user_answers.get(idx)
        if user_ans and user_ans == q['answer']:
            correct += 1
    st.session_state.score = correct

def main():
    st.set_page_config(page_title="Biochem Quiz", layout="wide")
    st.title("Biochemistry Quiz App")

    df = load_data()
    if df is None:
        return

    init_session_state()

    # Initialize feedback state if not present
    if 'feedback_mode' not in st.session_state:
        st.session_state.feedback_mode = False

    if not st.session_state.quiz_started:
        st.write(f"Loaded {len(df)} questions from database.")
        if st.button("Start New Quiz (20 Questions)"):
            start_quiz(df)
            st.rerun()
    
    elif not st.session_state.finished:
        # Quiz Loop
        idx = st.session_state.current_index
        total = len(st.session_state.questions)
        q = st.session_state.questions[idx]
        
        # Progress
        st.progress((idx) / total)
        st.subheader(f"Question {idx + 1} / {total}")
        
        # Display Question Text
        st.markdown(f"**{q['Question']}**")
        
        # Display Figure
        fig_path = q.get('Figure')
        if fig_path and isinstance(fig_path, str) and os.path.exists(fig_path):
            try:
                img = Image.open(fig_path)
                st.image(img, caption="Figure for Question")
            except Exception as e:
                st.warning(f"Could not load image: {fig_path}")

        # Options
        options = ['A', 'B', 'C', 'D']
        # Retrieve previously selected Answer if any
        existing_ans = st.session_state.user_answers.get(idx, None)
        
        # Radio button
        # Disable interaction if in feedback mode
        choice = st.radio(
            "Select an answer:",
            options,
            index=options.index(existing_ans) if existing_ans else None,
            format_func=lambda x: f"{x}. {q[x]}" if pd.notna(q[x]) else x,
            key=f"q_{idx}",
            disabled=st.session_state.feedback_mode
        )
        
        # Feedback Display
        if st.session_state.feedback_mode:
            correct_ans = q['answer']
            st.error(f"Incorrect! The correct answer is: **{correct_ans}**.  \n\n{correct_ans}. {q[correct_ans]}")
        
        # Navigation Buttons
        col1, col2, col3 = st.columns([1, 1, 4])
        
        # Button Logic
        # If in feedback mode, button is "Confirm/Continue"
        # If not, button is "Next"
        
        with col2:
            if st.session_state.feedback_mode:
                # "Continue" button to actually move forward
                if st.button("Continue"):
                    st.session_state.feedback_mode = False
                    if idx < total - 1:
                        next_question()
                    else:
                        finish_quiz()
                    st.rerun()
            else:
                # Normal "Next" / "Submit" button
                btn_text = "Next" if idx < total - 1 else "Submit Quiz"
                if st.button(btn_text):
                    if not choice:
                        st.warning("Please select an answer.")
                    else:
                        # Record answer
                        submit_answer(choice)
                        
                        # Check correctness
                        if choice == q['answer']:
                            # Correct -> Proceed
                            if idx < total - 1:
                                next_question()
                            else:
                                finish_quiz()
                            st.rerun()
                        else:
                            # Incorrect -> Show Feedback
                            st.session_state.feedback_mode = True
                            st.rerun()
        
        with col1:
             # Previous button (disabled in feedback mode usually, or allow backtracking?)
             # User logic implies forward flow. Let's keep Previous but disable in feedback 
             if idx > 0 and not st.session_state.feedback_mode:
                if st.button("Previous"):
                    # Save current state?
                    if choice: submit_answer(choice)
                    prev_question()
                    st.rerun()

    else:
        # Result Screen
        score = st.session_state.score
        total = len(st.session_state.questions)
        st.balloons()
        st.success(f"Quiz Completed! Your Score: {score} / {total}")
        
        # Analysis
        wrong_data = []
        for idx, q in enumerate(st.session_state.questions):
            user_ans = st.session_state.user_answers.get(idx)
            if user_ans != q['answer']:
                wrong_data.append({
                    "Question": q['Question'],
                    "Category": q['分類'] if pd.notna(q['分類']) else "Unclassified",
                    "Your Answer": user_ans,
                    "Correct Answer": q['answer'],
                    "Option A": q['A'],
                    "Option B": q['B'],
                    "Option C": q['C'],
                    "Option D": q['D']
                })
        
        if wrong_data:
            st.subheader("Analysis of Incorrect Answers")
            wrong_df = pd.DataFrame(wrong_data)
            
            # Bar Chart: Wrong count by Category
            category_counts = wrong_df['Category'].value_counts().reset_index()
            category_counts.columns = ['Category', 'Count']
            
            fig = px.bar(category_counts, x='Category', y='Count', title="Wrong Answers by Category")
            st.plotly_chart(fig)
            
            st.write("### Detailed Review")
            st.dataframe(wrong_df)

            st.divider()
            st.subheader("🤖 AI Study Advisor")
            
            api_key = st.text_input("Enter OpenAI API Key for Study Advice:", 
                                   value=DEFAULT_API_KEY,
                                   type="password",
                                   help="Using default key. You can override if needed.")
            
            if st.button("Get Study Advice"):
                with st.spinner("Analyzing your answers..."):
                    advice = get_study_advice(wrong_df, api_key)
                    st.markdown(advice)

        else:
            st.write("Perfect Score! Well done!")

        if st.button("Restart Quiz"):
            st.session_state.quiz_started = False
            st.session_state.finished = False
            st.rerun()

if __name__ == "__main__":
    main()
