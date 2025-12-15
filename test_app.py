# ==============================
# 数学学習アプリ【完全・安定版】
# ==============================

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

REQUIRED_COLUMNS = [
    "student_id",
    "question",
    "student_answer",
    "correct_answer",
    "is_correct",
    "timestamp",
]

# ==============================
# 共通関数
# ==============================

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def load_problems():
    if not os.path.exists(PROBLEM_FILE):
        return []
    try:
        with open(PROBLEM_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


def save_problems(problems):
    with open(PROBLEM_FILE, "w", encoding="utf-8") as f:
        json.dump(problems, f, ensure_ascii=False, indent=2)


def load_results_safe():
    if not os.path.exists(RESULT_FILE):
        return None
    try:
        df = pd.read_csv(RESULT_FILE)
        if not all(col in df.columns for col in REQUIRED_COLUMNS):
            return None
        return df
    except:
        return None


def reset_results():
    if os.path.exists(RESULT_FILE):
        os.remove(RESULT_FILE)

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
        return str(student).lower() == str(correct).lower()


def check_answer(student, correct):
    if isinstance(correct, list):
        return any(is_equal(student, c) for c in correct)
    return is_equal(student, correct)

# ==============================
# 生徒画面
# ==============================

def student_view():
    st.header("✏ 生徒用テスト")

    student_id = st.text_input("生徒ID（出席番号など）")
    if student_id == "":
        st.info("生徒IDを入力してください")
        return

    problems = load_problems()
    if len(problems) == 0:
        st.warning("問題が登録されていません（教師が問題を追加してください）")
        return

    if "order" not in st.session_state:
        st.session_state.order = list(range(len(problems)))
        random.shuffle(st.session_state.order)
        st.session_state.q = 0
        st.session_state.results = {}
        st.session_state.finished = False

    idx = st.session_state.order[st.session_state.q]
    prob = problems[idx]

    st.subheader(f"問題 {st.session_state.q + 1} / {len(problems)}")
    st.write(prob["question"])

    default = st.session_state.results.get(idx, {}).get("student_answer", "")
    answer = st.text_input("答え", value=default)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("回答して次へ"):
            st.session_state.results[idx] = {
                "student_id": student_id,
                "question": prob["question"],
                "student_answer": answer,
                "correct_answer": str(prob["answer"]),
                "is_correct": check_answer(answer, prob["answer"]),
                "timestamp": now(),
            }
            if st.session_state.q < len(problems) - 1:
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
                encoding="utf-8",
            )
            st.dataframe(df)
            st.success(f"正答率：{df['is_correct'].mean()*100:.1f}%")

# ==============================
# 教師画面
# ==============================

def teacher_view():
    st.header("🧑‍🏫 教師用管理")

    # ---------- 問題編集 ----------
    st.subheader("📘 問題編集")
    problems = load_problems()

    for i, p in enumerate(problems):
        with st.expander(f"{i+1}. {p['question']}"):
            q = st.text_input("問題文", p["question"], key=f"q{i}")
            a = st.text_input("答え", str(p["answer"]), key=f"a{i}")

            if st.button("保存", key=f"s{i}"):
                try:
                    ans = json.loads(a) if a.startswith("[") else a
                except:
                    ans = a
                problems[i] = {"question": q, "answer": ans}
                save_problems(problems)
                st.success("保存しました")
                st.rerun()

            if st.button("削除", key=f"d{i}"):
                problems.pop(i)
                save_problems(problems)
                st.rerun()

    st.subheader("➕ 新規問題追加")
    nq = st.text_input("新しい問題文")
    na = st.text_input("答え")
    if st.button("追加"):
        try:
            na = json.loads(na) if na.startswith("[") else na
        except:
            pass
        problems.append({"question": nq, "answer": na})
        save_problems(problems)
        st.success("追加しました")
        st.rerun()

    # ---------- 成績分析 ----------
    st.divider()
    st.subheader("📊 成績分析")

    df = load_results_safe()
    if df is None:
        st.error("成績データを読み込めません。リセットしてください。")
        if st.button("🔄 成績データをリセット"):
            reset_results()
            st.success("リセットしました")
            st.rerun()
        return

    st.metric("クラス正答率", f"{df['is_correct'].mean()*100:.1f}%")

    qrate = df.groupby("question")["is_correct"].mean() * 100
    st.subheader("問題別正答率")
    st.bar_chart(qrate)

    st.subheader("👤 個人成績")
    sid = st.selectbox("生徒ID", sorted(df["student_id"].unique()))
    sdf = df[df["student_id"] == sid]

    st.metric("個人正答率", f"{sdf['is_correct'].mean()*100:.1f}%")

    sdf["timestamp"] = pd.to_datetime(sdf["timestamp"])
    sdf = sdf.sort_values("timestamp")
    sdf["累積正答率"] = sdf["is_correct"].expanding().mean() * 100

    st.line_chart(sdf.set_index("timestamp")["累積正答率"])

    st.divider()
    if st.button("⚠ 全成績データを完全リセット"):
        reset_results()
        st.success("全データを削除しました")
        st.rerun()

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

