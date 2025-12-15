
import streamlit as st
import json
import random
import pandas as pd
import math
import sympy as sp
import re
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
    try:
        with open(PROBLEM_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_problems(problems):
    with open(PROBLEM_FILE, "w", encoding="utf-8") as f:
        json.dump(problems, f, ensure_ascii=False, indent=2)

# ==============================
# 採点処理
# ==============================
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

def is_equal(student, correct):
    student = normalize(student)
    correct = normalize(correct)

    try:
        return sp.simplify(sp.sympify(student) - sp.sympify(correct)) == 0
    except:
        sv = safe_eval(student)
        cv = safe_eval(correct)
        if sv is not None and cv is not None:
            return abs(sv - cv) < 1e-6
        return student.lower() == correct.lower()

def check_answer(student, correct):
    if isinstance(correct, list):
        return any(is_equal(student, c) for c in correct)
    return is_equal(student, correct)

# ==============================
# 生徒画面
# ==============================
def student_view():
    st.header("✏ 生徒用テスト")
    st.caption(f"日時：{now()}")

    problems = load_problems()
    n = len(problems)

    if n == 0:
        st.info("問題がまだ登録されていません。")
        return

    if "order" not in st.session_state:
        st.session_state.order = list(range(n))
        random.shuffle(st.session_state.order)
        st.session_state.q = 0
        st.session_state.results = {}
        st.session_state.finished = False

    idx = st.session_state.order[st.session_state.q]
    prob = problems[idx]

    st.subheader(f"問題 {st.session_state.q + 1} / {n}")
    st.write(prob["question"])

    ans_key = f"ans_{idx}"
    answer = st.text_input("答えを入力", key=ans_key)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("回答して次へ"):
            st.session_state.results[idx] = {
                "question": prob["question"],
                "student_answer": answer,
                "correct_answer": str(prob["answer"]),
                "is_correct": check_answer(answer, prob["answer"]),
                "timestamp": now()
            }

            if st.session_state.q < n - 1:
                st.session_state.q += 1
            else:
                st.session_state.finished = True

            st.rerun()

    with col2:
        if st.button("前へ戻る") and st.session_state.q > 0:
            st.session_state.q -= 1
            st.rerun()

    if st.session_state.finished:
        st.divider()
        if st.button("結果を見る"):
            df = pd.DataFrame(st.session_state.results.values())

            df.to_csv(
                RESULT_FILE,
                mode="a",
                header=not os.path.exists(RESULT_FILE),
                index=False,
                encoding="utf-8"
            )

            st.subheader("📊 解答結果")
            st.dataframe(df)
            st.success(f"正答率：{df['is_correct'].mean() * 100:.1f}%")

# ==============================
# 教師画面
# ==============================
def teacher_view():
    st.header("🧑‍🏫 教師用管理")
    st.caption(f"日時：{now()}")

    problems = load_problems()

    st.subheader("📘 問題編集")
    for i, p in enumerate(problems):
        with st.expander(f"{i+1}. {p['question']}"):
            q = st.text_input("問題文", p["question"], key=f"q{i}")
            a = st.text_input("答え（複数は [\"a\",\"b\"]）", str(p["answer"]), key=f"a{i}")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("保存", key=f"s{i}"):
                    try:
                        ans = json.loads(a) if a.startswith("[") else a
                    except:
                        ans = a
                    problems[i] = {"question": q, "answer": ans}
                    save_problems(problems)
                    st.success("保存しました")
                    st.rerun()

            with col2:
                if st.button("削除", key=f"d{i}"):
                    problems.pop(i)
                    save_problems(problems)
                    st.rerun()

    st.subheader("➕ 新規問題追加")
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
        st.rerun()

    # ===== 分析 =====
    st.divider()
    st.subheader("📊 正答率分析")

    if os.path.exists(RESULT_FILE):
        df = pd.read_csv(RESULT_FILE)

        overall = df["is_correct"].mean() * 100
        st.metric("全体正答率", f"{overall:.1f}%")

        rate_df = (
            df.groupby("question")["is_correct"]
            .mean()
            .reset_index()
        )
        rate_df["正答率(%)"] = rate_df["is_correct"] * 100

        st.subheader("問題ごとの正答率（表）")
        st.dataframe(rate_df[["question", "正答率(%)"]])

        st.subheader("問題ごとの正答率（グラフ）")
        st.bar_chart(
            rate_df.set_index("question")["正答率(%)"]
        )
    else:
        st.info("まだ生徒の解答データがありません。")

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
        if st.button("生徒として開始"):
            st.session_state.mode = "student"
            st.rerun()
    else:
        pw = st.text_input("教師パスワード", type="password")
        if st.button("ログイン"):
            if pw == TEACHER_PASSWORD:
                st.session_state.mode = "teacher"
                st.rerun()
            else:
                st.error("パスワードが違います")

elif st.session_state.mode == "student":
    if st.button("ログアウト"):
        st.session_state.clear()
        st.rerun()
    student_view()

elif st.session_state.mode == "teacher":
    if st.button("ログアウト"):
        st.session_state.clear()
        st.rerun()
    teacher_view()


