# ==============================
# 数学学習アプリ【完全・修正版】
# Streamlit 1.30+
# ==============================

import streamlit as st
import json
import random
import pandas as pd
import sympy as sp
import os
from datetime import datetime

# ==============================
# 設定
# ==============================
PROBLEM_FILE = "problems.json"
RESULT_FILE = "results.csv"
TEACHER_PASSWORD = "20020711"

# ==============================
# 共通関数
# ==============================

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def load_problems():
    if not os.path.exists(PROBLEM_FILE):
        return []
    with open(PROBLEM_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_problems(problems):
    with open(PROBLEM_FILE, "w", encoding="utf-8") as f:
        json.dump(problems, f, ensure_ascii=False, indent=2)


def load_results():
    if not os.path.exists(RESULT_FILE):
        return pd.DataFrame()
    return pd.read_csv(RESULT_FILE)


def check_answer(student, correct):
    try:
        return sp.simplify(student) == sp.simplify(correct)
    except Exception:
        return str(student).strip() == str(correct).strip()

# ==============================
# 生徒画面
# ==============================

def student_view():
    st.header("✏ 生徒用テスト")

    student_id = st.text_input("生徒ID")
    if not student_id:
        return

    problems = load_problems()
    if not problems:
        st.warning("問題がありません")
        return

    if "answers" not in st.session_state:
        st.session_state.answers = {}
        st.session_state.q = 0

    q = st.session_state.q
    prob = problems[q]

    st.subheader(f"問題 {q+1} / {len(problems)}")
    st.write(prob["question"])

    answer = st.text_input(
        "答え",
        value=st.session_state.answers.get(q, ""),
        key=f"ans_{q}"
    )

    st.session_state.answers[q] = answer

    col1, col2 = st.columns(2)

    with col1:
        if st.button("前へ") and q > 0:
            st.session_state.q -= 1
            st.rerun()

    with col2:
        if st.button("次へ"):
            if q < len(problems) - 1:
                st.session_state.q += 1
                st.rerun()
            else:
                # 保存
                records = []
                for i, p in enumerate(problems):
                    records.append({
                        "student_id": student_id,
                        "question": p["question"],
                        "student_answer": st.session_state.answers.get(i, ""),
                        "correct_answer": p["answer"],
                        "is_correct": check_answer(
                            st.session_state.answers.get(i, ""), p["answer"]
                        ),
                        "timestamp": now()
                    })

                df = pd.DataFrame(records)
                df.to_csv(
                    RESULT_FILE,
                    mode="a",
                    header=not os.path.exists(RESULT_FILE),
                    index=False,
                    encoding="utf-8"
                )

                st.success("提出完了")
                st.dataframe(df)
                st.write(f"正答率：{df['is_correct'].mean()*100:.1f}%")

# ==============================
# 教師画面
# ==============================

def teacher_view():
    st.header("🧑‍🏫 教師用")

    # --- 問題編集 ---
    st.subheader("📘 問題編集")
    problems = load_problems()

    for i, p in enumerate(problems):
        with st.expander(f"問題 {i+1}"):
            q = st.text_input("問題文", p["question"], key=f"q{i}")
            a = st.text_input("答え", p["answer"], key=f"a{i}")

            if st.button("保存", key=f"s{i}"):
                problems[i] = {"question": q, "answer": a}
                save_problems(problems)
                st.success("保存しました")
                st.rerun()

            if st.button("削除", key=f"d{i}"):
                problems.pop(i)
                save_problems(problems)
                st.rerun()

    st.subheader("➕ 新規追加")
    nq = st.text_input("新しい問題")
    na = st.text_input("答え")
    if st.button("追加"):
        problems.append({"question": nq, "answer": na})
        save_problems(problems)
        st.success("追加しました")
        st.rerun()

    # --- 成績分析 ---
    st.subheader("📊 成績分析")
    df = load_results()
    if df.empty:
        st.info("データがありません")
        return

    st.metric("全体正答率", f"{df['is_correct'].mean()*100:.1f}%")

    st.bar_chart(df.groupby("question")['is_correct'].mean() * 100)

    sid = st.selectbox("生徒選択", df['student_id'].unique())
    sdf = df[df['student_id'] == sid]

    st.metric("個人正答率", f"{sdf['is_correct'].mean()*100:.1f}%")
    st.dataframe(sdf)

# ==============================
# メイン
# ==============================

st.set_page_config(page_title="数学学習アプリ")

if "mode" not in st.session_state:
    st.session_state.mode = None

if st.session_state.mode is None:
    st.title("📘 学習アプリ")
    mode = st.radio("利用者選択", ["生徒", "教師"])

    if mode == "生徒":
        if st.button("開始"):
            st.session_state.mode = "student"
            st.rerun()
    else:
        pw = st.text_input("教師パスワード", type="password")
        if st.button("ログイン") and pw == TEACHER_PASSWORD:
            st.session_state.mode = "teacher"
            st.rerun()

elif st.session_state.mode == "student":
    if st.button("ログアウト"):
        st.session_state.clear()
        st.rerun()
    student_view()

else:
    if st.button("ログアウト"):
        st.session_state.clear()
        st.rerun()
    teacher_view()

