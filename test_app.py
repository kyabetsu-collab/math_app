# ==============================
# 数学学習アプリ【完全・最終分析版】
# Streamlit 1.30+
# ==============================

import streamlit as st
import json
import random
import pandas as pd
import sympy as sp
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
        if df.empty:
            return None
        if not all(c in df.columns for c in REQUIRED_COLUMNS):
            return None
        df["is_correct"] = df["is_correct"].astype(int)
        return df
    except Exception:
        return None

def reset_results():
    if os.path.exists(RESULT_FILE):
        os.remove(RESULT_FILE)

# ==============================
# 採点処理（完全対応）
# ==============================

def normalize_text(s):
    if not isinstance(s, str):
        return s
    s = unicodedata.normalize("NFKC", s)
    s = s.strip().replace(" ", "")
    s = s.replace("√", "sqrt").replace("，", ",")
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

    if "," in student or "," in correct:
        try:
            return normalize_solution(student) == normalize_solution(correct)
        except Exception:
            pass

    s_expr = safe_sympy(student)
    c_expr = safe_sympy(correct)
    if s_expr is not None and c_expr is not None:
        return sp.simplify(s_expr - c_expr) == 0

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
    answer = st.text_input("答え", value=default)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("回答して次へ"):
            st.session_state.results[idx] = {
                "student_id": student_id,
                "question": prob["question"],
                "student_answer": answer,
                "correct_answer": str(prob["answer"]),
                "is_correct": int(check_answer(answer, prob["answer"])),
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
# 教師画面（分析 完全版）
# ==============================

def teacher_view():
    st.header("🧑‍🏫 教師用管理")

    st.subheader("📊 成績分析")

    df = load_results_safe()
    if df is None:
        st.warning("成績データがありません")
        return

    # ---------- 全体 ----------
    st.markdown("### 👥 クラス全体")

    st.metric("クラス正答率", f"{df['is_correct'].mean()*100:.1f}%")

    q_stats = (
        df.groupby("question")["is_correct"]
          .agg(["mean", "count"])
          .reset_index()
    )
    q_stats["正答率(%)"] = q_stats["mean"] * 100
    q_stats["誤答率(%)"] = 100 - q_stats["正答率(%)"]

    st.dataframe(
        q_stats[["question", "正答率(%)", "誤答率(%)"]].round(1)
    )

    st.bar_chart(
        q_stats.set_index("question")[["正答率(%)", "誤答率(%)"]]
    )

    st.divider()

    # ---------- 個人 ----------
    st.markdown("### 👤 個人分析")

    sid = st.selectbox("生徒IDを選択", sorted(df["student_id"].unique()))
    sdf = df[df["student_id"] == sid]

    st.metric("個人正答率", f"{sdf['is_correct'].mean()*100:.1f}%")

    per_q = sdf.groupby("question")["is_correct"].mean().reset_index()
    per_q["正答率(%)"] = per_q["is_correct"] * 100

    st.bar_chart(
        per_q.set_index("question")["正答率(%)"]
    )

    st.markdown("#### ❌ 間違えた問題")

    wrong = sdf[sdf["is_correct"] == 0]
    if wrong.empty:
        st.success("全問正解です")
    else:
        st.dataframe(
            wrong[["question", "student_answer", "correct_answer"]]
        )

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

