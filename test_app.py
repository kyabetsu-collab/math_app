import streamlit as st
import json
import random
import pandas as pd
import math
import sympy as sp
import re
from datetime import datetime

# ================================
# 設定
# ================================
PROBLEM_FILE = "problems.json"
TEACHER_PASSWORD = "20020711"

# ================================
# 共通関数
# ================================
def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def load_problems():
    try:
        with open(PROBLEM_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_problems(problems):
    with open(PROBLEM_FILE, "w", encoding="utf-8") as f:
        json.dump(problems, f, ensure_ascii=False, indent=2)

# ================================
# 採点処理
# ================================
def normalize(s):
    if not isinstance(s, str):
        return s
    s = s.replace("　", " ").strip()
    s = re.sub(r"\s*,\s*", ",", s)
    return s

def safe_eval(expr):
    try:
        expr = expr.replace("√", "sqrt")
        return float(eval(expr, {"sqrt": math.sqrt}))
    except:
        return None

def equal_answer(student, correct):
    student = normalize(student)
    correct = normalize(correct)

    try:
        return sp.simplify(sp.sympify(student) - sp.sympify(correct)) == 0
    except:
        s = safe_eval(student)
        c = safe_eval(correct)
        if s is not None and c is not None:
            return abs(s - c) < 1e-6
        return student.lower() == correct.lower()

def check_answer(student, correct):
    if isinstance(correct, list):
        return any(equal_answer(student, c) for c in correct)
    return equal_answer(student, correct)

# ================================
# 生徒画面
# ================================
def student_view():
    st.header("✏ 生徒用テスト画面")
    problems = load_problems()

    if not problems:
        st.info("問題がまだ登録されていません。")
        return

    n = len(problems)

    if "order" not in st.session_state:
        st.session_state.order = list(range(n))
        random.shuffle(st.session_state.order)
        st.session_state.q = 0
        st.session_state.results = [{} for _ in range(n)]

    idx = st.session_state.order[st.session_state.q]
    prob = problems[idx]

    st.subheader(f"問題 {st.session_state.q+1}/{n}")
    st.write(prob["question"])

    key = f"ans_{st.session_state.q}"
    answer = st.text_input("答え", key=key)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("次へ"):
            st.session_state.results[st.session_state.q] = {
                "question": prob["question"],
                "student_answer": answer,
                "correct_answer": prob["answer"],
                "is_correct": check_answer(answer, prob["answer"])
            }
            if st.session_state.q < n-1:
                st.session_state.q += 1
    with col2:
        if st.button("戻る") and st.session_state.q > 0:
            st.session_state.q -= 1

    if all("is_correct" in r for r in st.session_state.results):
        if st.button("結果を見る"):
            df = pd.DataFrame(st.session_state.results)
            st.dataframe(df)
            rate = df["is_correct"].mean() * 100
            st.success(f"正答率：{rate:.1f}%")

# ================================
# 教師画面
# ================================
def teacher_view():
    st.header("🧑‍🏫 教師用管理画面")
    problems = load_problems()

    st.subheader("📘 問題編集")
    for i, p in enumerate(problems):
        with st.expander(f"{i+1}. {p['question']}"):
            q = st.text_input("問題文", p["question"], key=f"q{i}")
            a = st.text_input("答え（複数は [\"a\",\"b\"]）", str(p["answer"]), key=f"a{i}")

            if st.button("保存", key=f"s{i}"):
                try:
                    ans = json.loads(a) if a.startswith("[") else a
                except:
                    ans = a
                problems[i] = {"question": q, "answer": ans}
                save_problems(problems)
                st.success("保存しました")
                st.experimental_rerun()

            if st.button("削除", key=f"d{i}"):
                problems.pop(i)
                save_problems(problems)
                st.experimental_rerun()

    st.subheader("➕ 新規追加")
    nq = st.text_input("新しい問題文")
    na = st.text_input("答え")
    if st.button("追加"):
        try:
            na_val = json.loads(na) if na.startswith("[") else na
        except:
            na_val = na
        problems.append({"question": nq, "answer": na_val})
        save_problems(problems)
        st.success("追加しました")
        st.experimental_rerun()

# ================================
# メイン（ログイン管理）
# ================================
st.set_page_config(page_title="数学学習アプリ", layout="centered")
st.caption(f"起動時刻：{now()}")

if "mode" not in st.session_state:
    st.session_state.mode = None

# --- ログイン ---
if st.session_state.mode is None:
    st.title("📘 数学学習アプリ")
    mode = st.radio("利用者を選択", ["生徒", "教師"])

    if mode == "生徒":
        if st.button("開始"):
            st.session_state.mode = "student"
            st.experimental_rerun()

    else:
        pw = st.text_input("教師パスワード", type="password")
        if st.button("ログイン"):
            if pw == TEACHER_PASSWORD:
                st.session_state.mode = "teacher"
                st.experimental_rerun()
            else:
                st.error("パスワードが違います")

# --- 生徒 ---
elif st.session_state.mode == "student":
    if st.button("ログアウト"):
        st.session_state.clear()
        st.experimental_rerun()
    student_view()

# --- 教師 ---
elif st.session_state.mode == "teacher":
    if st.button("ログアウト"):
        st.session_state.clear()
        st.experimental_rerun()
    teacher_view()

