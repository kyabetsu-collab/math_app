# ==============================
# 数学学習アプリ【完全・最終版】
# Streamlit 1.30+
# ==============================

import streamlit as st
import json
import random
import pandas as pd
import math
import sympy as sp
import re
import os
import unicodedata
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
    except Exception:
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
    except Exception:
        return None


def reset_results():
    if os.path.exists(RESULT_FILE):
        os.remove(RESULT_FILE)

# ==============================
# 採点処理（表記ゆれ完全吸収）
# ==============================

def normalize_text(s):
    if not isinstance(s, str):
        return s

    s = unicodedata.normalize("NFKC", s)
    s = s.strip().replace(" ", "")
    s = s.replace("，", ",").replace("√", "sqrt")
    s = s.replace("十分条件", "十分").replace("必要条件", "必要")
    s = s.strip("{}()")
    return s


def normalize_solution(s):
    s = normalize_text(s)
    s = s.replace("x=", "")
    parts = s.split(",")
    try:
        parts = [str(sp.simplify(p)) for p in parts]
    except Exception:
        pass
    return sorted(parts)


def safe_sympy(expr):
    try:
        return sp.simplify(sp.sympify(expr))
    except Exception:
        return None


def is_equal(student, correct):
    student = normalize_text(student)
    correct = normalize_text(correct)

    # 解集合（順序無視）
    if "," in student or "," in correct:
        try:
            return normalize_solution(student) == normalize_solution(correct)
        except Exception:
            pass

    # 数式比較
    s_expr = safe_sympy(student)
    c_expr = safe_sympy(correct)
    if s_expr is not None and c_expr is not None:
        return sp.simplify(s_expr - c_expr) == 0

    # 数値比較
    try:
        return abs(float(student) - float(correct)) < 1e-6
    except Exception:
        pass

    return student == correct


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
    if not problems:
        st.warning("問題が登録されていません")
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
    key = f"answer_{st.session_state.q}"

    answer = st.text_input("答え", value=default, key=key)

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

    st.subheader("📘 問題編集")
    problems = load_problems()

    for i, p in enumerate(problems):
        with st.expander(f"{i+1}. {p['question']}"):
            q = st.text_input("問題文", p["question"], key=f"q{i}")
            a = st.text_input("答え", str(p["answer"]), key=f"a{i}")

            if st.button("保存", key=f"s{i}"):
                try:
                    ans = json.loads(a) if a.startswith("[") else a
                except Exception:
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
        except Exception:
            pass
        problems.append({"question": nq, "answer": na})
        save_problems(problems)
        st.success("追加しました")
        st.rerun()

    st.divider()
    st.subheader("📊 成績分析")

    df = load_results_safe()
    if df is None:
        st.error("成績データを読み込めません")
        if st.button("🔄 リセット"):
            reset_results()
            st.rerun()
        return

    st.metric("クラス正答率", f"{df['is_correct'].mean()*100:.1f}%")
    st.bar_chart(df.groupby("question")["is_correct"].mean() * 100)

    sid = st.selectbox("生徒ID", sorted(df["student_id"].unique()))
    sdf = df[df["student_id"] == sid].copy()

    st.metric("個人正答率", f"{sdf['is_correct'].mean()*100:.1f}%")

    sdf["timestamp"] = pd.to_datetime(sdf["timestamp"])
    sdf["累積正答率"] = sdf["is_correct"].expanding().mean() * 100
    st.line_chart(sdf.set_index("timestamp")["累積正答率"])

    if st.button("⚠ 全成績リセット"):
        reset_results()
        st.rerun()

# ==============================
# メイン
# ==============================

st.set_page_config(page_title="学習アプリ")

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

